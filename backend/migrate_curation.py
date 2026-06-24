"""
一次性迁移脚本：建 curation_decisions 表 + 从 RequirementCard 回填历史"已采纳"决定。

在项目根目录执行：
  .venv\\Scripts\\python.exe backend\\migrate_curation.py

逻辑：
- create_all 自动建表（含 curation_decisions）。
- 已有 RequirementCard 的每条记录 = 历史采集 = 一次"采纳"决定，
  按 (source_type, source_id) 补一条 curation_decision，decision='adopted'，
  ai_prediction 留空（不计入准确率）。已存在的跳过。
"""
import asyncio
from datetime import datetime

from sqlalchemy import select

from app.database import engine, Base, async_session
from app.models import RequirementCard, CurationDecision


async def main():
    from sqlalchemy import text

    # 1. 建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 修正唯一约束：旧版 (source_type, source_id) → 新版 (source_id)
        await conn.execute(text(
            "ALTER TABLE curation_decisions DROP CONSTRAINT IF EXISTS uq_curation_source"
        ))
        await conn.execute(text(
            "ALTER TABLE curation_decisions DROP CONSTRAINT IF EXISTS uq_curation_source_id"
        ))
        await conn.execute(text(
            "ALTER TABLE curation_decisions ADD CONSTRAINT uq_curation_source_id "
            "UNIQUE (source_id)"
        ))
        # 补齐 RequirementCard 模型已声明但表中缺失的列（历史迁移遗漏，
        # 采纳进需求板时 ORM 会写这两列）
        await conn.execute(text(
            "ALTER TABLE requirement_cards ADD COLUMN IF NOT EXISTS "
            "ticket_type VARCHAR(20) NOT NULL DEFAULT 'requirement'"
        ))
        await conn.execute(text(
            "ALTER TABLE requirement_cards ADD COLUMN IF NOT EXISTS "
            "priority VARCHAR(10) NOT NULL DEFAULT 'medium'"
        ))
    print("OK: 表与约束已就绪")

    # 2. 回填历史采集为 adopted
    # 只查实际存在的列，避开 RequirementCard 模型里未迁移的 ticket_type/priority
    async with async_session() as db:
        cards = (await db.execute(select(
            RequirementCard.game_id,
            RequirementCard.source_type,
            RequirementCard.source_id,
            RequirementCard.source_snapshot,
            RequirementCard.created_at,
        ))).all()
        print(f"RequirementCard 共 {len(cards)} 条")

        # 已存在的 (source_type, source_id) 去重
        existing = set((await db.execute(
            select(CurationDecision.source_type, CurationDecision.source_id)
        )).all())

        new_count = 0
        for game_id, source_type, source_id, snapshot, created_at in cards:
            key = (source_type, source_id)
            if key in existing:
                continue
            db.add(CurationDecision(
                game_id=game_id,
                source_type=source_type,
                source_id=source_id,
                decision="adopted",
                decided_at=created_at or datetime.utcnow(),
                source_snapshot=snapshot or {},
            ))
            existing.add(key)
            new_count += 1

        await db.commit()
        print(f"回填 adopted 决定：{new_count} 条")

    await engine.dispose()
    print("完成！")


asyncio.run(main())
