"""
游戏更新公告 API
前缀：/api/announcements

GET  /api/announcements            列表（分页 + 按游戏 + 关键词）
GET  /api/announcements/count      当前游戏公告总数（供侧边栏）
GET  /api/announcements/stats      统计（总数 + 今日新增）
GET  /api/announcements/sync/status 同步状态
POST /api/announcements/sync       手动触发同步（仅管理员）
"""
import asyncio
import uuid
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import GameAnnouncement, User
from app.auth import get_current_user

router = APIRouter(prefix="/api/announcements", tags=["announcements"])


def _to_dict(a: GameAnnouncement) -> dict:
    return {
        "id":            str(a.id),
        "game_id":       str(a.game_id),
        "external_id":   a.external_id,
        "title":         a.title,
        "title_zh":      a.title_zh or a.title,
        "body_zh":       a.body_zh,
        "is_translated": a.is_translated,
        "lang":          a.lang,
        "published_at":  a.published_at.isoformat() + "Z" if a.published_at else None,
        "source_url":    a.source_url,
    }


@router.get("")
async def list_announcements(
    game_id:  Optional[uuid.UUID] = Query(None),
    page:     int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    keyword:  Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(GameAnnouncement)
    if game_id:
        q = q.where(GameAnnouncement.game_id == game_id)
    if keyword:
        q = q.where(GameAnnouncement.title_zh.ilike(f"%{keyword}%"))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = (q.order_by(desc(GameAnnouncement.published_at))
          .offset((page - 1) * per_page).limit(per_page))
    rows = (await db.execute(q)).scalars().all()

    return {
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "items":    [_to_dict(r) for r in rows],
    }


@router.get("/count")
async def announcement_count(
    game_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """返回公告总数（按 game_id 过滤），供侧边栏导航计数。"""
    q = select(func.count(GameAnnouncement.id))
    if game_id:
        q = q.where(GameAnnouncement.game_id == game_id)
    return {"count": (await db.execute(q)).scalar() or 0}


@router.get("/stats")
async def announcement_stats(
    game_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    base = select(func.count(GameAnnouncement.id))
    if game_id:
        base = base.where(GameAnnouncement.game_id == game_id)
    total = (await db.execute(base)).scalar() or 0

    today_start = datetime.combine(date.today(), datetime.min.time())
    today_new = (await db.execute(
        base.where(GameAnnouncement.published_at >= today_start)
    )).scalar() or 0

    return {"total": total, "today_new": today_new}


@router.get("/sync/status")
async def sync_status(_: User = Depends(get_current_user)):
    from app.crawlers.steam.announcement_sync import get_sync_status
    return get_sync_status()


@router.post("/sync")
async def trigger_sync(
    game_id: Optional[uuid.UUID] = Query(None),
    limit: Optional[int] = Query(None, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """手动同步公告。limit 不为空时为试爬：每个游戏只取最近 limit 条。"""
    if not current_user.is_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="仅管理员可触发同步")

    from app.crawlers.steam.announcement_sync import sync_announcements, _is_syncing
    if _is_syncing:
        return {"status": "already_running", "message": "同步正在进行中"}

    asyncio.create_task(sync_announcements(str(game_id) if game_id else None, limit=limit))
    return {"status": "started", "message": "同步已开始"}


@router.post("/clear")
async def clear_announcements(
    game_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """清空公告。game_id 不为空时只清该游戏，否则清全部。"""
    if not current_user.is_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="仅管理员可清空")

    from sqlalchemy import delete
    q = delete(GameAnnouncement)
    if game_id:
        q = q.where(GameAnnouncement.game_id == game_id)
    result = await db.execute(q)
    await db.commit()
    return {"deleted": result.rowcount}
