import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Comment, Game, User
from app.auth import get_current_user
from app.schemas.schemas import CommentOut, CommentListOut

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=CommentListOut)
async def search_comments(
    q: str = Query(..., min_length=1),
    game_id: uuid.UUID | None = Query(None),
    platform: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    # Try semantic search with pgvector if embedding column has data
    # Fall back to full-text search
    try:
        from app.ai.embedding import generate_embedding
        from app.ai.router import get_ai_router
        router_obj = get_ai_router()
        embedding = await router_obj.embed(q)
        vector_str = "[" + ",".join(str(v) for v in embedding) + "]"

        query = (
            select(Comment, Game.name.label("game_name"))
            .join(Game)
            .where(Comment.embedding.isnot(None))
            .order_by(Comment.embedding.cosine_distance(vector_str))
        )
        count_q = (
            select(text("count(*)"))
            .select_from(Comment)
            .join(Game)
            .where(Comment.embedding.isnot(None))
        )
    except Exception:
        # Fallback to ILIKE search
        query = (
            select(Comment, Game.name.label("game_name"))
            .join(Game)
            .where(Comment.content.ilike(f"%{q}%"))
            .order_by(Comment.published_at.desc())
        )
        count_q = (
            select(text("count(*)"))
            .select_from(Comment)
            .join(Game)
            .where(Comment.content.ilike(f"%{q}%"))
        )

    if game_id:
        query = query.where(Comment.game_id == game_id)
        count_q = count_q.where(Comment.game_id == game_id)
    if platform:
        query = query.where(Comment.platform == platform)
        count_q = count_q.where(Comment.platform == platform)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).all()

    items = [
        CommentOut(
            id=r[0].id, game_id=r[0].game_id, platform=r[0].platform,
            source_type=r[0].source_type, source_url=r[0].source_url,
            author_name=r[0].author_name, content=r[0].content,
            content_lang=r[0].content_lang, published_at=r[0].published_at,
            sentiment=r[0].sentiment, sentiment_score=r[0].sentiment_score,
            category=r[0].category, summary=r[0].summary,
            is_duplicate=r[0].is_duplicate, game_name=r[1] if len(r) > 1 else None,
        )
        for r in rows
    ]
    return CommentListOut(total=total, items=items, page=page, page_size=page_size)
