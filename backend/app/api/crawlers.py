import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Game, User, CrawlJob, Comment
from app.auth import get_current_user
from app.crawlers.registry import get_crawler, available_platforms
from app.crawlers.scheduler import run_crawl, _get_platform_app_id

router = APIRouter(prefix="/api/crawlers", tags=["crawlers"])


@router.get("/qq/group-names")
async def get_qq_group_names(
    game_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """返回该游戏所有 QQ 群的真实群名 {group_id: group_name}，从 NapCat 实时查询。"""
    from app.config import get_settings
    import httpx

    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if not game or not game.qq_group_ids:
        return {}

    settings = get_settings()
    if not settings.qq_napcat_url:
        return {}

    names: dict[str, str] = {}
    headers = {}
    if settings.qq_access_token:
        headers["Authorization"] = f"Bearer {settings.qq_access_token}"

    async with httpx.AsyncClient(
        base_url=settings.qq_napcat_url.rstrip("/"), headers=headers, timeout=10
    ) as client:
        for gid in game.qq_group_ids:
            try:
                r = await client.post("/get_group_info", json={"group_id": int(gid)})
                data = (r.json().get("data") or {})
                name = data.get("group_name") or gid
                names[gid] = name
            except Exception:
                names[gid] = gid  # 查询失败时降级为群 ID

    return names


@router.get("/schedule")
async def get_schedule(_: User = Depends(get_current_user)):
    from app.crawlers.scheduler import scheduler
    from app.config import get_settings
    job = scheduler.get_job("crawl_all")
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {
        "enabled": job is not None,
        "interval_minutes": get_settings().crawler_interval_minutes,
        "next_run_time": next_run,
    }


@router.post("/{platform}/run")
async def trigger_crawl(
    platform: str,
    game_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if platform not in available_platforms():
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    game_uuid = uuid.UUID(game_id)
    result = await db.execute(select(Game).where(Game.id == game_uuid))
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    # 预建 CrawlJob 并提交，保证后台任务拿到真实 job_id，不受 APScheduler 干扰
    job = CrawlJob(game_id=game.id, platform=platform, status="running", phase="crawl")
    db.add(job)
    await db.commit()

    platform_id = _get_platform_app_id(game, platform) or ""
    asyncio.create_task(
        run_crawl(platform, platform_id, str(game.id), full=True, job_id=str(job.id))
    )
    return {"status": "ok", "platform": platform, "game_id": game_id, "job_id": str(job.id)}


@router.post("/{platform}/trial")
async def trigger_trial_crawl(
    platform: str,
    game_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """试爬：只抓 5 条，验证爬虫机制是否正常，结果存库（有去重）。"""
    if platform not in available_platforms():
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    game_uuid = uuid.UUID(game_id)
    result = await db.execute(select(Game).where(Game.id == game_uuid))
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    # 预建 CrawlJob
    job = CrawlJob(game_id=game.id, platform=platform, status="running", phase="crawl")
    db.add(job)
    await db.commit()

    platform_id = _get_platform_app_id(game, platform) or ""
    asyncio.create_task(
        run_crawl(platform, platform_id, str(game.id), limit=5, full=True, job_id=str(job.id))
    )
    return {"status": "ok", "platform": platform, "game_id": game_id, "mode": "trial", "job_id": str(job.id)}


@router.get("/jobs/{job_id}")
async def get_job_by_id(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """按 job_id 轮询单个爬取任务的状态（含两阶段进度）。"""
    result = await db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id":          str(job.id),
        "status":      job.status,    # running | done | failed
        "phase":       job.phase,     # crawl | ai | None
        "new_count":   job.new_count,
        "ai_total":    job.ai_total,
        "ai_done":     job.ai_done,
        "started_at":  job.started_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error_msg":   job.error_msg,
    }


@router.get("/jobs")
async def list_jobs(
    game_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return latest crawl job per platform + total comment count per platform."""
    platforms = available_platforms()
    result = []

    for platform in platforms:
        # Latest job for this game+platform
        job_q = (
            select(CrawlJob)
            .where(CrawlJob.game_id == game_id, CrawlJob.platform == platform)
            .order_by(CrawlJob.started_at.desc())
            .limit(1)
        )
        job = (await db.execute(job_q)).scalar_one_or_none()

        # Total comment count
        count_q = select(func.count(Comment.id)).where(
            Comment.game_id == game_id,
            Comment.platform == platform,
        )
        total = (await db.execute(count_q)).scalar() or 0

        result.append({
            "platform": platform,
            "total_comments": total,
            "job": {
                "id":          str(job.id) if job else None,
                "status":      job.status if job else None,
                "phase":       job.phase if job else None,
                "started_at":  job.started_at.isoformat() if job else None,
                "finished_at": job.finished_at.isoformat() if job and job.finished_at else None,
                "new_count":   job.new_count if job else 0,
                "ai_total":    job.ai_total if job else 0,
                "ai_done":     job.ai_done if job else 0,
                "error_msg":   job.error_msg if job else None,
            } if job else None,
        })

    return result
