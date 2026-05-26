"""
QQ 新消息联合分析：同时完成单条分类 + 话题聚合（仅处理新增消息）。

Phase2 + Phase3 合一，避免多次 AI 调用的信息损耗。
手动「重新聚合」按钮仍走 topic_cluster.cluster_topics()（全量重算）。
"""
import json
import logging
import uuid
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.router import get_ai_router
from app.ai.topic_cluster import _split_into_batches  # 复用批次切分逻辑

logger = logging.getLogger(__name__)

_MIN_TOPIC_MESSAGES = 2

_SYSTEM_PROMPT = """\
你是一个游戏社区运营助手，分析 QQ 群聊天记录。

任务一：对每条消息判断是否与游戏相关，并分配分类和情感。

分类标准（选一个最符合的）：
  bug        — 游戏出现非预期的错误、崩溃或功能失效。
               例：闪退、技能失效、数据丢失、显示错误、进不了游戏。
               文字包含：崩溃、卡住、不行、打不开、丢了、错了、失效、异常等。
  suggestion — 玩家希望新增或修改某个功能/设计。
               例："建议加个XXX"、"能不能把XXX改成YYY"、"希望增加..."。
               文字包含：建议、希望、能不能、要是...就好了等。
  complaint  — 对游戏现有设计/运营/定价的不满（非bug，是对有意设计的抱怨）。
               例：价格太贵、平衡性差、更新太慢、某机制不合理。
               文字包含：太贵、太慢、不合理、平衡差、讨厌、烦、太强、太弱、没用、下水道等。
  praise     — 明确的正面评价。
               例："这个版本改得很好"、"XXX功能做得很棒"。
               文字包含：很好、棒、喜欢、爱了、强了、太好了、好玩、不错等。
  other      — 与游戏相关但不属于以上（攻略讨论、资讯转发、活动等）。
  null       — 与游戏无关或无法判断（闲聊、红包、广告、图片等）。

情感标准：
  positive   — 整体正面/满意
  negative   — 整体负面/不满
  neutral    — 中性或混合
  null       — 无法判断

任务二：找出哪些消息属于同一话题（多人讨论同一问题），生成话题标题和摘要。
  - 话题至少需要 2 条相关消息
  - 孤立消息只出现在 messages 数组中，不进入任何话题

返回纯 JSON（不含 markdown 代码块）：
{
  "messages": [
    {"index": 0, "category": "bug", "sentiment": "negative"},
    {"index": 1, "category": null, "sentiment": null}
  ],
  "topics": [
    {
      "title": "登录闪退问题",
      "summary": "多名玩家反馈进入游戏时出现闪退...",
      "category": "bug",
      "sentiment": "negative",
      "indices": [0, 1, 3]
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
) -> None:
    """
    对本次新增的 QQ 评论做联合分析：
    1. 更新 Comment.category / Comment.sentiment
    2. 创建 QQTopic 记录（不删除旧话题，仅追加）
    """
    from sqlalchemy import select
    from app.models import Comment

    if not new_comment_ids:
        return

    # 按时间升序读取新消息
    result = await db.execute(
        select(Comment)
        .where(Comment.id.in_(new_comment_ids))
        .order_by(Comment.published_at.asc())
    )
    comments = result.scalars().all()
    if not comments:
        return

    game_uuid = uuid.UUID(game_id) if isinstance(game_id, str) else game_id
    batches = _split_into_batches(comments)
    logger.info(f"[qq_analyzer] game_id={game_id} {len(comments)} 条新消息，分 {len(batches)} 批")

    for i, batch in enumerate(batches):
        logger.info(f"[qq_analyzer] 处理第 {i + 1}/{len(batches)} 批（{len(batch)} 条）")
        await _analyze_batch(batch, game_uuid, db)

    await db.commit()
    logger.info(f"[qq_analyzer] game_id={game_id} 联合分析完成")


async def _analyze_batch(batch: list, game_uuid: uuid.UUID, db: AsyncSession) -> None:
    from app.models import QQTopic

    numbered = "\n".join(
        f"{i}. [{c.author_name or '匿名'}] {c.content[:200]}"
        for i, c in enumerate(batch)
    )

    router = get_ai_router()
    try:
        resp = await router.chat(_SYSTEM_PROMPT, numbered, temperature=0.2, max_tokens=3000)
    except Exception as e:
        logger.warning(f"[qq_analyzer] AI 调用失败，跳过本批: {e}")
        return

    # 提取 JSON（防止模型在前后加废话）
    text = resp.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        logger.warning(f"[qq_analyzer] AI 返回无法解析: {text[:200]}")
        return

    try:
        data = json.loads(text[start:end])
    except json.JSONDecodeError as e:
        logger.warning(f"[qq_analyzer] JSON 解析失败: {e} | 原文: {text[:200]}")
        return

    # ── 更新单条分类 ──────────────────────────────────────────────────────
    for msg_info in data.get("messages", []):
        idx = msg_info.get("index")
        if not isinstance(idx, int) or idx >= len(batch):
            continue
        comment = batch[idx]
        cat = msg_info.get("category")
        sent = msg_info.get("sentiment")
        if cat in _VALID_CATEGORIES:
            comment.category = cat
        if sent in _VALID_SENTIMENTS:
            comment.sentiment = sent

    # ── 创建话题（追加，不删旧话题）──────────────────────────────────────
    for topic_data in data.get("topics", []):
        indices = topic_data.get("indices", [])
        valid_indices = [i for i in indices if isinstance(i, int) and 0 <= i < len(batch)]
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
            title=topic_data.get("title", "未命名话题")[:255],
            summary=topic_data.get("summary", ""),
            category=cat if cat in _VALID_CATEGORIES else None,
            sentiment=sent if sent in _VALID_SENTIMENTS else None,
            group_id=group_id,
            comment_ids=comment_ids,
            started_at=min(times) if times else None,
            ended_at=max(times) if times else None,
        ))

    kept = sum(
        1 for m in data.get("messages", [])
        if m.get("category") in _VALID_CATEGORIES
    )
    topics_created = len([
        t for t in data.get("topics", [])
        if len([
            i for i in t.get("indices", [])
            if isinstance(i, int) and 0 <= i < len(batch)
        ]) >= _MIN_TOPIC_MESSAGES
    ])
    logger.info(f"[qq_analyzer] 本批：{kept}/{len(batch)} 条有分类，{topics_created} 个话题")
