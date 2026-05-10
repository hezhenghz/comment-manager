import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import AlertRule, User
from app.auth import get_current_user
from app.schemas.schemas import AlertRuleCreate, AlertRuleUpdate, AlertRuleOut

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertRuleOut])
async def list_rules(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(AlertRule).order_by(AlertRule.created_at.desc()))
    return [AlertRuleOut.model_validate(r) for r in result.scalars().all()]


@router.post("", response_model=AlertRuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(body: AlertRuleCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    rule = AlertRule(game_id=body.game_id, keywords=body.keywords, channel=body.channel)
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
