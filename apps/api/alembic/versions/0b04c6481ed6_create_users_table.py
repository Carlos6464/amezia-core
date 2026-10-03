"""create users table

Revision ID: 0b04c6481ed6
Revises: 3de30ec336e3
Create Date: 2026-08-08 13:16:33.976773

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0b04c6481ed6'
down_revision: str | Sequence[str] | None = '3de30ec336e3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role_enum = postgresql.ENUM("user", "admin", name="user_role")
user_language_enum = postgresql.ENUM("pt-BR", "en", name="user_language")


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    user_role_enum.create(bind, checkfirst=True)
    user_language_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM("user", "admin", name="user_role", create_type=False),
            nullable=False,
            server_default="user",
        ),
        sa.Column(
            "language",
            postgresql.ENUM("pt-BR", "en", name="user_language", create_type=False),
            nullable=False,
            server_default="pt-BR",
        ),
        sa.Column("oauth_provider", sa.String(length=20), nullable=True),
        sa.Column("oauth_id", sa.String(length=255), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "password_hash IS NOT NULL OR oauth_provider IS NOT NULL",
            name="ck_users_has_auth_method",
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index(
        "ux_users_oauth_provider_id",
        "users",
        ["oauth_provider", "oauth_id"],
        unique=True,
        postgresql_where=sa.text("oauth_provider IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ux_users_oauth_provider_id", table_name="users")
    op.drop_table("users")
    user_language_enum.drop(op.get_bind(), checkfirst=True)
    user_role_enum.drop(op.get_bind(), checkfirst=True)
