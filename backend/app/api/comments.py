import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, delete
from sqlalchemy.orm import selectinload
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
    content_lang: str | None = Query(None),
    recommended: bool | None = Query(None),  # True=推荐, False=不推荐
    q: str | None = Query(None),             # 关键词全文搜索（ILIKE）
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Comment).options(selectinload(Comment.game))
    count_q = select(func.count(Comment.id))

    filters = []
    if game_id:
        filters.append(Comment.game_id == game_id)
    if platform:
        filters.append(Comment.platform == platform)
    if sentiment:
        filters.append(Comment.sentiment == sentiment)
    if category:
        filters.append(Comment.category == category)
    if content_lang:
        filters.append(Comment.content_lang == content_lang)
    if recommended is True:
        filters.append(Comment.thumbs_up == 1)
    elif recommended is False:
        filters.append(Comment.thumbs_up == 0)
    if q:
        filters.append(Comment.content.ilike(f"%{q}%"))

    for f in filters:
        query = query.where(f)
        count_q = count_q.where(f)

    total = (await db.execute(count_q)).scalar() or 0
    query = query.order_by(desc(Comment.published_at)).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    items = [
        CommentOut(
            id=c.id, game_id=c.game_id, platform=c.platform, source_type=c.source_type,
            source_url=c.source_url, author_name=c.author_name, content=c.content,
            content_lang=c.content_lang, published_at=c.published_at, sentiment=c.sentiment,
            sentiment_score=c.sentiment_score, category=c.category, summary=c.summary,
            translation=c.translation, is_duplicate=c.is_duplicate,
            game_name=c.game.name if c.game else None, thumbs_up=c.thumbs_up,
        )
        for c in rows
    ]
    return CommentListOut(total=total, items=items, page=page, page_size=page_size)


@router.post("/clear", status_code=204)
async def clear_comments(
    game_id: uuid.UUID = Query(...),
    platform: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    await db.execute(
        delete(Comment)
        .where(Comment.game_id == game_id, Comment.platform == platform)
        .execution_options(synchronize_session=False)
    )
    await db.commit()


@router.get("/{comment_id}", response_model=CommentOut)
async def get_comment(comment_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Comment).options(selectinload(Comment.game)).where(Comment.id == comment_id))
    c = result.scalar_one_or_none()
    if c is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")
    return CommentOut(
        id=c.id, game_id=c.game_id, platform=c.platform, source_type=c.source_type,
        source_url=c.source_url, author_name=c.author_name, content=c.content,
        content_lang=c.content_lang, published_at=c.published_at, sentiment=c.sentiment,
        sentiment_score=c.sentiment_score, category=c.category, summary=c.summary,
        translation=c.translation, is_duplicate=c.is_duplicate,
        game_name=c.game.name if c.game else None, thumbs_up=c.thumbs_up,
    )


@router.post("/{comment_id}/translate")
async def translate_comment(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from fastapi import HTTPException
    from app.ai.translate import translate_to_chinese

    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    c = result.scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Not found")

    # 优先返回已存储的翻译
    if c.translation:
        return {"translated": c.translation}

    try:
        translated = await translate_to_chinese(c.content)
        c.translation = translated
        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"translated": translated}
