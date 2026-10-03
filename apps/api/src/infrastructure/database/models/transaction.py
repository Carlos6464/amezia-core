import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base
from src.infrastructure.security.encrypted_string import EncryptedString

transaction_type_enum = ENUM("income", "expense", name="transaction_type", create_type=False)
payment_status_enum = ENUM("pending", "paid", name="payment_status", create_type=False)


class Transaction(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Model SQLAlchemy da tabela `transactions` — lançamentos
    financeiros (receita/despesa) de um usuário. `description` é
    persistido já criptografado (AES/Fernet, RN-05), transparente via
    `EncryptedString`. Parcelamento (`installment_*`) e recorrência
    (`recurrence_rule_id`) são campos opcionais — cada linha continua
    sendo uma transação independente (build-context-03 §2.7).
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_transactions_amount_positive"),
        Index("ux_transactions_public_id", "public_id", unique=True),
        Index("ix_transactions_user_date", "user_id", "date"),
        Index("ix_transactions_user_type", "user_id", "type"),
        Index("ix_transactions_category", "category_id"),
        Index("ix_transactions_installment_group", "installment_group_id"),
        Index("ix_transactions_recurrence_rule", "recurrence_rule_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(26), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    type: Mapped[str] = mapped_column(transaction_type_enum, nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="BRL")
    description: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(payment_status_enum, nullable=False, server_default="paid")
    payment_method: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    receipt_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paid_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    installment_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    installment_number: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    installment_total: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    recurrence_rule_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("transaction_recurrences.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
