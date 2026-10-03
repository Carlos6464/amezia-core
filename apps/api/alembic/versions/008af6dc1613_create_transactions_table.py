"""create transactions table

Revision ID: 008af6dc1613
Revises: 7ddca8277a58
Create Date: 2026-08-09 14:16:02.723501

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '008af6dc1613'
down_revision: str | Sequence[str] | None = '7ddca8277a58'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

transaction_type_enum = postgresql.ENUM("income", "expense", name="transaction_type")
payment_status_enum = postgresql.ENUM("pending", "paid", "confirmed", name="payment_status")


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    transaction_type_enum.create(bind, checkfirst=True)
    payment_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("public_id", sa.String(length=26), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            sa.BigInteger(),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "type",
            postgresql.ENUM("income", "expense", name="transaction_type", create_type=False),
            nullable=False,
        ),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="BRL"),
        # Ciphertext AES (RN-05) via EncryptedString — sem length fixo, mesmo padrão de users.phone.
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "paid", "confirmed", name="payment_status", create_type=False
            ),
            nullable=False,
            server_default="confirmed",
        ),
        sa.Column("receipt_key", sa.String(length=255), nullable=True),
        sa.Column("installment_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("installment_number", sa.SmallInteger(), nullable=True),
        sa.Column("installment_total", sa.SmallInteger(), nullable=True),
        # FK para transaction_recurrences criada na próxima migration (7f4b3c3637ef) —
        # evita referência para frente a uma tabela que ainda não existe aqui.
        sa.Column("recurrence_rule_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("amount_cents > 0", name="ck_transactions_amount_positive"),
    )
    op.create_index("ux_transactions_public_id", "transactions", ["public_id"], unique=True)
    op.create_index(
        "ix_transactions_user_date", "transactions", ["user_id", sa.text("date DESC")]
    )
    op.create_index("ix_transactions_user_type", "transactions", ["user_id", "type"])
    op.create_index("ix_transactions_category", "transactions", ["category_id"])
    op.create_index(
        "ix_transactions_installment_group", "transactions", ["installment_group_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_transactions_installment_group", table_name="transactions")
    op.drop_index("ix_transactions_category", table_name="transactions")
    op.drop_index("ix_transactions_user_type", table_name="transactions")
    op.drop_index("ix_transactions_user_date", table_name="transactions")
    op.drop_index("ux_transactions_public_id", table_name="transactions")
    op.drop_table("transactions")
    payment_status_enum.drop(op.get_bind(), checkfirst=True)
    transaction_type_enum.drop(op.get_bind(), checkfirst=True)
