"""decouple ai pipeline from crawl

Revision ID: 005
Revises: 004
Create Date: 2026-05-28

把 AI 分析从爬取阶段解耦：
- comments 表新增 ai_status / ai_retry_count / next_ai_attempt_at / last_ai_error / is_game_feedback
- 回填存量：已分析（sentiment 非空）→ done；未分析 → pending；
  Discord 已分析 → is_game_feedback=TRUE
- 加 partial index 加速 worker 扫 pending
"""
from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. 加字段（带 server_default 让既有行有值）──────────────────────
    op.add_column(
        "comments",
        sa.Column("ai_status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.add_column(
        "comments",
        sa.Column("ai_retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "comments",
        sa.Column("next_ai_attempt_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "comments",
        sa.Column("last_ai_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "comments",
        sa.Column("is_game_feedback", sa.Boolean(), nullable=True),
    )

    # ── 2. 回填存量 ───────────────────────────────────────────────────
    # 已经做过 AI 分析的标 done；剩余保持 pending（来自 server_default）
    op.execute("UPDATE comments SET ai_status = 'done' WHERE sentiment IS NOT NULL")
    # Discord 已分析的回填 is_game_feedback=TRUE，保持前端可见性一致
    op.execute(
        "UPDATE comments "
        "SET is_game_feedback = TRUE "
        "WHERE platform = 'discord' AND sentiment IS NOT NULL"
    )

    # ── 3. partial index：worker 扫 pending 时只扫 pending 行 ─────────
    op.execute(
        "CREATE INDEX idx_comments_ai_pending "
        "ON comments (next_ai_attempt_at NULLS FIRST, fetched_at) "
        "WHERE ai_status = 'pending'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_comments_ai_pending")
    op.drop_column("comments", "is_game_feedback")
    op.drop_column("comments", "last_ai_error")
    op.drop_column("comments", "next_ai_attempt_at")
    op.drop_column("comments", "ai_retry_count")
    op.drop_column("comments", "ai_status")
