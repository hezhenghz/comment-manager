"""
BUG上报（Dump 系统）同步调度
- sync_bug_reports()         : 执行一次增量同步
- start_bug_sync_scheduler() : 注册 APScheduler 定时任务
"""

import logging
from datetime import datetime, timedelta

from app.config import get_settings

logger = logging.getLogger(__name__)

# 上次同步的元信息（内存缓存，重启后归零）
_last_sync_at: datetime | None = None
_last_sync_count: int = 0
_is_syncing: bool = False


def get_sync_status() -> dict:
    return {
        "last_sync_at":    _last_sync_at.isoformat() if _last_sync_at else None,
        "last_sync_count": _last_sync_count,
        "is_syncing":      _is_syncing,
    }


async def sync_bug_reports() -> dict:
    """
    增量同步 Dump 上报：
    - 使用 since=_last_sync_at（初次同步抓取最近 7 天）
    - 新记录 INSERT，已存在的跳过（dump 记录不会变化）
    返回 {"new": N, "updated": M, "error": None|str}
    """
    global _last_sync_at, _last_sync_count, _is_syncing

    if _is_syncing:
        return {"new": 0, "updated": 0, "error": "同步进行中，请稍后"}

    _is_syncing = True
    new_count = 0
    error_msg = None

    from app.crawlers.zentao import ZenTaoCrawler
    crawler = ZenTaoCrawler()

    try:
        # 认证
        ok = await crawler.login()
        if not ok:
            error_msg = "认证失败，请检查 ZENTAO_COOKIE 或 ZENTAO_USERNAME/PASSWORD"
            logger.error(f"[zentao-sync] {error_msg}")
            return {"new": 0, "updated": 0, "error": error_msg}

        # 确定增量起始时间
        since = _last_sync_at
        if since is None:
            # 初次同步：抓取最近 7 天
            since = datetime.utcnow() - timedelta(days=7)
            logger.info(f"[zentao-sync] 初次同步，起始时间: {since.date()}")
        else:
            logger.info(f"[zentao-sync] 增量同步，起始时间: {since.date()}")

        # 抓取数据（crawler 内部按天翻页）
        bugs = await crawler.fetch_bugs(since=since)
        logger.info(f"[zentao-sync] 共抓取 {len(bugs)} 条记录")

        if bugs:
            from app.database import async_session
            from app.models import BugReport
            from sqlalchemy import select

            async with async_session() as db:
                for bug in bugs:
                    eid = bug.get("external_id", "")
                    if not eid:
                        continue

                    # 检查是否已存在（dump 记录不变，只 INSERT 新记录）
                    existing = (await db.execute(
                        select(BugReport.id).where(BugReport.external_id == eid)
                    )).scalar_one_or_none()

                    if existing is None:
                        db.add(BugReport(
                            external_id  = eid,
                            title        = bug["title"],
                            description  = bug["description"],
                            status       = bug["status"],
                            priority     = bug["priority"],
                            severity     = bug["severity"],
                            module       = bug["module"],
                            submitter    = bug["submitter"],
                            assignee     = bug["assignee"],
                            submitted_at = bug["submitted_at"],
                            resolved_at  = bug["resolved_at"],
                            closed_at    = bug["closed_at"],
                            source_url   = bug["source_url"],
                            product      = bug["product"],
                            fetched_at   = datetime.utcnow(),
                            raw_json     = bug["raw_json"],
                        ))
                        new_count += 1

                await db.commit()

        _last_sync_at = datetime.utcnow()
        _last_sync_count = new_count
        logger.info(f"[zentao-sync] 完成：新增 {new_count} 条")
        return {"new": new_count, "updated": 0, "error": None}

    except Exception as e:
        import traceback
        error_msg = str(e)
        logger.error(f"[zentao-sync] 异常: {e}\n{traceback.format_exc()}")
        return {"new": 0, "updated": 0, "error": error_msg}
    finally:
        _is_syncing = False
        await crawler.close()


def start_bug_sync_scheduler():
    """将 BUG 同步任务注册到主 APScheduler 实例。"""
    from app.crawlers.scheduler import scheduler

    interval = get_settings().zentao_sync_interval
    if interval <= 0:
        logger.info("[zentao-sync] ZENTAO_SYNC_INTERVAL<=0，不启动定时同步")
        return

    scheduler.add_job(
        _sync_wrapper,
        trigger="interval",
        minutes=interval,
        id="bug_report_sync",
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"[zentao-sync] 已注册定时同步，间隔={interval}分钟")


async def _sync_wrapper():
    """APScheduler 调用的包装函数，捕获所有异常。"""
    try:
        await sync_bug_reports()
    except Exception as e:
        logger.error(f"[zentao-sync] 定时任务异常: {e}")
