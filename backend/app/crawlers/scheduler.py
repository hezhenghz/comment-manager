import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import get_settings
from app.crawlers.registry import get_crawler, available_platforms

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

# 并发锁：key = (game_id, platform) → 加锁时间。
# 解耦后 crawl 阶段不会再因 AI 卡死；TTL 用于兜底真·crawl 卡死
# （Discord/Steam API 挂、网络断），到期自动释放，防止前端按钮永远点不动。
_running: dict[tuple[str, str], datetime] = {}


def _lock_acquire(key: tuple[str, str]) -> bool:
    """尝试加锁，True=成功，False=已被持有且未过期。"""
    ttl = get_settings().crawler_lock_ttl_seconds
    held_at = _running.get(key)
    if held_at and (datetime.utcnow() - held_at).total_seconds() < ttl:
        return False
    _running[key] = datetime.utcnow()
    return True


def _lock_release(key: tuple[str, str]) -> None:
    _running.pop(key, None)


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

    解耦后本函数只跑 Phase 1（爬取入库），AI 分析由 app.ai.worker 独立后台任务处理。
    """
    key = (game_id, platform)
    if not _lock_acquire(key):
        logger.info(f"[scheduler] {platform}/{game_id} 已在运行（锁未过期），跳过本次触发")
        if job_id:
            await _mark_job_failed(job_id, "被并发锁跳过（同平台已在运行）")
        return
    try:
        await _run_crawl_inner(platform, game_app_id, game_id,
                               limit=limit, full=full, job_id=job_id)
    except Exception as e:
        import traceback
        logger.error(
            f"[scheduler] 未捕获异常 platform={platform} game_id={game_id}: "
            f"{e}\n{traceback.format_exc()}"
        )
        if job_id:
            await _mark_job_failed(job_id, f"未捕获异常: {e}")
    finally:
        _lock_release(key)


async def _run_crawl_inner(
    platform: str,
    game_app_id: str,
    game_id: str,
    limit: int | None = None,
    full: bool = False,
    job_id: str | None = None,
) -> None:
    """Phase 1：抓取 + 入库（评论默认 ai_status='pending'，由 AI worker 异步处理）。"""
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

    async with async_session() as db:
        result = await db.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        if not game:
            logger.warning(f"[scheduler] 未找到游戏 game_id={game_id}")
            if job_id:
                await _mark_job_failed(job_id, "未找到游戏")
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

        # 试爬模式：fetch_limit = 已存数量 + limit，从平台翻过已存评论再捞新的
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

        # ── 插入新评论（不运行 AI pipeline，留给 worker）─────────────
        new_count = 0
        for fc in fetched:
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

            # ai_status 走 ORM 默认值 "pending"，无需显式赋值
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
            new_count += 1

        # Phase 1 完成即标 done；AI 由独立 worker 异步处理
        job.new_count = new_count
        job.status = "done"
        job.phase = None
        job.finished_at = datetime.utcnow()

        await db.commit()
        logger.info(
            f"[scheduler] {platform}/{game_name} 爬取完成（已入库待 AI 分析）："
            f"新增 {new_count} 条，跳过 {len(fetched) - new_count} 条重复"
        )

    # 告警仍在 crawl 完成后触发（关键词告警不依赖 AI；阈值告警依赖 sentiment，
    # AI 没跑完时阈值告警会偏低，由 worker 跑完后下一次 _trigger_alerts 兜底）
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


async def cleanup_orphan_jobs() -> int:
    """启动时清理「幽灵 running job」。

    场景：后端进程被强杀（崩溃 / 用户 Ctrl+C / 端口冲突被 start-backend.ps1 杀掉），
    数据库里的 status='running' 的 job 永远不会被 mark done/failed，前端会一直显示
    「爬取中」。这个函数在每次后端启动时把它们标 failed，保证状态机干净。

    Returns:
        清理掉的 job 数量。
    """
    from app.database import async_session
    from app.models import CrawlJob, LineupFetchJob
    from sqlalchemy import select

    _ORPHAN_MSG = "后端进程重启时清理：上次运行未正常结束（可能被强杀或卡死）"
    try:
        cleaned = 0
        async with async_session() as db:
            # 评论爬虫 CrawlJob
            crawl_orphans = (await db.execute(select(CrawlJob).where(
                CrawlJob.status == "running",
                CrawlJob.finished_at.is_(None),
            ))).scalars().all()
            for job in crawl_orphans:
                job.status = "failed"
                job.phase = None
                job.finished_at = datetime.utcnow()
                job.error_msg = _ORPHAN_MSG
            # 阵容拉取 LineupFetchJob（无 phase 字段）
            lineup_orphans = (await db.execute(select(LineupFetchJob).where(
                LineupFetchJob.status == "running",
                LineupFetchJob.finished_at.is_(None),
            ))).scalars().all()
            for job in lineup_orphans:
                job.status = "failed"
                job.finished_at = datetime.utcnow()
                job.error_msg = _ORPHAN_MSG
            cleaned = len(crawl_orphans) + len(lineup_orphans)
            if cleaned:
                await db.commit()
                logger.warning(
                    f"[scheduler] 启动清理：CrawlJob {len(crawl_orphans)} 个、"
                    f"LineupFetchJob {len(lineup_orphans)} 个幽灵 running 标为 failed"
                )
            else:
                logger.info("[scheduler] 启动清理：无幽灵 running job")
            return cleaned
    except Exception as e:
        logger.error(f"[scheduler] cleanup_orphan_jobs 失败: {e}")
        return 0


def apply_lineup_schedule(enabled: bool, interval_hours: int) -> None:
    """按配置动态增删阵容拉取定时任务，立即生效（无需重启）。

    enabled=True：以 interval_hours 注册/替换 lineup_fetch（trigger 走默认 auto）。
    enabled=False：移除 lineup_fetch。
    """
    from app.lineup.fetcher import fetch_all_lineups

    if enabled:
        scheduler.add_job(
            fetch_all_lineups,
            "interval",
            hours=interval_hours,
            id="lineup_fetch",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"[scheduler] 阵容自动拉取已启用，间隔={interval_hours}h")
    else:
        if scheduler.get_job("lineup_fetch"):
            scheduler.remove_job("lineup_fetch")
        logger.info("[scheduler] 阵容自动拉取已禁用")


def start_scheduler(lineup_enabled: bool = True, lineup_interval_hours: int = 1) -> None:
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
    # 阵容拉取定时任务：按 DB 配置注册（独立于评论爬虫）
    apply_lineup_schedule(lineup_enabled, lineup_interval_hours)
    logger.info(
        f"[scheduler] 已启动，评论爬虫间隔={settings.crawler_interval_minutes}min，"
        f"阵容自动拉取={'开' if lineup_enabled else '关'}（间隔={lineup_interval_hours}h），"
        f"锁 TTL={settings.crawler_lock_ttl_seconds}s"
    )


async def cleanup_orphan_jobs() -> None:
    """清理上次进程残留的 running 状态 CrawlJob（标记为失败）。"""
    try:
        from app.database import async_session
        from app.models import CrawlJob
        from sqlalchemy import select, update
        from datetime import datetime
        async with async_session() as db:
            result = await db.execute(
                update(CrawlJob)
                .where(CrawlJob.status == "running")
                .values(status="failed", finished_at=datetime.utcnow(),
                        error_msg="进程重启，任务未完成")
            )
            await db.commit()
            if result.rowcount:
                logger.info(f"[scheduler] 清理 {result.rowcount} 个残留 running 任务")
    except Exception as e:
        logger.warning(f"[scheduler] cleanup_orphan_jobs 失败: {e}")


def _get_platform_app_id(game, platform: str) -> str | None:
    """根据平台返回该游戏对应的平台 ID。"""
    if platform in ("steam_store", "steam_hub", "xiaoheihe"):
        return game.steam_app_id or None
    elif platform == "discord":
        ids = game.discord_channel_ids
        return ",".join(ids) if ids else None
    elif platform == "qq":
        ids = game.qq_group_ids
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
