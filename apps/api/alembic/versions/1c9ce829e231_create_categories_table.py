"""create categories table

Revision ID: 1c9ce829e231
Revises: 0b04c6481ed6
Create Date: 2026-08-09 02:56:04.346117

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1c9ce829e231'
down_revision: str | Sequence[str] | None = '0b04c6481ed6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("public_id", sa.String(length=26), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("NOT is_system OR user_id IS NULL", name="ck_categories_system_no_owner"),
    )
    op.create_index("ix_categories_public_id", "categories", ["public_id"], unique=True)
    op.create_index("ix_categories_user_id", "categories", ["user_id"], unique=False)
    op.create_index(
        "ix_categories_user_name",
        "categories",
        ["user_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_categories_user_name", table_name="categories")
    op.drop_index("ix_categories_user_id", table_name="categories")
    op.drop_index("ix_categories_public_id", table_name="categories")
    op.drop_table("categories")
