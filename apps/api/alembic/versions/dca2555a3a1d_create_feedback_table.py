"""create feedback table

Revision ID: dca2555a3a1d
Revises: 798208513a50
Create Date: 2026-08-15 09:05:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'dca2555a3a1d'
down_revision: str | Sequence[str] | None = '798208513a50'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

feedback_channel_enum = postgresql.ENUM("web", "whatsapp", name="feedback_channel")


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    feedback_channel_enum.create(bind, checkfirst=True)

    op.create_table(
        "feedback",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("public_id", sa.String(length=26), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Ciphertext AES (RN-05) via EncryptedString — sem length fixo, mesmo padrão de users.phone.
        sa.Column("message", sa.String(), nullable=False),
        sa.Column(
            "channel",
            postgresql.ENUM("web", "whatsapp", name="feedback_channel", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ux_feedback_public_id", "feedback", ["public_id"], unique=True)
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_created_at", "feedback", ["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_feedback_created_at", table_name="feedback")
    op.drop_index("ix_feedback_user_id", table_name="feedback")
    op.drop_index("ux_feedback_public_id", table_name="feedback")
    op.drop_table("feedback")
    feedback_channel_enum.drop(op.get_bind(), checkfirst=True)
