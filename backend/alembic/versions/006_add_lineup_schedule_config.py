"""add lineup schedule config and trigger column

Revision ID: 006
Revises: 005
Create Date: 2026-06-03

阵容自动拉取「前端可见+可控」：
- 新增 lineup_schedule_config 单行配置表（enabled / interval_hours），并插入默认行
- lineup_fetch_jobs 新增 trigger 列（manual | auto），区分手动/定时来源

幂等实现：表/列可能已被 main.py 的 Base.metadata.create_all 创建，
迁移前先用 inspector 检查，避免 DuplicateTable / DuplicateColumn。
"""
from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # ── 1. 调度配置表 ─────────────────────────────────────────────────
    if not insp.has_table("lineup_schedule_config"):
        op.create_table(
            "lineup_schedule_config",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("interval_hours", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
    # 默认单行配置（已存在则不动）
    op.execute(
        "INSERT INTO lineup_schedule_config (id, enabled, interval_hours, updated_at) "
        "VALUES (1, TRUE, 1, NOW()) ON CONFLICT (id) DO NOTHING"
    )

    # ── 2. lineup_fetch_jobs 加 trigger 列 ────────────────────────────
    cols = [c["name"] for c in insp.get_columns("lineup_fetch_jobs")]
    if "trigger" not in cols:
        op.add_column(
            "lineup_fetch_jobs",
            sa.Column("trigger", sa.String(20), nullable=False, server_default="auto"),
        )
    # 存量历史 job 来源未知，统一回填为 manual（避免污染「上次自动拉取结果」）
    op.execute("UPDATE lineup_fetch_jobs SET trigger = 'manual'")
    idx = [i["name"] for i in insp.get_indexes("lineup_fetch_jobs")]
    if "ix_lineup_fetch_jobs_trigger" not in idx:
        op.create_index(
            "ix_lineup_fetch_jobs_trigger", "lineup_fetch_jobs", ["trigger"]
        )


def downgrade() -> None:
    op.drop_index("ix_lineup_fetch_jobs_trigger", table_name="lineup_fetch_jobs")
    op.drop_column("lineup_fetch_jobs", "trigger")
    op.drop_table("lineup_schedule_config")
