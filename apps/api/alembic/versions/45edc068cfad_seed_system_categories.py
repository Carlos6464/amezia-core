"""seed system categories

Revision ID: 45edc068cfad
Revises: 1c9ce829e231
Create Date: 2026-08-09 02:56:11.324369

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '45edc068cfad'
down_revision: str | Sequence[str] | None = '1c9ce829e231'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# public_id gerado uma única vez ao escrever esta migration (build-context-02
# §2.3) — os nomes/cores são a decisão pragmática registrada nas Observações
# do build-context (PRD Seção 6.3 só pede "7 categorias de sistema via seed",
# sem listar quais).
SYSTEM_CATEGORIES = [
    {"public_id": "01KZJ77B0H0460W4J9SKQ8TJQW", "name": "Alimentação", "color": "#6366f1"},
    {"public_id": "01KZJ77B0JCM7MQYSHRK8VSTGY", "name": "Moradia", "color": "#f43f5e"},
    {"public_id": "01KZJ77B0KSA193NF847ZKZ6C3", "name": "Transporte", "color": "#818cf8"},
    {"public_id": "01KZJ77B0MYKPNHWZJDYWYF11W", "name": "Saúde", "color": "#10b981"},
    {"public_id": "01KZJ77B0NES4GSXNEGBPMSBD6", "name": "Educação", "color": "#60a5fa"},
    {"public_id": "01KZJ77B0PR85X8139ESWWQ7VV", "name": "Lazer", "color": "#f59e0b"},
    {"public_id": "01KZJ77B0Q9SYXDAD46Q148KET", "name": "Outros", "color": "#94a3b8"},
]

categories_table = sa.table(
    "categories",
    sa.column("public_id", sa.String),
    sa.column("name", sa.String),
    sa.column("color", sa.String),
    sa.column("user_id", postgresql.UUID(as_uuid=True)),
    sa.column("is_system", sa.Boolean),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.bulk_insert(
        categories_table,
        [
            {
                "public_id": category["public_id"],
                "name": category["name"],
                "color": category["color"],
                "user_id": None,
                "is_system": True,
            }
            for category in SYSTEM_CATEGORIES
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sa.text("DELETE FROM categories WHERE is_system = true AND public_id = ANY(:ids)").bindparams(
            ids=[category["public_id"] for category in SYSTEM_CATEGORIES]
        )
    )
