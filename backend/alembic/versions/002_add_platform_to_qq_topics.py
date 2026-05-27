"""add platform to qq_topics

Revision ID: 002
Revises: 001
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "qq_topics",
        sa.Column("platform", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("qq_topics", "platform")
