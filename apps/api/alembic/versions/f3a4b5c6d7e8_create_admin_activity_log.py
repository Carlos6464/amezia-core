"""create admin_activity_log

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-09-11 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f3a4b5c6d7e8'
down_revision: str | Sequence[str] | None = 'e2f3a4b5c6d7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Tabela `admin_activity_log` (build-context-11 §2.3) — feed de
    atividade recente da Visão Geral do Admin (cadastro, upgrade/
    downgrade/cancelamento de assinatura). `event_type` é `VARCHAR`, não
    enum Postgres — a lista de eventos cresce conforme novos módulos
    quiserem aparecer no feed, sem exigir migration a cada um.
    `user_id` nullable + `ON DELETE SET NULL`: o registro de atividade é
    histórico, deve sobreviver à exclusão da conta (RN-03 não cobre esta
    tabela — é log, não dado do usuário).
    """
    op.create_table(
        "admin_activity_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_admin_activity_log_created_at", "admin_activity_log", ["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_admin_activity_log_created_at", table_name="admin_activity_log")
    op.drop_table("admin_activity_log")
