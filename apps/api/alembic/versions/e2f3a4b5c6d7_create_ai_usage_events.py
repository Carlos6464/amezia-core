"""create ai_usage_events

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-09-10 01:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: str | Sequence[str] | None = 'd1e2f3a4b5c6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ai_usage_feature_enum = postgresql.ENUM(
    "agent_chat",
    "report_narrative",
    "bot_expense_parsing",
    "bot_audio_transcription",
    name="ai_usage_feature",
)
ai_usage_provider_enum = postgresql.ENUM("gemini", "grok", name="ai_usage_provider")


def upgrade() -> None:
    """Upgrade schema.

    Tabela `ai_usage_events` (build-context-10 §2.3) — log unificado de
    toda chamada de IA do produto. `feature`/`provider` são enum Postgres
    (conjunto fechado e conhecido); `model` é `VARCHAR` de propósito
    (modelo novo não deve exigir migration). `ON DELETE CASCADE` em
    `user_id` estende o cascade de exclusão de conta (RN-03).
    """
    ai_usage_feature_enum.create(op.get_bind(), checkfirst=True)
    ai_usage_provider_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ai_usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "feature",
            postgresql.ENUM(
                "agent_chat",
                "report_narrative",
                "bot_expense_parsing",
                "bot_audio_transcription",
                name="ai_usage_feature",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "provider",
            postgresql.ENUM("gemini", "grok", name="ai_usage_provider", create_type=False),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_ai_usage_user_id_created_at", "ai_usage_events", ["user_id", "created_at"]
    )
    op.create_index("ix_ai_usage_created_at", "ai_usage_events", ["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ai_usage_created_at", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_user_id_created_at", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
    ai_usage_provider_enum.drop(op.get_bind(), checkfirst=True)
    ai_usage_feature_enum.drop(op.get_bind(), checkfirst=True)
