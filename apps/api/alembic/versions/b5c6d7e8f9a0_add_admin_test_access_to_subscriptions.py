"""add admin_test_access_granted_at to subscriptions

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-09-15 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b5c6d7e8f9a0'
down_revision: str | Sequence[str] | None = 'a4b5c6d7e8f9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    `subscriptions.admin_test_access_granted_at` (2026-09-15) — acesso de
    teste Premium concedido manualmente pelo admin a um usuário
    específico, sem passar pelo Stripe (nunca gera cobrança real).
    `NULL` = conta normal; preenchido = "vitalício" até um admin desligar
    de novo (`resolve_effective_plan()` no domínio devolve Premium na
    hora enquanto este campo estiver preenchido, antes de olhar
    `plan`/Stripe/`legacy_pro_until`). Guarda a data de concessão (não um
    booleano) pelo mesmo motivo de `legacy_pro_until`/`trial_ends_at`
    nesta tabela — dá rastro de auditoria de quando foi concedido, sem
    precisar de uma coluna extra só pra isso.
    """
    op.add_column(
        "subscriptions",
        sa.Column("admin_test_access_granted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("subscriptions", "admin_test_access_granted_at")
