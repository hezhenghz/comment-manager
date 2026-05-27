"""add requirement_cards table

Revision ID: 004
Revises: 003
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "requirement_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("game_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_snapshot", postgresql.JSONB(), nullable=True, server_default="'{}'"),
        sa.Column("requirement_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="todo"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_req_cards_game_id", "requirement_cards", ["game_id"])
    op.create_index("idx_req_cards_source_id", "requirement_cards", ["source_id"])


def downgrade() -> None:
    op.drop_index("idx_req_cards_source_id", "requirement_cards")
    op.drop_index("idx_req_cards_game_id", "requirement_cards")
    op.drop_table("requirement_cards")
