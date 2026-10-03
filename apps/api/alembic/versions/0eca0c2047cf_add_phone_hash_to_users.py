"""add phone_hash to users

Revision ID: 0eca0c2047cf
Revises: dca2555a3a1d
Create Date: 2026-08-15 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0eca0c2047cf'
down_revision: str | Sequence[str] | None = 'dca2555a3a1d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Cross-build-context: hash determinístico de telefone (build-context-07
    §2.2) sobre a tabela `users` (build-context-01) — RN-09 permite
    migration posterior alterar tabela de um build-context anterior, mesmo
    padrão já usado por `monthly_budget_cents` (build-context-03).
    HMAC-SHA256 (hex) = 64 caracteres fixos.
    """
    op.add_column("users", sa.Column("phone_hash", sa.String(length=64), nullable=True))
    op.create_index("ux_users_phone_hash", "users", ["phone_hash"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ux_users_phone_hash", table_name="users")
    op.drop_column("users", "phone_hash")
