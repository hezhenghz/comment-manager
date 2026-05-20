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
    today_q = base.where(Comment.published_at >= today_start)
    today_new = (await db.execute(today_q)).scalar() or 0

    bug_q = base.where(Comment.category == "bug")
    bug_count = (await db.execute(bug_q)).scalar() or 0

    today_bug_q = bug_q.where(Comment.published_at >= today_start)
    today_bug_count = (await db.execute(today_bug_q)).scalar() or 0

    suggestion_q = base.where(Comment.category == "suggestion")
    suggestion_count = (await db.execute(suggestion_q)).scalar() or 0

    today_suggestion_q = suggestion_q.where(Comment.published_at >= today_start)
    today_suggestion_count = (await db.execute(today_suggestion_q)).scalar() or 0

    steam_base = select(func.count(Comment.id)).where(
        Comment.platform == "steam_store",
        Comment.thumbs_up.isnot(None),
    )
    if game_id:
        steam_base = steam_base.where(Comment.game_id == game_id)
    steam_total = (await db.execute(steam_base)).scalar() or 0

    if steam_total > 0:
        negative_q = steam_base.where(Comment.thumbs_up == 0)
        negative_count = (await db.execute(negative_q)).scalar() or 0
        negative_review_rate = round(negative_count / steam_total * 100, 1)
    else:
        negative_review_rate = None

    return DashboardStats(
        total_comments=total,
        today_new=today_new,
        bug_count=bug_count,
        today_bug_count=today_bug_count,
        suggestion_count=suggestion_count,
        today_suggestion_count=today_suggestion_count,
        negative_review_rate=negative_review_rate,
    )


@router.get("/trends", response_model=list[TrendPoint])
async def get_trends(
    days: int = Query(30, ge=1, le=90),
    mode: str = Query("cumulative", regex="^(cumulative|daily)$"),
    game_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    today = datetime.utcnow().date()
    points = []

    if mode == "cumulative":
        # For each day: health score of ALL comments published up to that day
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            d_end = datetime(d.year, d.month, d.day, 23, 59, 59, 999999)
            q = select(Comment.sentiment).where(Comment.published_at <= d_end)
            if game_id:
                q = q.where(Comment.game_id == game_id)
            sentiments = (await db.execute(q)).scalars().all()
            total = len(sentiments)
            positive = sum(1 for s in sentiments if s == "positive")
            neutral  = sum(1 for s in sentiments if s == "neutral")
            health = round((positive + neutral * 0.5) / total * 100, 1) if total > 0 else 0.0
            points.append(TrendPoint(date=d.isoformat(), count=total, health_score=health))
    else:
        # daily: health score of comments published on that specific day
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            d_start = datetime(d.year, d.month, d.day, 0, 0, 0)
            d_end   = datetime(d.year, d.month, d.day, 23, 59, 59, 999999)
            q = select(Comment.sentiment).where(
                Comment.published_at >= d_start, Comment.published_at <= d_end
            )
            if game_id:
                q = q.where(Comment.game_id == game_id)
            sentiments = (await db.execute(q)).scalars().all()
            total = len(sentiments)
            positive = sum(1 for s in sentiments if s == "positive")
            neutral  = sum(1 for s in sentiments if s == "neutral")
            health = round((positive + neutral * 0.5) / total * 100, 1) if total > 0 else 0.0
            points.append(TrendPoint(date=d.isoformat(), count=total, health_score=health))

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
    from collections import Counter, defaultdict
    import jieba
    from app.models import Game

    # Fetch comments (content + sentiment)
    q = select(Comment.content, Comment.sentiment).where(Comment.content.isnot(None))
    if game_id:
        q = q.where(Comment.game_id == game_id)
    rows = (await db.execute(q)).all()

    # Built-in stopwords
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
        "游戏", "玩家", "一个", "感觉", "觉得", "真的", "非常", "非常好",
    }

    # Merge per-game custom stopwords
    if game_id:
        game_row = await db.execute(select(Game).where(Game.id == game_id))
        game_obj = game_row.scalar_one_or_none()
        if game_obj and game_obj.stopwords:
            stopwords |= {w.lower() for w in game_obj.stopwords}

    word_counts: Counter = Counter()
    word_sentiment: dict[str, list[int]] = defaultdict(list)  # word -> [+1/0/-1 per occurrence]

    for content, sentiment in rows:
        text = re.sub(r"[^\w\s一-鿿]", " ", content)
        words = list(jieba.cut(text))
        seen = set()
        for w in words:
            w = w.strip().lower()
            if len(w) >= 2 and w not in stopwords:
                word_counts[w] += 1
                if w not in seen:
                    seen.add(w)
                    if sentiment == "positive":
                        word_sentiment[w].append(1)
                    elif sentiment == "negative":
                        word_sentiment[w].append(-1)
                    else:
                        word_sentiment[w].append(0)

    result = []
    for w, c in word_counts.most_common(limit):
        scores = word_sentiment.get(w, [])
        sentiment_score = round(sum(scores) / len(scores), 3) if scores else 0.0
        result.append(WordCloudItem(word=w, weight=c, sentiment_score=sentiment_score))
    return result
