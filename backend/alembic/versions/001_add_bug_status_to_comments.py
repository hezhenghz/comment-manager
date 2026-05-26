"""add bug_status to comments

Revision ID: 001
Revises:
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "comments",
        sa.Column("bug_status", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("comments", "bug_status")
