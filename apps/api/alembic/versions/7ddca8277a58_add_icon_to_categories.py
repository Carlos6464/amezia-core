"""add icon to categories

Revision ID: 7ddca8277a58
Revises: 45edc068cfad
Create Date: 2026-08-09 04:01:05.102658

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7ddca8277a58'
down_revision: str | Sequence[str] | None = '45edc068cfad'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Ícone padrão para categorias já existentes (privadas criadas antes deste
# build-context) — "tag" é o mesmo ícone usado como fallback no frontend e
# reaproveita o path já presente no menu lateral (Categorias).
DEFAULT_ICON = "tag"

# Ícones específicos das 7 categorias de sistema (feedback do usuário sobre
# o build-context-02: categorias precisam de ícone, não só cor/iniciais).
SYSTEM_CATEGORY_ICONS = {
    "Alimentação": "utensils",
    "Moradia": "house",
    "Transporte": "car",
    "Saúde": "heart-pulse",
    "Educação": "graduation-cap",
    "Lazer": "party-popper",
    "Outros": "tag",
}


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "categories",
        sa.Column("icon", sa.String(length=30), nullable=False, server_default=DEFAULT_ICON),
    )
    categories_table = sa.table(
        "categories", sa.column("name", sa.String), sa.column("icon", sa.String)
    )
    for name, icon in SYSTEM_CATEGORY_ICONS.items():
        op.execute(
            categories_table.update().where(categories_table.c.name == name).values(icon=icon)
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("categories", "icon")
