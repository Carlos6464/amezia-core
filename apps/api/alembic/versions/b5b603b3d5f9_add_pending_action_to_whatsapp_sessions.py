"""add pending_action to whatsapp_sessions

Revision ID: b5b603b3d5f9
Revises: b2c3d4e5f6a7
Create Date: 2026-09-09 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b5b603b3d5f9'
down_revision: str | Sequence[str] | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "whatsapp_sessions",
        sa.Column("pending_action", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("whatsapp_sessions", "pending_action")
