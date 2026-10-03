"""create whatsapp bot tables

Revision ID: fcd68f69f49f
Revises: 0eca0c2047cf
Create Date: 2026-08-15 18:05:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fcd68f69f49f'
down_revision: str | Sequence[str] | None = '0eca0c2047cf'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

whatsapp_bot_mode_enum = postgresql.ENUM(
    "expense", "chat", "report", "feedback", name="whatsapp_bot_mode"
)


def upgrade() -> None:
    """Upgrade schema.

    `whatsapp_sessions` (build-context-07 §2.4) — uma linha por usuário
    (não por conversa/mensagem), `current_state` NULL = Menu.
    `processed_bot_messages` — deduplicação (RN-04), UNIQUE composto
    sustenta o `INSERT ... ON CONFLICT DO NOTHING` atômico.
    """
    bind = op.get_bind()
    whatsapp_bot_mode_enum.create(bind, checkfirst=True)

    op.create_table(
        "whatsapp_sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phone_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "current_state",
            postgresql.ENUM(
                "expense", "chat", "report", "feedback", name="whatsapp_bot_mode", create_type=False
            ),
            nullable=True,
        ),
        sa.Column(
            "last_interaction_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "ux_whatsapp_sessions_user_id", "whatsapp_sessions", ["user_id"], unique=True
    )
    op.create_index(
        "ux_whatsapp_sessions_phone_hash", "whatsapp_sessions", ["phone_hash"], unique=True
    )

    op.create_table(
        "processed_bot_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "whatsapp_instance_id",
            sa.BigInteger(),
            sa.ForeignKey("evolution_instances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("whatsapp_message_id", sa.String(length=255), nullable=False),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "whatsapp_instance_id", "whatsapp_message_id", name="ux_processed_bot_messages_instance_message"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("processed_bot_messages")
    op.drop_index("ux_whatsapp_sessions_phone_hash", table_name="whatsapp_sessions")
    op.drop_index("ux_whatsapp_sessions_user_id", table_name="whatsapp_sessions")
    op.drop_table("whatsapp_sessions")
    whatsapp_bot_mode_enum.drop(op.get_bind(), checkfirst=True)
