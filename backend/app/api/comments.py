import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Comment, Game, User
from app.auth import get_current_user
from app.schemas.schemas import CommentOut, CommentListOut

router = APIRouter(prefix="/api/comments", tags=["comments"])


@router.get("", response_model=CommentListOut)
async def list_comments(
    game_id: uuid.UUID | None = Query(None),
    platform: str | None = Query(None),
    sentiment: str | None = Query(None),
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Comment).join(Game)
    count_q = select(func.count(Comment.id)).join(Game)

    if game_id:
        query = query.where(Comment.game_id == game_id)
        count_q = count_q.where(Comment.game_id == game_id)
    if platform:
        query = query.where(Comment.platform == platform)
        count_q = count_q.where(Comment.platform == platform)
    if sentiment:
        query = query.where(Comment.sentiment == sentiment)
        count_q = count_q.where(Comment.sentiment == sentiment)
    if category:
        query = query.where(Comment.category == category)
        count_q = count_q.where(Comment.category == category)

    total = (await db.execute(count_q)).scalar() or 0
    query = query.order_by(desc(Comment.published_at)).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    items = [
        CommentOut(
            id=c.id, game_id=c.game_id, platform=c.platform, source_type=c.source_type,
            source_url=c.source_url, author_name=c.author_name, content=c.content,
            content_lang=c.content_lang, published_at=c.published_at, sentiment=c.sentiment,
            sentiment_score=c.sentiment_score, category=c.category, summary=c.summary,
            is_duplicate=c.is_duplicate, game_name=c.game.name if c.game else None,
        )
        for c in rows
    ]
    return CommentListOut(total=total, items=items, page=page, page_size=page_size)


@router.get("/{comment_id}", response_model=CommentOut)
async def get_comment(comment_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Comment).join(Game).where(Comment.id == comment_id))
    c = result.scalar_one_or_none()
    if c is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")
    return CommentOut(
        id=c.id, game_id=c.game_id, platform=c.platform, source_type=c.source_type,
        source_url=c.source_url, author_name=c.author_name, content=c.content,
        content_lang=c.content_lang, published_at=c.published_at, sentiment=c.sentiment,
        sentiment_score=c.sentiment_score, category=c.category, summary=c.summary,
        is_duplicate=c.is_duplicate, game_name=c.game.name if c.game else None,
    )
