import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import AlertRule, AlertEvent, Comment, User
from app.auth import get_current_user
from app.schemas.schemas import AlertRuleCreate, AlertRuleUpdate, AlertRuleOut, AlertEventOut

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# ── Rules ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[AlertRuleOut])
async def list_rules(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(AlertRule).order_by(AlertRule.created_at.desc()))
    return [AlertRuleOut.model_validate(r) for r in result.scalars().all()]


@router.post("", response_model=AlertRuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(body: AlertRuleCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    rule = AlertRule(
        game_id=body.game_id,
        rule_type=body.rule_type,
        keywords=body.keywords,
        threshold_value=body.threshold_value,
        channel=body.channel,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return AlertRuleOut.model_validate(rule)


@router.put("/{rule_id}", response_model=AlertRuleOut)
async def update_rule(rule_id: uuid.UUID, body: AlertRuleUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Not found")
    if body.keywords is not None:
        rule.keywords = body.keywords
    if body.threshold_value is not None:
        rule.threshold_value = body.threshold_value
    if body.channel is not None:
        rule.channel = body.channel
    if body.enabled is not None:
        rule.enabled = body.enabled
    await db.flush()
    await db.refresh(rule)
    return AlertRuleOut.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(rule)


# ── Events ────────────────────────────────────────────────────────────────────

@router.get("/events", response_model=list[AlertEventOut])
async def list_events(
    game_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = (
        select(AlertEvent, AlertRule, Comment.content.label("comment_content"))
        .join(AlertRule, AlertEvent.rule_id == AlertRule.id)
        .outerjoin(Comment, AlertEvent.comment_id == Comment.id)
        .order_by(AlertEvent.triggered_at.desc())
        .limit(100)
    )
    if game_id:
        q = q.where(AlertRule.game_id == game_id)
    rows = (await db.execute(q)).all()

    result = []
    for event, rule, comment_content in rows:
        result.append(AlertEventOut(
            id=event.id,
            rule_id=event.rule_id,
            comment_id=event.comment_id,
            triggered_at=event.triggered_at,
            is_read=event.is_read,
            rule_type=rule.rule_type,
            keywords=rule.keywords,
            threshold_value=rule.threshold_value,
            comment_content=comment_content,
            game_id=rule.game_id,
        ))
    return result


@router.get("/unread-count")
async def unread_count(
    game_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = (
        select(func.count(AlertEvent.id))
        .join(AlertRule, AlertEvent.rule_id == AlertRule.id)
        .where(AlertEvent.is_read == False)  # noqa: E712
    )
    if game_id:
        q = q.where(AlertRule.game_id == game_id)
    count = (await db.execute(q)).scalar() or 0
    return {"count": count}


@router.post("/events/{event_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(event_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(AlertEvent).where(AlertEvent.id == event_id))
    event = result.scalar_one_or_none()
    if event:
        event.is_read = True


@router.post("/events/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    game_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = (
        select(AlertEvent)
        .join(AlertRule, AlertEvent.rule_id == AlertRule.id)
        .where(AlertEvent.is_read == False)  # noqa: E712
    )
    if game_id:
        q = q.where(AlertRule.game_id == game_id)
    events = (await db.execute(q)).scalars().all()
    for e in events:
        e.is_read = True
