"""
群聊 API
POST /api/chat/messages?game_id=...    发送消息
GET  /api/chat/messages?game_id=...&since=<ISO>&limit=50  拉取消息（短轮询）
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ChatMessage, User
from app.schemas.schemas import ChatMessageCreate, ChatMessageOut
from app.api.auth import get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/messages", response_model=ChatMessageOut, status_code=201)
async def send_message(
    game_id: uuid.UUID,
    body: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="消息内容不能为空")
    if len(content) > 2000:
        raise HTTPException(status_code=422, detail="消息内容不能超过 2000 字符")

    display_name = current_user.display_name or current_user.username
    msg = ChatMessage(
        game_id=game_id,
        user_id=current_user.id,
        display_name=display_name,
        content=content,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


@router.get("/messages", response_model=list[ChatMessageOut])
async def get_messages(
    game_id: uuid.UUID,
    since: Optional[str] = Query(None, description="ISO datetime，只返回此时间之后的消息"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(ChatMessage).where(ChatMessage.game_id == game_id)

    if since:
        # 解析 ISO datetime，兼容带/不带时区
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            # 转为无时区（数据库存 UTC 无时区）
            if since_dt.tzinfo is not None:
                since_dt = since_dt.replace(tzinfo=None)
        except ValueError:
            raise HTTPException(status_code=422, detail="since 参数格式不正确，请使用 ISO 8601")
        stmt = stmt.where(ChatMessage.created_at > since_dt)
        stmt = stmt.order_by(ChatMessage.created_at.asc()).limit(limit)
    else:
        # 初始加载：返回最近 N 条，按时间正序排列
        subq = (
            select(ChatMessage)
            .where(ChatMessage.game_id == game_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
            .subquery()
        )
        from sqlalchemy.orm import aliased
        ChatAlias = aliased(ChatMessage, subq)
        stmt = select(ChatAlias).order_by(ChatAlias.created_at.asc())

    result = await db.execute(stmt)
    return result.scalars().all()
