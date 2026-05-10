import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Comment, Game, User
from app.auth import get_current_user
from app.schemas.schemas import DashboardStats, TrendPoint, CategoryDist, SourceDist, WordCloudItem

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    game_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    base = select(func.count(Comment.id)).select_from(Comment)
    if game_id:
        base = base.where(Comment.game_id == game_id)

    total = (await db.execute(base)).scalar() or 0

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_q = base.where(Comment.fetched_at >= today_start)
    today_new = (await db.execute(today_q)).scalar() or 0

    bug_q = base.where(Comment.category == "bug")
    bug_count = (await db.execute(bug_q)).scalar() or 0

    neg_q = base.where(Comment.sentiment == "negative")
    neg_count = (await db.execute(neg_q)).scalar() or 0
    negative_ratio = round(neg_count / total * 100, 1) if total > 0 else 0

    return DashboardStats(total_comments=total, today_new=today_new, bug_count=bug_count, negative_ratio=negative_ratio)


@router.get("/trends", response_model=list[TrendPoint])
async def get_trends(
    days: int = Query(7, ge=1, le=90),
    game_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    points = []
    for i in range(days - 1, -1, -1):
        d = datetime.utcnow().date() - timedelta(days=i)
        base = select(Comment).where(func.date(Comment.published_at) == d.isoformat())
        if game_id:
            base = base.where(Comment.game_id == game_id)
        rows = (await db.execute(base)).scalars().all()
        positive = sum(1 for r in rows if r.sentiment == "positive")
        negative = sum(1 for r in rows if r.sentiment == "negative")
        neutral = sum(1 for r in rows if r.sentiment == "neutral")
        points.append(TrendPoint(date=d.isoformat(), count=len(rows), positive=positive, negative=negative, neutral=neutral))
    return points


@router.get("/categories", response_model=list[CategoryDist])
async def get_categories(
    game_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(Comment.category, func.count()).select_from(Comment).where(Comment.category.isnot(None))
    if game_id:
        q = q.where(Comment.game_id == game_id)
    q = q.group_by(Comment.category).order_by(func.count().desc())
    rows = (await db.execute(q)).all()
    return [CategoryDist(category=r[0], count=r[1]) for r in rows]


@router.get("/sources", response_model=list[SourceDist])
async def get_sources(
    game_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(Comment.platform, func.count()).select_from(Comment)
    if game_id:
        q = q.where(Comment.game_id == game_id)
    q = q.group_by(Comment.platform)
    rows = (await db.execute(q)).all()
    return [SourceDist(platform=r[0], count=r[1]) for r in rows]


@router.get("/wordcloud", response_model=list[WordCloudItem])
async def get_wordcloud(
    game_id: uuid.UUID | None = Query(None),
    limit: int = Query(100, ge=10, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    import re
    from collections import Counter
    import jieba

    q = select(Comment.content).where(Comment.content.isnot(None))
    if game_id:
        q = q.where(Comment.game_id == game_id)
    rows = (await db.execute(q)).scalars().all()

    stopwords = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "shall", "you", "your",
        "i", "me", "my", "we", "our", "it", "its", "they", "them", "their",
        "this", "that", "these", "those", "not", "no", "nor", "so", "if",
        "then", "than", "too", "very", "just", "about", "also", "game",
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
        "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
        "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
        "什么", "怎么", "如何", "为什么", "还是", "可以", "这个", "那个",
        "还", "被", "把", "又", "能", "让", "给", "但", "却", "只", "吗",
        "吧", "呢", "啊", "哦", "嗯", "哈", "呀", "么", "没", "所", "才",
    }

    all_words: list[str] = []
    for content in rows:
        text = re.sub(r"[^\w\s一-鿿]", " ", content)
        words = jieba.cut(text)
        for w in words:
            w = w.strip().lower()
            if len(w) >= 2 and w not in stopwords:
                all_words.append(w)

    counter = Counter(all_words)
    return [WordCloudItem(word=w, weight=c) for w, c in counter.most_common(limit)]
