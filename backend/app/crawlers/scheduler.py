import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import get_settings
from app.crawlers.registry import get_crawler, available_platforms

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def run_crawl(platform: str, game_app_id: str, game_id: str) -> None:
    """Run a crawler and save results to DB."""
    from app.database import async_session
    from app.models import Comment, Game
    from app.ai.pipeline import run_pipeline
    from sqlalchemy import select

    crawler = get_crawler(platform)
    if not crawler:
        logger.error(f"No crawler for platform: {platform}")
        return

    async with async_session() as db:
        result = await db.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        if not game:
            return

        # Get the latest fetched comment's published_at as since
        latest_result = await db.execute(
            select(Comment.published_at)
            .where(Comment.game_id == game_id, Comment.platform == platform)
            .order_by(Comment.published_at.desc())
            .limit(1)
        )
        since = latest_result.scalar_one_or_none()

        try:
            fetched = await crawler.fetch(game.steam_app_id, since)
        except Exception as e:
            logger.error(f"Crawler {platform} failed for game {game.name}: {e}")
            return

        for fc in fetched:
            comment = Comment(
                game_id=game.id,
                platform=fc.platform,
                source_type=fc.source_type,
                source_url=fc.source_url,
                author_name=fc.author_name,
                content=fc.content,
                published_at=fc.published_at or datetime.utcnow(),
                fetched_at=datetime.utcnow(),
                thumbs_up=fc.thumbs_up,
                thumbs_down=fc.thumbs_down,
                raw_json=fc.raw_json,
            )
            db.add(comment)
            await db.flush()
            try:
                await run_pipeline(comment, db)
            except Exception as e:
                logger.warning(f"AI pipeline failed for comment {comment.id}: {e}")

        await db.commit()
        logger.info(f"Saved {len(fetched)} comments from {platform} for {game.name}")


def start_scheduler() -> None:
    settings = get_settings()
    from app.database import get_db
    # Register a catch-all job for all enabled games & platforms
    scheduler.add_job(
        run_all_crawlers,
        "interval",
        minutes=settings.crawler_interval_minutes,
        id="crawl_all",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started, interval={settings.crawler_interval_minutes}min")


async def run_all_crawlers() -> None:
    from app.database import async_session
    from app.models import Game
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(Game))
        games = result.scalars().all()

    for game in games:
        for platform in available_platforms():
            await run_crawl(platform, game.steam_app_id or "", str(game.id))
