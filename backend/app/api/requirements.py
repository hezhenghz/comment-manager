import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import RequirementCard, User, Game
from app.auth import get_current_user
from app.schemas.schemas import RequirementCardCreate, RequirementCardOut, RequirementCardUpdate

router = APIRouter(prefix="/api/requirements", tags=["requirements"])

_VALID_STATUSES = {"todo", "in_progress", "done"}


@router.post("", response_model=RequirementCardOut)
async def create_requirement(
    body: RequirementCardCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """采集一条需求卡。同一 source_id 不允许重复采集。采集后自动触发 AI 生成需求描述。"""
    # 防重复：同一 source_id 已采集
    existing = (
        await db.execute(
            select(RequirementCard).where(RequirementCard.source_id == body.source_id)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="该内容已采集到需求板")

    # 确认游戏存在
    game = await db.get(Game, body.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # AI 生成需求描述
    from app.ai.requirement_generator import generate_requirement_text
    snapshot = dict(body.source_snapshot)
    snapshot["source_type"] = body.source_type
    req_text = await generate_requirement_text(snapshot)

    card = RequirementCard(
        game_id=body.game_id,
        source_type=body.source_type,
        source_id=body.source_id,
        source_snapshot=body.source_snapshot,
        requirement_text=req_text,
        status="todo",
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


@router.get("", response_model=list[RequirementCardOut])
async def list_requirements(
    game_id: uuid.UUID = Query(...),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """列出指定游戏的需求卡（按创建时间倒序）。"""
    from sqlalchemy import desc

    q = select(RequirementCard).where(RequirementCard.game_id == game_id)
    if status and status in _VALID_STATUSES:
        q = q.where(RequirementCard.status == status)
    q = q.order_by(desc(RequirementCard.created_at))
    rows = (await db.execute(q)).scalars().all()
    return list(rows)


@router.get("/collected-ids")
async def get_collected_ids(
    game_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """返回指定游戏已采集的 source_id 列表（供前端显示"已安排"徽章）。"""
    rows = (
        await db.execute(
            select(RequirementCard.source_id).where(RequirementCard.game_id == game_id)
        )
    ).scalars().all()
    return {"source_ids": [str(sid) for sid in rows]}


@router.patch("/{card_id}", response_model=RequirementCardOut)
async def update_requirement(
    card_id: uuid.UUID,
    body: RequirementCardUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """更新需求描述文本或状态。"""
    card = await db.get(RequirementCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Requirement card not found")

    if body.requirement_text is not None:
        card.requirement_text = body.requirement_text
    if body.status is not None:
        if body.status not in _VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
        card.status = body.status
    card.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(card)
    return card


@router.delete("/{card_id}")
async def delete_requirement(
    card_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """删除需求卡。"""
    card = await db.get(RequirementCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Requirement card not found")
    await db.delete(card)
    await db.commit()
    return {"ok": True}
