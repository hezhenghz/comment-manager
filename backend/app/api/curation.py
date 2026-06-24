"""
策划处理 + AI 影子学习 API
前缀：/api/curation

POST /api/curation/decide       策划处理一条（采纳/不采纳）；采纳自动进需求板
GET  /api/curation/decisions    某游戏/类型下各 source_id 的处理状态（前端渲染徽章）
GET  /api/curation/accuracy     游戏管理用：近 100 条 AI 预判一致率
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import CurationDecision, RequirementCard, User, Game
from app.auth import get_current_user

router = APIRouter(prefix="/api/curation", tags=["curation"])

_VALID_DECISIONS = {"adopted", "rejected"}
_ACCURACY_WINDOW = 100


class DecideBody(BaseModel):
    game_id: uuid.UUID
    source_type: str           # 'comment'|'bug'|'suggestion'|'topic'|'bugreport'
    source_id: uuid.UUID
    decision: str              # 'adopted' | 'rejected'
    source_snapshot: dict = {}  # 采纳进需求板时用（标题/内容快照）


@router.post("/decide")
async def decide(
    body: DecideBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.decision not in _VALID_DECISIONS:
        raise HTTPException(status_code=400, detail=f"非法处理结果: {body.decision}")

    game = await db.get(Game, body.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # 取或建决定记录（source_id 唯一）
    row = (await db.execute(
        select(CurationDecision).where(CurationDecision.source_id == body.source_id)
    )).scalar_one_or_none()
    if row is None:
        row = CurationDecision(
            game_id=body.game_id,
            source_type=body.source_type,
            source_id=body.source_id,
            decision="pending",
        )
        db.add(row)

    row.decision = body.decision
    row.decided_by = current_user.id
    row.decided_at = datetime.utcnow()
    if body.source_snapshot and not row.source_snapshot:
        row.source_snapshot = body.source_snapshot
    # 回填 AI 预判命中（仅当此前有影子预判）
    if row.ai_prediction:
        row.ai_hit = (row.ai_prediction == body.decision)

    # 采纳 → 采集进需求板（复用现有逻辑：AI 生成需求描述 + 插入；已存在则跳过）
    if body.decision == "adopted":
        await _collect_to_requirements(db, body)

    await db.commit()
    return {"ok": True, "decision": row.decision, "ai_hit": row.ai_hit}


async def _collect_to_requirements(db: AsyncSession, body: DecideBody) -> None:
    """把条目采集进需求板，逻辑对齐 requirements.create_requirement。已采集则跳过。"""
    existing = (await db.execute(
        select(RequirementCard.id).where(RequirementCard.source_id == body.source_id)
    )).scalar_one_or_none()
    if existing:
        return

    from app.ai.requirement_generator import generate_requirement_text
    snapshot = dict(body.source_snapshot or {})
    snapshot["source_type"] = body.source_type
    try:
        req_text = await generate_requirement_text(snapshot)
    except Exception:
        req_text = ""

    db.add(RequirementCard(
        game_id=body.game_id,
        source_type=body.source_type,
        source_id=body.source_id,
        source_snapshot=body.source_snapshot or {},
        requirement_text=req_text,
        status="todo",
    ))


@router.get("/decisions")
async def list_decisions(
    game_id: uuid.UUID = Query(...),
    source_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """返回该游戏（可选类型）下已处理条目的 {source_id: decision} 映射。
    供前端渲染「已采纳/已不采纳」徽章。"""
    q = select(CurationDecision.source_id, CurationDecision.decision).where(
        CurationDecision.game_id == game_id,
        CurationDecision.decision != "pending",
    )
    if source_type:
        q = q.where(CurationDecision.source_type == source_type)
    rows = (await db.execute(q)).all()
    return {str(sid): dec for sid, dec in rows}


@router.get("/accuracy")
async def accuracy(
    game_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """近 100 条 AI 影子预判一致率（仅统计有预判且已决定的）。
    未达冷启动门槛时 predicting=False，前端显示「样本积累中」。"""
    # 已处理样本数（判断是否进入预判阶段）
    processed_count = (await db.execute(
        select(func.count(CurationDecision.id)).where(
            CurationDecision.game_id == game_id,
            CurationDecision.decision != "pending",
        )
    )).scalar() or 0

    # 最近 N 条有 ai_hit（即有预判且已决定）的记录
    rows = (await db.execute(
        select(CurationDecision.ai_hit).where(
            CurationDecision.game_id == game_id,
            CurationDecision.ai_hit.isnot(None),
        ).order_by(desc(CurationDecision.decided_at)).limit(_ACCURACY_WINDOW)
    )).scalars().all()

    total = len(rows)
    hit = sum(1 for h in rows if h)
    rate = round(hit / total * 100, 1) if total else None

    return {
        "processed_count": processed_count,
        "cold_start_threshold": 100,
        "predicting": processed_count >= 100,
        "total": total,
        "hit": hit,
        "rate": rate,
    }
