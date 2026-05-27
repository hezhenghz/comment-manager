"""add discord_channel_names to games

Revision ID: 003
Revises: 002
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column(
            "discord_channel_names",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="'{}'",
        ),
    )


def downgrade() -> None:
    op.drop_column("games", "discord_channel_names")
