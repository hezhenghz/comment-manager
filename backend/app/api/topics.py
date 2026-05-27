import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import QQTopic, Comment, User
from app.auth import get_current_user
from app.schemas.schemas import CommentOut

router = APIRouter(prefix="/api/topics", tags=["topics"])


class TopicOut(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    title: str
    summary: str
    category: str | None = None
    sentiment: str | None = None
    group_id: str | None = None
    platform: str | None = None
    comment_count: int
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TopicListOut(BaseModel):
    total: int
    items: list[TopicOut]
    page: int
    page_size: int


@router.get("", response_model=TopicListOut)
async def list_topics(
    game_id: uuid.UUID = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from sqlalchemy import func, desc

    count_q = select(func.count(QQTopic.id)).where(QQTopic.game_id == game_id)
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(QQTopic)
        .where(QQTopic.game_id == game_id)
        .order_by(desc(func.coalesce(QQTopic.ended_at, QQTopic.created_at)))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).scalars().all()

    items = [
        TopicOut(
            id=t.id,
            game_id=t.game_id,
            title=t.title,
            summary=t.summary,
            category=t.category,
            sentiment=t.sentiment,
            group_id=t.group_id,
            platform=t.platform,
            comment_count=len(t.comment_ids or []),
            started_at=t.started_at,
            ended_at=t.ended_at,
            created_at=t.created_at,
        )
        for t in rows
    ]
    return TopicListOut(total=total, items=items, page=page, page_size=page_size)


@router.post("/recluster")
async def recluster_topics(
    game_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """手动触发指定游戏的 QQ/Discord 话题全量重算（后台异步执行）。"""
    import asyncio
    from app.ai.topic_cluster import cluster_topics
    from app.database import async_session

    async def _run():
        async with async_session() as bg_db:
            await cluster_topics(str(game_id), bg_db)

    asyncio.create_task(_run())
    return {"status": "ok", "message": "话题聚合已触发，请稍后刷新页面"}


@router.get("/{topic_id}/comments", response_model=list[CommentOut])
async def get_topic_comments(
    topic_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from sqlalchemy.orm import selectinload

    result = await db.execute(select(QQTopic).where(QQTopic.id == topic_id))
    topic = result.scalar_one_or_none()
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    if not topic.comment_ids:
        return []

    rows = (
        await db.execute(
            select(Comment)
            .options(selectinload(Comment.game))
            .where(Comment.id.in_(topic.comment_ids))
            .order_by(Comment.published_at.asc())
        )
    ).scalars().all()

    return [
        CommentOut(
            id=c.id,
            game_id=c.game_id,
            platform=c.platform,
            source_type=c.source_type,
            source_url=c.source_url,
            author_name=c.author_name,
            content=c.content,
            content_lang=c.content_lang,
            published_at=c.published_at,
            sentiment=c.sentiment,
            sentiment_score=c.sentiment_score,
            category=c.category,
            summary=c.summary,
            translation=c.translation,
            is_duplicate=c.is_duplicate,
            game_name=c.game.name if c.game else None,
            thumbs_up=c.thumbs_up,
            bug_status=c.bug_status,
        )
        for c in rows
    ]
