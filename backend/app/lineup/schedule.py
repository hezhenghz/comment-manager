# -*- coding: utf-8 -*-
"""阵容自动拉取调度配置的读写 helper（单行配置，持久化到 DB）。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import LineupScheduleConfig


async def get_or_create_config(db: AsyncSession) -> LineupScheduleConfig:
    """读取单行调度配置；不存在则按 settings 默认值初始化。"""
    cfg = await db.get(LineupScheduleConfig, 1)
    if cfg is None:
        cfg = LineupScheduleConfig(
            id=1,
            enabled=True,
            interval_hours=get_settings().lineup_interval_hours,
        )
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    return cfg
