"""add dashboard_layout to users

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-09-15 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c6d7e8f9a0b1'
down_revision: str | Sequence[str] | None = 'b5c6d7e8f9a0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    `users.dashboard_layout` (2026-09-15, fora de qualquer build-context,
    pedido direto do usuário) — quais cards do Dashboard ficam visíveis e
    em que ordem, um array JSON de `{"card": "...", "visible": bool}`
    (ordem da lista = ordem de exibição). `NULL` = usuário nunca
    personalizou, o frontend cai no layout padrão (todos visíveis, ordem
    original) — mesmo espírito de `monthly_budget_cents IS NULL` já
    usado nesta tabela pra "ainda não configurado".
    """
    op.add_column("users", sa.Column("dashboard_layout", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "dashboard_layout")
