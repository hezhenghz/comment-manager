import asyncio
import logging
import uuid
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import get_settings
from app.crawlers.registry import get_crawler, available_platforms

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

# 并发锁：key = (game_id, platform)，防止同一游戏同一平台重复运行
_running: set[tuple[str, str]] = set()


async def run_crawl(
    platform: str,
    game_app_id: str,
    game_id: str,
    limit: int | None = None,
    full: bool = False,
    job_id: str | None = None,
) -> None:
    """入口：捕获所有异常，保证任务不会让调度器崩溃。
    limit!=None 时为试爬模式；full=True 时强制全量（忽略 since）。
    job_id 不为 None 时接管已预建的 CrawlJob（手动触发路径）。
    """
    key = (game_id, platform)
    if key in _running:
        logger.info(f"[scheduler] {platform}/{game_id} 已在运行，跳过本次触发")
        if job_id:
            await _mark_job_failed(job_id, "被并发锁跳过（同平台已在运行）")
        return
    _running.add(key)
    try:
        await _run_crawl_inner(platform, game_app_id, game_id,
                               limit=limit, full=full, job_id=job_id)
    except Exception as e:
        import traceback
        logger.error(
            f"[scheduler] 未捕获异常 platform={platform} game_id={game_id}: "
            f"{e}\n{traceback.format_exc()}"
        )
    finally:
        _running.discard(key)


async def _run_crawl_inner(
    platform: str,
    game_app_id: str,
    game_id: str,
    limit: int | None = None,
    full: bool = False,
    job_id: str | None = None,
) -> None:
    from app.database import async_session
    from app.models import Comment, Game, CrawlJob
    from sqlalchemy import select

    if not game_app_id:
        logger.info(f"[scheduler] game_id={game_id} platform={platform} 没有配置平台 ID，跳过")
        if job_id:
            await _mark_job_failed(job_id, "没有配置平台 ID")
        return

    crawler = get_crawler(platform)
    if not crawler:
        logger.warning(f"[scheduler] 未找到爬虫: {platform}")
        if job_id:
            await _mark_job_failed(job_id, f"未找到爬虫: {platform}")
        return

    # ── Phase 1：爬取阶段 ──────────────────────────────────────────────────────
    new_comment_ids: list[uuid.UUID] = []
    job_uuid: uuid.UUID | None = None
    game_name: str = ""

    try:
        async with async_session() as db:
            result = await db.execute(select(Game).where(Game.id == game_id))
            game = result.scalar_one_or_none()
            if not game:
                logger.warning(f"[scheduler] 未找到游戏 game_id={game_id}")
                return
            game_name = game.name

            # 接管预建 Job 或新建 Job
            if job_id:
                job = await db.get(CrawlJob, uuid.UUID(job_id))
                if not job:
                    logger.warning(f"[scheduler] 预建 job 不存在 job_id={job_id}")
                    return
                job.phase = "crawl"
                job.status = "running"
            else:
                job = CrawlJob(game_id=game.id, platform=platform,
                               status="running", phase="crawl")
                db.add(job)
            await db.flush()
            job_uuid = job.id

            # 增量起点：full=True 时忽略，由 DB 唯一索引去重
            since: datetime | None = None
            if not full:
                latest_result = await db.execute(
                    select(Comment.published_at)
                    .where(Comment.game_id == game_id, Comment.platform == platform)
                    .order_by(Comment.published_at.desc())
                    .limit(1)
                )
                since = latest_result.scalar_one_or_none()

            mode = f"试爬(limit={limit})" if limit else "全量"
            logger.info(f"[scheduler] {platform}/{game.name} 开始{mode}抓取，since={since}")

            # 试爬模式：fetch_limit = 已存数量 + limit
            # 从 Steam 翻过所有已存评论，再捞 limit 条新的
            # 全量模式：不限制（limit=None）
            if limit:
                from sqlalchemy import func
                count_q = select(func.count(Comment.id)).where(
                    Comment.game_id == game.id,
                    Comment.platform == platform,
                )
                existing_count = (await db.execute(count_q)).scalar() or 0
                fetch_limit = existing_count + limit
            else:
                fetch_limit = None
            try:
                fetched = await crawler.fetch(game_app_id, since, limit=fetch_limit)
            except Exception as e:
                logger.error(f"[scheduler] 爬虫 {platform} 抓取失败 game={game.name}: {e}")
                job.status = "failed"
                job.phase = None
                job.error_msg = str(e)
                job.finished_at = datetime.utcnow()
                await db.commit()
                return

            # ── 批量去重 ────────────────────────────────────────────────────
            external_ids = [fc.external_id for fc in fetched if fc.external_id]
            existing_ids: set[str] = set()
            if external_ids:
                exist_result = await db.execute(
                    select(Comment.external_id).where(
                        Comment.game_id == game.id,
                        Comment.platform == platform,
                        Comment.external_id.in_(external_ids),
                    )
                )
                existing_ids = set(exist_result.scalars())

            # ── 插入新评论（不运行 AI pipeline）────────────────────────────
            new_count = 0
            for fc in fetched:
                # 试爬：新增数已达目标，停止（多抓的其余部分丢弃）
                if limit and new_count >= limit:
                    break
                if fc.external_id:
                    if fc.external_id in existing_ids:
                        continue
                else:
                    dup = await db.execute(
                        select(Comment.id).where(
                            Comment.game_id == game.id,
                            Comment.platform == fc.platform,
                            Comment.author_name == fc.author_name,
                            Comment.content == fc.content,
                        ).limit(1)
                    )
                    if dup.scalar_one_or_none() is not None:
                        continue

                comment = Comment(
                    game_id=game.id,
                    platform=fc.platform,
                    source_type=fc.source_type,
                    source_url=fc.source_url,
                    external_id=fc.external_id,
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
                new_comment_ids.append(comment.id)
                new_count += 1

            # 阶段一完成：更新 job 状态
            job.new_count = new_count
            job.ai_total = new_count
            job.ai_done = 0
            if new_count > 0:
                job.phase = "ai"
            else:
                # 无新增，直接完成
                job.status = "done"
                job.phase = None
                job.finished_at = datetime.utcnow()

            await db.commit()
            logger.info(
                f"[scheduler] {platform}/{game_name} 爬取完成："
                f"新增 {new_count} 条，跳过 {len(fetched) - new_count} 条重复"
            )

    except Exception as e:
        import traceback
        logger.error(f"[scheduler] Phase1 异常 platform={platform} game_id={game_id}: "
                     f"{e}\n{traceback.format_exc()}")
        if job_uuid:
            await _mark_job_failed(str(job_uuid), str(e))
        return

    # 无新增则跳过 Phase 2
    if not new_comment_ids:
        await _trigger_alerts(game_id)
        return

    # ── Phase 2：AI 分析阶段 ───────────────────────────────────────────────────
    try:
        from app.ai.pipeline import run_pipeline
        from app.database import async_session
        from app.models import Comment, CrawlJob

        async with async_session() as db2:
            job2 = await db2.get(CrawlJob, job_uuid)
            total = len(new_comment_ids)

            for i, cid in enumerate(new_comment_ids):
                comment = await db2.get(Comment, cid)
                if comment:
                    try:
                        await run_pipeline(comment, db2)
                    except Exception as e:
                        logger.warning(f"[scheduler] AI pipeline 失败 comment={cid}: {e}")

                job2.ai_done = i + 1
                # 每 10 条提交一次（或最后一条），让前端能看到进度
                if (i + 1) % 10 == 0 or (i + 1) == total:
                    await db2.commit()

            job2.status = "done"
            job2.phase = None
            job2.finished_at = datetime.utcnow()
            await db2.commit()

            logger.info(f"[scheduler] {platform}/{game_name} AI 分析完成：共 {total} 条")

    except Exception as e:
        import traceback
        logger.error(f"[scheduler] Phase2 异常 platform={platform}: "
                     f"{e}\n{traceback.format_exc()}")
        await _mark_job_failed(str(job_uuid), f"AI 分析阶段失败: {e}")
        return

    await _trigger_alerts(game_id)


async def _mark_job_failed(job_id: str, error_msg: str) -> None:
    """将 Job 标为 failed。"""
    try:
        from app.database import async_session
        from app.models import CrawlJob
        async with async_session() as db:
            job = await db.get(CrawlJob, uuid.UUID(job_id))
            if job:
                job.status = "failed"
                job.error_msg = error_msg
                job.phase = None
                job.finished_at = datetime.utcnow()
                await db.commit()
    except Exception as e:
        logger.warning(f"[scheduler] _mark_job_failed 失败: {e}")


async def _trigger_alerts(game_id: str) -> None:
    """检查告警规则，插入匹配的 alert_events。"""
    from app.models import AlertRule, AlertEvent, Comment
    from app.database import async_session
    from sqlalchemy import select, func, or_
    from datetime import timedelta

    try:
        async with async_session() as db:
            result = await db.execute(
                select(AlertRule).where(
                    AlertRule.game_id == game_id,
                    AlertRule.enabled == True,  # noqa: E712
                )
            )
            rules = result.scalars().all()
            if not rules:
                return

            for rule in rules:
                if rule.rule_type == "keyword" and rule.keywords:
                    keyword_filters = [Comment.content.ilike(f"%{kw}%") for kw in rule.keywords]
                    recent_cutoff = datetime.utcnow() - timedelta(hours=1)
                    q = select(Comment.id).where(
                        Comment.game_id == game_id,
                        Comment.fetched_at >= recent_cutoff,
                        or_(*keyword_filters),
                    )
                    matched = (await db.execute(q)).scalars().all()
                    for comment_id in matched:
                        existing = await db.execute(
                            select(AlertEvent.id).where(
                                AlertEvent.rule_id == rule.id,
                                AlertEvent.comment_id == comment_id,
                            ).limit(1)
                        )
                        if existing.scalar_one_or_none() is None:
                            db.add(AlertEvent(rule_id=rule.id, comment_id=comment_id))
                            rule.last_triggered_at = datetime.utcnow()

                elif rule.rule_type == "threshold" and rule.threshold_value is not None:
                    if rule.last_triggered_at and (
                        datetime.utcnow() - rule.last_triggered_at
                    ).total_seconds() < 3600:
                        continue
                    day_start = datetime.utcnow() - timedelta(hours=24)
                    total_q = select(func.count(Comment.id)).where(
                        Comment.game_id == game_id,
                        Comment.published_at >= day_start,
                    )
                    neg_q = total_q.where(Comment.sentiment == "negative")
                    total = (await db.execute(total_q)).scalar() or 0
                    negative = (await db.execute(neg_q)).scalar() or 0
                    if total > 0:
                        neg_ratio = negative / total * 100
                        if neg_ratio >= rule.threshold_value:
                            db.add(AlertEvent(rule_id=rule.id, comment_id=None))
                            rule.last_triggered_at = datetime.utcnow()
                            logger.info(
                                f"[scheduler] 阈值告警触发 game={game_id} "
                                f"负面率={neg_ratio:.1f}% >= {rule.threshold_value}%"
                            )

            await db.commit()
    except Exception as e:
        logger.warning(f"[scheduler] _trigger_alerts 失败: {e}")


def start_scheduler() -> None:
    settings = get_settings()
    scheduler.add_job(
        run_all_crawlers,
        "interval",
        minutes=settings.crawler_interval_minutes,
        id="crawl_all",
        replace_existing=True,
        max_instances=1,   # 防止调度器自身重叠执行
    )
    scheduler.start()
    logger.info(f"[scheduler] 已启动，间隔={settings.crawler_interval_minutes}min")


def _get_platform_app_id(game, platform: str) -> str | None:
    """根据平台返回该游戏对应的平台 ID。"""
    if platform in ("steam_store", "steam_hub", "xiaoheihe"):
        return game.steam_app_id or None
    elif platform == "discord":
        ids = game.discord_channel_ids
        return ",".join(ids) if ids else None
    return None


async def run_all_crawlers() -> None:
    from app.database import async_session
    from app.models import Game
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(Game))
        games = result.scalars().all()

    for game in games:
        for platform in available_platforms():
            pid = _get_platform_app_id(game, platform)
            if not pid:
                continue
            await run_crawl(platform, pid, str(game.id))
