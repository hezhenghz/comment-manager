"""
群聊话题聚合（QQ + Discord）

把时间上相近、语义相关的群聊消息聚合成「话题」，由 AI 生成标题和摘要。
每次爬取完成后自动触发，全量重算该游戏的话题列表。
"""

import json
import logging
import uuid
from datetime import timedelta

from app.ai.router import get_ai_router

logger = logging.getLogger(__name__)

# 每批最多条数
_BATCH_SIZE = 30
# 批内时间窗口上限（超过则强制切批）
_BATCH_WINDOW_HOURS = 2
# 话题至少需要几条消息（孤立消息不成话题）
_MIN_TOPIC_MESSAGES = 2

# 各平台对应的 raw_json 频道字段名
_PLATFORM_CHANNEL = {
    "qq":      "group_id",
    "discord": "channel_id",
}

_SYSTEM_PROMPT = """\
你是一个游戏社区运营助手，负责分析群聊/频道聊天记录，找出玩家集中讨论的话题。

你的任务：
1. 把给定的带编号消息列表中，时间上连续且语义相关的消息归为同一话题
2. 每条消息只能归属一个话题；孤立消息（与其他消息话题无关）不归入任何话题
3. 为每个话题生成简短标题（10字以内）和摘要（50-150字）
4. 判断话题的分类（bug/suggestion/complaint/praise/other）和情感（positive/negative/neutral）

严格要求：
- 返回纯 JSON 数组，不加任何解释、markdown 代码块或其他文字
- 若所有消息都是孤立的，返回空数组 []
- indices 是消息的编号列表（从 0 开始）

输出格式（示例）：
[
  {
    "title": "登录闪退问题",
    "summary": "多名玩家反馈进入游戏时出现闪退，主要集中在手机端...",
    "category": "bug",
    "sentiment": "negative",
    "indices": [0, 1, 3]
  }
]"""


def _split_into_batches(comments: list) -> list[list]:
    """按时间窗口将消息切分为批次，每批最多 _BATCH_SIZE 条、时间跨度不超过 _BATCH_WINDOW_HOURS。"""
    if not comments:
        return []

    batches: list[list] = []
    current: list = []
    batch_start_time = None

    for c in comments:
        ts = c.published_at
        if not current:
            current.append(c)
            batch_start_time = ts
            continue

        # 超出时间窗口或批次大小，切批
        time_exceeded = (
            ts and batch_start_time and
            (ts - batch_start_time) > timedelta(hours=_BATCH_WINDOW_HOURS)
        )
        size_exceeded = len(current) >= _BATCH_SIZE

        if time_exceeded or size_exceeded:
            batches.append(current)
            current = [c]
            batch_start_time = ts
        else:
            current.append(c)

    if current:
        batches.append(current)

    return batches


async def _cluster_batch(batch: list, channel_field: str = "group_id") -> list[dict]:
    """对一批消息调用 AI，返回话题列表（含 indices 已映射为 comment.id）。"""
    numbered = "\n".join(
        f"{i}. [{c.author_name or '匿名'}] {c.content[:200]}"
        for i, c in enumerate(batch)
    )

    router = get_ai_router()
    try:
        resp = await router.chat(
            _SYSTEM_PROMPT,
            numbered,
            temperature=0.2,
            max_tokens=2048,
        )
    except Exception as e:
        logger.warning(f"[topic_cluster] AI 调用失败: {e}")
        return []

    # 提取 JSON（防止模型在前后加废话）
    text = resp.strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        logger.warning(f"[topic_cluster] AI 返回无法解析为 JSON 数组: {text[:200]}")
        return []

    try:
        raw_topics = json.loads(text[start:end])
    except json.JSONDecodeError as e:
        logger.warning(f"[topic_cluster] JSON 解析失败: {e} | 原文: {text[:200]}")
        return []

    results = []
    for t in raw_topics:
        indices = t.get("indices", [])
        # 过滤掉消息数不足的话题
        valid_indices = [i for i in indices if isinstance(i, int) and 0 <= i < len(batch)]
        if len(valid_indices) < _MIN_TOPIC_MESSAGES:
            continue

        comment_ids = [batch[i].id for i in valid_indices]
        times = [batch[i].published_at for i in valid_indices if batch[i].published_at]

        # 取该话题消息中出现最多的频道/群 ID
        from collections import Counter
        channel_ids_in_topic = [
            (batch[i].raw_json or {}).get(channel_field)
            for i in valid_indices
        ]
        channel_id_counts = Counter(cid for cid in channel_ids_in_topic if cid)
        group_id = channel_id_counts.most_common(1)[0][0] if channel_id_counts else None

        results.append({
            "title":       t.get("title", "未命名话题")[:255],
            "summary":     t.get("summary", ""),
            "category":    t.get("category") if t.get("category") in ("bug", "suggestion", "complaint", "praise", "other") else None,
            "sentiment":   t.get("sentiment") if t.get("sentiment") in ("positive", "negative", "neutral") else None,
            "group_id":    group_id,
            "comment_ids": comment_ids,
            "started_at":  min(times) if times else None,
            "ended_at":    max(times) if times else None,
        })

    return results


async def cluster_topics(game_id: str, db) -> None:
    """
    全量重算指定游戏的 QQ + Discord 话题。
    - 清空旧话题，分平台重新聚合写入
    """
    from sqlalchemy import select, delete
    from app.models import Comment, QQTopic

    game_uuid = uuid.UUID(game_id) if isinstance(game_id, str) else game_id

    # 1. 清空旧话题
    await db.execute(delete(QQTopic).where(QQTopic.game_id == game_id))
    await db.flush()

    total_topics = 0

    # 2. 分平台聚合
    for platform, channel_field in _PLATFORM_CHANNEL.items():
        result = await db.execute(
            select(Comment)
            .where(Comment.game_id == game_id, Comment.platform == platform)
            .order_by(Comment.published_at.asc())
        )
        comments = result.scalars().all()

        if not comments:
            logger.info(f"[topic_cluster] game_id={game_id} 无 {platform} 评论，跳过")
            continue

        batches = _split_into_batches(comments)
        logger.info(f"[topic_cluster] game_id={game_id} {platform} 共 {len(comments)} 条消息，分 {len(batches)} 批")

        for i, batch in enumerate(batches):
            logger.info(f"[topic_cluster] {platform} 第 {i + 1}/{len(batches)} 批（{len(batch)} 条）")
            topics = await _cluster_batch(batch, channel_field)
            for t in topics:
                db.add(QQTopic(
                    game_id=game_uuid,
                    platform=platform,
                    title=t["title"],
                    summary=t["summary"],
                    category=t["category"],
                    sentiment=t["sentiment"],
                    group_id=t.get("group_id"),
                    comment_ids=t["comment_ids"],
                    started_at=t["started_at"],
                    ended_at=t["ended_at"],
                ))
            total_topics += len(topics)
            logger.info(f"[topic_cluster] {platform} 第 {i + 1} 批识别出 {len(topics)} 个话题")

    await db.commit()
    logger.info(f"[topic_cluster] game_id={game_id} 话题聚合完成，共 {total_topics} 个话题")


async def analyze_new_discord_topics(
    game_id: str,
    new_comment_ids: list[uuid.UUID],
    db,
) -> None:
    """
    对本次新增的 Discord 消息做话题聚合（追加，不删除旧话题）。
    分类已由 run_pipeline 完成，此处仅做话题聚合。
    """
    from sqlalchemy import select
    from app.models import Comment, QQTopic

    if not new_comment_ids:
        return

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
    logger.info(f"[topic_cluster] game_id={game_id} Discord {len(comments)} 条新消息，分 {len(batches)} 批")

    for i, batch in enumerate(batches):
        logger.info(f"[topic_cluster] Discord 新增第 {i + 1}/{len(batches)} 批（{len(batch)} 条）")
        topics = await _cluster_batch(batch, "channel_id")
        for t in topics:
            db.add(QQTopic(
                game_id=game_uuid,
                platform="discord",
                title=t["title"],
                summary=t["summary"],
                category=t["category"],
                sentiment=t["sentiment"],
                group_id=t.get("group_id"),
                comment_ids=t["comment_ids"],
                started_at=t["started_at"],
                ended_at=t["ended_at"],
            ))
        logger.info(f"[topic_cluster] Discord 新增第 {i + 1} 批识别出 {len(topics)} 个话题")

    await db.commit()
    logger.info(f"[topic_cluster] game_id={game_id} Discord 话题追加完成")
