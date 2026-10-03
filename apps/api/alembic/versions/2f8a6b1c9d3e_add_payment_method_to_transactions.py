"""add payment_method to transactions

Revision ID: 2f8a6b1c9d3e
Revises: 69d9315c549c
Create Date: 2026-08-10 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2f8a6b1c9d3e'
down_revision: str | Sequence[str] | None = '69d9315c549c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Ciphertext AES (RN-05) via EncryptedString — sem length fixo, mesmo padrão de description.
    op.add_column("transactions", sa.Column("payment_method", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("transactions", "payment_method")
