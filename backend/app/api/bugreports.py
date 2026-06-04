"""
BUG上报 API 路由
前缀：/api/bugreports

GET  /api/bugreports             列表（分页 + 筛选）
GET  /api/bugreports/stats       统计（按状态分组）
GET  /api/bugreports/sync/status 同步状态（上次时间 + 是否进行中）
POST /api/bugreports/sync        手动触发同步（仅管理员，使用本地 ZenTao 凭据）
POST /api/bugreports/_push       接收外部推送（用于异地爬虫架构，Token 鉴权）
"""

import asyncio
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import BugReport
from app.auth import get_current_user
from app.models import User

router = APIRouter(prefix="/api/bugreports", tags=["bugreports"])

# 优先级 / 严重程度 / 状态的中文标签
PRIORITY_LABEL = {1: "紧急", 2: "重要", 3: "中", 4: "低"}
SEVERITY_LABEL = {1: "严重", 2: "重要", 3: "中", 4: "低"}
STATUS_LABEL   = {"active": "激活", "resolved": "已解决", "closed": "已关闭"}


def _bug_to_dict(b: BugReport) -> dict:
    return {
        "id":           str(b.id),
        "external_id":  b.external_id,
        "title":        b.title,
        "description":  b.description,
        "status":       b.status,
        "status_label": STATUS_LABEL.get(b.status or "", b.status or "—"),
        "priority":     b.priority,
        "priority_label": PRIORITY_LABEL.get(b.priority, "—") if b.priority else "—",
        "severity":     b.severity,
        "severity_label": SEVERITY_LABEL.get(b.severity, "—") if b.severity else "—",
        "module":       b.module,
        "submitter":    b.submitter,
        "assignee":     b.assignee,
        "submitted_at": b.submitted_at.isoformat() + "Z" if b.submitted_at else None,
        "resolved_at":  b.resolved_at.isoformat() + "Z" if b.resolved_at else None,
        "closed_at":    b.closed_at.isoformat() + "Z" if b.closed_at else None,
        "source_url":   b.source_url,
        "product":      b.product,
        "fetched_at":   b.fetched_at.isoformat() + "Z" if b.fetched_at else None,
    }


@router.get("")
async def list_bug_reports(
    page:      int            = Query(1, ge=1),
    per_page:  int            = Query(20, ge=1, le=100),
    status:    Optional[str]  = Query(None),
    priority:  Optional[int]  = Query(None),
    severity:  Optional[int]  = Query(None),
    submitter: Optional[str]  = Query(None),
    keyword:   Optional[str]  = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """返回 Bug 列表（分页 + 多维筛选）。"""
    q = select(BugReport)

    if status:
        q = q.where(BugReport.status == status)
    if priority is not None:
        q = q.where(BugReport.priority == priority)
    if severity is not None:
        q = q.where(BugReport.severity == severity)
    if submitter:
        q = q.where(BugReport.submitter.ilike(f"%{submitter}%"))
    if keyword:
        q = q.where(BugReport.title.ilike(f"%{keyword}%"))

    # 总数
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # 分页
    q = q.order_by(desc(BugReport.submitted_at)).offset((page - 1) * per_page).limit(per_page)
    rows = (await db.execute(q)).scalars().all()

    return {
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "items":    [_bug_to_dict(r) for r in rows],
    }


@router.get("/stats")
async def bug_stats(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """按状态分组统计 Bug 数量，以及今日新增数量。"""
    from datetime import datetime, date

    # 按状态分组
    rows = (await db.execute(
        select(BugReport.status, func.count().label("cnt"))
        .group_by(BugReport.status)
    )).all()

    by_status = {r.status or "unknown": r.cnt for r in rows}
    total = sum(by_status.values())

    # 今日新增（按 submitted_at 当天 — 即玩家上报当天）
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_new = (await db.execute(
        select(func.count()).where(BugReport.submitted_at >= today_start)
    )).scalar_one()

    return {
        "total":      total,
        "active":     by_status.get("active", 0),
        "resolved":   by_status.get("resolved", 0),
        "closed":     by_status.get("closed", 0),
        "today_new":  today_new,
        "by_status":  by_status,
    }


@router.get("/sync/status")
async def sync_status(
    _current_user: User = Depends(get_current_user),
):
    """返回上次同步时间和当前同步状态。"""
    from app.crawlers.zentao.sync import get_sync_status
    return get_sync_status()


@router.post("/sync")
async def trigger_sync(
    current_user: User = Depends(get_current_user),
):
    """
    手动触发 BUG 同步。
    优先级：
      1. 如果配置了 LOCAL_PUSHER_URL，则转发到本地推送服务（异地架构）
      2. 否则使用本机的 ZenTao 凭据直接同步（单机架构）
    """
    if not current_user.is_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="仅管理员可触发同步")

    settings = get_settings()
    local_pusher_url = getattr(settings, "local_pusher_url", "") or os.environ.get("LOCAL_PUSHER_URL", "")

    # 异地架构：转发到本地推送服务
    if local_pusher_url:
        push_token = getattr(settings, "bug_push_token", "") or os.environ.get("BUG_PUSH_TOKEN", "")
        if not push_token:
            return {"status": "error", "message": "BUG_PUSH_TOKEN 未配置"}

        import httpx
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    f"{local_pusher_url.rstrip('/')}/trigger",
                    headers={"X-Push-Token": push_token},
                )
            if resp.status_code == 200:
                return {"status": "started", "message": "已通知本地推送服务，约 1 分钟后可见新数据"}
            elif resp.status_code == 401:
                return {"status": "error", "message": "本地推送服务 Token 验证失败"}
            else:
                return {"status": "error", "message": f"本地推送服务返回 {resp.status_code}"}
        except httpx.ConnectError:
            return {"status": "error", "message": "无法连接本地推送服务（请检查本地服务是否运行 + 防火墙）"}
        except httpx.TimeoutException:
            return {"status": "error", "message": "连接本地推送服务超时"}
        except Exception as e:
            return {"status": "error", "message": f"转发失败: {e}"}

    # 单机架构：本机直接同步
    from app.crawlers.zentao.sync import sync_bug_reports, _is_syncing
    if _is_syncing:
        return {"status": "already_running", "message": "同步正在进行中"}
    asyncio.create_task(sync_bug_reports())
    return {"status": "started", "message": "同步已开始"}


# ─── 外部推送端点（异地爬虫架构） ───────────────────────────────────────────

class BugReportPushItem(BaseModel):
    external_id:  str
    title:        str
    description:  Optional[str] = None
    status:       Optional[str] = "active"
    priority:     Optional[int] = None
    severity:     Optional[int] = None
    module:       Optional[str] = None
    submitter:    Optional[str] = None
    assignee:     Optional[str] = None
    submitted_at: Optional[datetime] = None
    resolved_at:  Optional[datetime] = None
    closed_at:    Optional[datetime] = None
    source_url:   Optional[str] = None
    product:      Optional[str] = "xkbb"
    raw_json:     Optional[dict] = None


class BugReportPushPayload(BaseModel):
    items: list[BugReportPushItem]


@router.post("/_push")
async def push_bug_reports(
    payload: BugReportPushPayload,
    x_push_token: Optional[str] = Header(None, alias="X-Push-Token"),
    db: AsyncSession = Depends(get_db),
):
    """
    接收外部爬虫推送的 BUG 数据（异地爬虫架构）。
    远程主机不爬数据，由本地机器跑 Playwright 爬完后 POST 推送过来。

    鉴权：Header `X-Push-Token` 必须等于 .env 中的 BUG_PUSH_TOKEN。
    去重：按 external_id 跳过已存在的记录。
    """
    settings = get_settings()
    expected = getattr(settings, "bug_push_token", "") or os.environ.get("BUG_PUSH_TOKEN", "")

    if not expected:
        raise HTTPException(status_code=503, detail="BUG_PUSH_TOKEN 未配置，推送端点未启用")

    if x_push_token != expected:
        raise HTTPException(status_code=401, detail="Token 无效")

    new_count = 0
    skipped = 0
    for item in payload.items:
        existing = (await db.execute(
            select(BugReport.id).where(BugReport.external_id == item.external_id)
        )).scalar_one_or_none()

        if existing is not None:
            skipped += 1
            continue

        db.add(BugReport(
            external_id  = item.external_id,
            title        = item.title,
            description  = item.description,
            status       = item.status or "active",
            priority     = item.priority,
            severity     = item.severity,
            module       = item.module,
            submitter    = item.submitter,
            assignee     = item.assignee,
            submitted_at = item.submitted_at,
            resolved_at  = item.resolved_at,
            closed_at    = item.closed_at,
            source_url   = item.source_url,
            product      = item.product or "xkbb",
            fetched_at   = datetime.utcnow(),
            raw_json     = item.raw_json,
        ))
        new_count += 1

    await db.commit()
    return {"received": len(payload.items), "new": new_count, "skipped": skipped}
