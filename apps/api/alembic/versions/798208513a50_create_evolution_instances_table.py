"""create evolution_instances table

Revision ID: 798208513a50
Revises: d4698009877d
Create Date: 2026-08-15 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '798208513a50'
down_revision: str | Sequence[str] | None = 'd4698009877d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

evolution_connection_status_enum = postgresql.ENUM(
    "connecting", "connected", "disconnected", name="evolution_connection_status"
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    evolution_connection_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "evolution_instances",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("public_id", sa.String(length=26), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        # Ciphertext AES (RN-05) via EncryptedString — sem length fixo, mesmo padrão de users.phone.
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "connecting", "connected", "disconnected",
                name="evolution_connection_status", create_type=False,
            ),
            nullable=False,
            server_default="disconnected",
        ),
        sa.Column("qr_code", sa.Text(), nullable=True),
        sa.Column("qr_code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("webhook_url", sa.String(length=500), nullable=False),
        sa.Column("webhook_secret", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ux_evolution_instances_public_id", "evolution_instances", ["public_id"], unique=True
    )
    op.create_index("ux_evolution_instances_name", "evolution_instances", ["name"], unique=True)
    op.create_index(
        "ux_evolution_instances_single_active",
        "evolution_instances",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ux_evolution_instances_single_active", table_name="evolution_instances")
    op.drop_index("ux_evolution_instances_name", table_name="evolution_instances")
    op.drop_index("ux_evolution_instances_public_id", table_name="evolution_instances")
    op.drop_table("evolution_instances")
    evolution_connection_status_enum.drop(op.get_bind(), checkfirst=True)
