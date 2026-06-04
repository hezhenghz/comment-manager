"""
QQ 新消息联合分析：同时完成单条分类 + 话题聚合（仅处理新增消息）。

返回 (processed_ids, skipped_ids)，供 AI worker 精确判定状态：
  - processed_ids：AI 真实分析过且判为游戏反馈的评论（done 候选）
  - skipped_ids  ：AI 真实分析过但判为非反馈（水群/广告/红包/图片）的评论（skipped 候选）
  - 既不在 processed 也不在 skipped 的：AI 调用失败 / AI 漏返回（retry 候选）

手动「重新聚合」按钮仍走 topic_cluster.cluster_topics()（全量重算）。
"""
import logging
import uuid
from collections import Counter

from json_repair import repair_json

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.router import get_ai_router
from app.ai.topic_cluster import _split_into_batches  # 复用批次切分逻辑

logger = logging.getLogger(__name__)

_MIN_TOPIC_MESSAGES = 2

_SYSTEM_PROMPT = """\
你是一个游戏社区运营助手，分析 QQ 群聊天记录。

任务一：对每条消息按 index 顺序逐条判断，必须为输入里的【每一条】返回结果，不得遗漏。
        对每条输出 is_feedback（布尔值）：
  - is_feedback = false  : 与游戏无关或无法判断（闲聊、红包、广告、图片、表情、纯语气词等）。
                           不必返回 category 和 sentiment。
  - is_feedback = true   : 与游戏相关的有效反馈。
                           必须返回 category 和 sentiment（不能省略，不能为 null）。

分类（仅当 is_feedback=true 时返回，从下面 5 个里选一个最符合的）：
  bug        — 游戏出现非预期的错误、崩溃或功能失效。
               例：闪退、技能失效、数据丢失、显示错误、进不了游戏。
  suggestion — 玩家希望新增或修改某个功能/设计。
               例："建议加个XXX"、"能不能把XXX改成YYY"、"希望增加..."。
  complaint  — 对游戏现有设计/运营/定价的不满（非 bug，是对有意设计的抱怨）。
               例：价格太贵、平衡性差、更新太慢、某机制不合理。
  praise     — 明确的正面评价。
               例："这个版本改得很好"、"XXX功能做得很棒"。
  other      — 与游戏相关但不属于以上（攻略讨论、资讯转发、活动等）。

情感（仅当 is_feedback=true 时返回，从下面 3 个里选一个）：
  positive   — 整体正面/满意
  negative   — 整体负面/不满
  neutral    — 中性或混合（讨论性、客观描述、混合情绪都归 neutral）

任务二：找出哪些 is_feedback=true 的消息属于同一话题（多人讨论同一问题），生成话题标题和摘要。
  - 话题至少需要 2 条相关消息
  - is_feedback=false 的消息不进入任何话题
  - 孤立的反馈消息也不进入话题，只出现在 messages 数组中

返回纯 JSON（不含 markdown 代码块，不要省略任何输入 index）：
{
  "messages": [
    {"index": 0, "is_feedback": false},
    {"index": 1, "is_feedback": true, "category": "bug", "sentiment": "negative"},
    {"index": 2, "is_feedback": true, "category": "other", "sentiment": "neutral"}
  ],
  "topics": [
    {
      "title": "登录闪退问题",
      "summary": "多名玩家反馈进入游戏时出现闪退...",
      "category": "bug",
      "sentiment": "negative",
      "indices": [1, 3]
    }
  ]
}
"""

_VALID_CATEGORIES = {"bug", "suggestion", "complaint", "praise", "other"}
_VALID_SENTIMENTS = {"positive", "negative", "neutral"}


async def analyze_new_qq_comments(
    game_id: str,
    new_comment_ids: list[uuid.UUID],
    db: AsyncSession,
) -> tuple[set[uuid.UUID], set[uuid.UUID], set[uuid.UUID]]:
    """
    对本次新增的 QQ 评论做联合分析。

    成功路径写入：
      - is_game_feedback = True/False（每条 AI 实际处理过的都填）
      - sentiment / category（仅 is_feedback=True 的填）
      - QQTopic 追加新话题

    返回：(processed_ids, skipped_ids, batch_failed_ids)
      - processed_ids   ：AI 判定 is_feedback=True 的评论 ID（worker 应标 done）
      - skipped_ids     ：AI 判定 is_feedback=False 的评论 ID（worker 应标 skipped）
      - batch_failed_ids：所属批次【AI 调用整体失败】（router 全挂/返回不可解析）的评论 ID。
                          worker 应整批延后重试、**不计入 max_retries、永不标 failed**——
                          这是解耦设计的核心：AI 挂只造成"分析延迟"，评论永远等得到重试。
      - 以上三者都不在的 ID：AI 调用成功但【漏返回了该条 index】（worker 应单条 retry/failed）。
    """
    from sqlalchemy import select
    from app.models import Comment

    if not new_comment_ids:
        return set(), set(), set()

    # 按时间升序读取新消息
    result = await db.execute(
        select(Comment)
        .where(Comment.id.in_(new_comment_ids))
        .order_by(Comment.published_at.asc())
    )
    comments = result.scalars().all()
    if not comments:
        return set(), set(), set()

    game_uuid = uuid.UUID(game_id) if isinstance(game_id, str) else game_id
    batches = _split_into_batches(comments)
    logger.info(f"[qq_analyzer] game_id={game_id} {len(comments)} 条新消息，分 {len(batches)} 批")

    processed_ids: set[uuid.UUID] = set()
    skipped_ids: set[uuid.UUID] = set()
    batch_failed_ids: set[uuid.UUID] = set()

    for i, batch in enumerate(batches):
        logger.info(f"[qq_analyzer] 处理第 {i + 1}/{len(batches)} 批（{len(batch)} 条）")
        batch_processed, batch_skipped, ai_call_failed = await _analyze_batch(
            batch, game_uuid, db
        )
        if ai_call_failed:
            # 整批连坐保护：AI 调用整体失败 → 整批进 batch_failed，不区分单条
            batch_failed_ids |= {c.id for c in batch}
        else:
            processed_ids |= batch_processed
            skipped_ids   |= batch_skipped

    await db.commit()
    unhandled = (
        len(comments) - len(processed_ids) - len(skipped_ids) - len(batch_failed_ids)
    )
    logger.info(
        f"[qq_analyzer] game_id={game_id} 联合分析完成："
        f"processed={len(processed_ids)} skipped={len(skipped_ids)} "
        f"batch_failed={len(batch_failed_ids)} unhandled={unhandled}"
    )
    return processed_ids, skipped_ids, batch_failed_ids


async def _analyze_batch(
    batch: list, game_uuid: uuid.UUID, db: AsyncSession,
) -> tuple[set[uuid.UUID], set[uuid.UUID], bool]:
    """单批分析，返回 (processed_ids, skipped_ids, ai_call_failed)。

    ai_call_failed=True 表示【整批 AI 调用失败】（router 全挂 / 返回不可解析 / JSON 损坏）——
    调用方应把整批视为"延后重试"而非逐条失败，避免水群消息被连坐标 failed。
    ai_call_failed=False 且某条不在 processed/skipped 里 = AI 成功但漏返回该 index（单条问题）。
    """
    from app.models import QQTopic

    numbered = "\n".join(
        f"{i}. [{c.author_name or '匿名'}] {c.content[:200]}"
        for i, c in enumerate(batch)
    )

    router = get_ai_router()
    try:
        resp = await router.chat(_SYSTEM_PROMPT, numbered, temperature=0.2, max_tokens=4096)
    except Exception as e:
        logger.warning(f"[qq_analyzer] AI 调用失败，整批延后重试: {e}")
        return set(), set(), True

    # 提取并修复 JSON（模型常输出 ```json 包裹、未转义引号、缺逗号、截断尾部等畸形 JSON）
    text = resp.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    candidate = text[start:end] if start != -1 and end > start else text
    # repair_json 容错解析，return_objects 直接拿 Python 对象；无法救回时返回空串/空对象
    data = repair_json(candidate, return_objects=True)
    if not isinstance(data, dict) or not data.get("messages"):
        logger.warning(f"[qq_analyzer] JSON 修复后仍无法解析，整批延后重试 | 原文: {text[:200]}")
        return set(), set(), True

    # ── 逐条处理 messages：根据 is_feedback 分流 ──────────────────────────
    processed_ids: set[uuid.UUID] = set()
    skipped_ids:   set[uuid.UUID] = set()

    for msg_info in data.get("messages", []):
        idx = msg_info.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(batch):
            continue
        comment = batch[idx]
        is_fb = msg_info.get("is_feedback")

        if is_fb is True:
            # 反馈消息：写 sentiment/category（兜底 neutral/other）
            cat = msg_info.get("category")
            sent = msg_info.get("sentiment")
            comment.is_game_feedback = True
            comment.category  = cat  if cat  in _VALID_CATEGORIES else "other"
            comment.sentiment = sent if sent in _VALID_SENTIMENTS else "neutral"
            processed_ids.add(comment.id)
        elif is_fb is False:
            # 水群消息：明确标记非反馈，sentiment/category 留 NULL（不污染统计）
            comment.is_game_feedback = False
            skipped_ids.add(comment.id)
        else:
            # AI 没给 is_feedback，或值非法 → 视为漏判，不进任何集合（worker retry）
            logger.warning(
                f"[qq_analyzer] AI 未返回 is_feedback for idx={idx} "
                f"comment={comment.id}: {msg_info}"
            )

    # ── 创建话题（追加，不删旧话题）──────────────────────────────────────
    topics_created = 0
    for topic_data in data.get("topics", []):
        indices = topic_data.get("indices", [])
        # 仅接受 is_feedback=true 的 index
        valid_indices = [
            i for i in indices
            if isinstance(i, int) and 0 <= i < len(batch)
            and batch[i].id in processed_ids
        ]
        if len(valid_indices) < _MIN_TOPIC_MESSAGES:
            continue

        comment_ids = [batch[i].id for i in valid_indices]
        times = [batch[i].published_at for i in valid_indices if batch[i].published_at]

        group_ids_raw = [(batch[i].raw_json or {}).get("group_id") for i in valid_indices]
        gid_counts = Counter(gid for gid in group_ids_raw if gid)
        group_id = gid_counts.most_common(1)[0][0] if gid_counts else None

        cat = topic_data.get("category")
        sent = topic_data.get("sentiment")
        db.add(QQTopic(
            game_id=game_uuid,
            platform="qq",
            title=topic_data.get("title", "未命名话题")[:255],
            summary=topic_data.get("summary", ""),
            category=cat  if cat  in _VALID_CATEGORIES else None,
            sentiment=sent if sent in _VALID_SENTIMENTS else None,
            group_id=group_id,
            comment_ids=comment_ids,
            started_at=min(times) if times else None,
            ended_at=max(times) if times else None,
        ))
        topics_created += 1

    logger.info(
        f"[qq_analyzer] 本批：processed={len(processed_ids)} "
        f"skipped={len(skipped_ids)} "
        f"unhandled={len(batch) - len(processed_ids) - len(skipped_ids)} "
        f"topics={topics_created}"
    )
    return processed_ids, skipped_ids, False
