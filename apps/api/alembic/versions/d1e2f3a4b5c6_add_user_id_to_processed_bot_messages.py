"""add user_id to processed_bot_messages

Revision ID: d1e2f3a4b5c6
Revises: c8f3a1b9d2e4
Create Date: 2026-09-10 00:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: str | Sequence[str] | None = 'c8f3a1b9d2e4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    `processed_bot_messages.user_id` (build-context-09 §2.6) — alteração
    incremental sobre a tabela do build-context-07 (RN-09, cadeia linear
    de migrations), mesmo padrão do `phone_hash` em `users`. Sustenta a
    contagem de mensagens do Bot por usuário/mês (`PlanLimits.
    whatsapp_bot_messages_per_month`) sem criar tabela nova. Nullable e
    `ON DELETE SET NULL`: a linha existe pela idempotência (RN-04)
    independente de o usuário ainda existir.
    """
    op.add_column(
        "processed_bot_messages",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_processed_bot_messages_user_id", "processed_bot_messages", ["user_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_processed_bot_messages_user_id", table_name="processed_bot_messages")
    op.drop_column("processed_bot_messages", "user_id")
