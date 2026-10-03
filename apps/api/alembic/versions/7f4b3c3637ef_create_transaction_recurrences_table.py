"""create transaction recurrences table

Revision ID: 7f4b3c3637ef
Revises: 008af6dc1613
Create Date: 2026-08-09 14:16:07.552113

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7f4b3c3637ef'
down_revision: str | Sequence[str] | None = '008af6dc1613'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

recurrence_frequency_enum = postgresql.ENUM("weekly", "monthly", "yearly", name="recurrence_frequency")


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    recurrence_frequency_enum.create(bind, checkfirst=True)

    op.create_table(
        "transaction_recurrences",
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
        # Ciphertext AES (RN-05) — mesmo campo/regra de transactions.description.
        sa.Column("description", sa.String(), nullable=False),
        sa.Column(
            "frequency",
            postgresql.ENUM(
                "weekly", "monthly", "yearly", name="recurrence_frequency", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("next_occurrence_date", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("amount_cents > 0", name="ck_transaction_recurrences_amount_positive"),
    )
    op.create_index(
        "ux_transaction_recurrences_public_id", "transaction_recurrences", ["public_id"], unique=True
    )
    op.create_index(
        "ix_transaction_recurrences_due",
        "transaction_recurrences",
        ["active", "next_occurrence_date"],
    )

    # transactions.recurrence_rule_id nasceu na migration anterior (008af6dc1613) sem FK,
    # porque esta tabela ainda não existia — a constraint fecha aqui.
    op.create_foreign_key(
        "fk_transactions_recurrence_rule_id",
        "transactions",
        "transaction_recurrences",
        ["recurrence_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_transactions_recurrence_rule", "transactions", ["recurrence_rule_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_transactions_recurrence_rule", table_name="transactions")
    op.drop_constraint("fk_transactions_recurrence_rule_id", "transactions", type_="foreignkey")
    op.drop_index("ix_transaction_recurrences_due", table_name="transaction_recurrences")
    op.drop_index("ux_transaction_recurrences_public_id", table_name="transaction_recurrences")
    op.drop_table("transaction_recurrences")
    recurrence_frequency_enum.drop(op.get_bind(), checkfirst=True)
