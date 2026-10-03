"""add paid_at to transactions

Revision ID: d4698009877d
Revises: 79f48337fa34
Create Date: 2026-08-12 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4698009877d'
down_revision: str | Sequence[str] | None = '79f48337fa34'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Cross-build-context: `paid_at` (data efetiva do pagamento, distinta de
    `date` — data do lançamento/vencimento) foi sugerido pelo usuário em
    2026-08-09 e deliberadamente adiado (ver DIARIO.md) para não misturar
    schema novo com um fix pontual da época. Retomado em 2026-08-12 junto
    do botão "Pagar" (marca status=paid + define paid_at + comprovante
    opcional, reaproveitando PUT /transactions/{id} e POST .../receipt já
    existentes).
    """
    op.add_column("transactions", sa.Column("paid_at", sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("transactions", "paid_at")
