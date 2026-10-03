"""add monthly budget limit to users

Revision ID: 96ecdf3b1016
Revises: 7f4b3c3637ef
Create Date: 2026-08-09 14:16:11.884627

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '96ecdf3b1016'
down_revision: str | Sequence[str] | None = '7f4b3c3637ef'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Cross-build-context: teto mensal (build-context-03) é um campo do
    perfil do usuário (build-context-01), mesmo padrão já previsto para
    `phone_hash` (build-context-07) — RN-09 permite migration posterior
    alterar tabela de um build-context anterior.
    """
    op.add_column("users", sa.Column("monthly_budget_cents", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "monthly_budget_cents")
