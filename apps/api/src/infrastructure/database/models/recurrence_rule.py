import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base
from src.infrastructure.security.encrypted_string import EncryptedString

recurrence_frequency_enum = ENUM(
    "weekly", "monthly", "yearly", name="recurrence_frequency", create_type=False
)


class RecurrenceRule(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Model SQLAlchemy da tabela `transaction_recurrences` —
    regra de recorrência indefinida ("até cancelar"). Não guarda
    transações futuras: um job ARQ cron diário
    (generate_recurring_transactions) materializa uma `Transaction` por
    vez, avançando `next_occurrence_date` (build-context-03 §2.7).
    """

    __tablename__ = "transaction_recurrences"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_transaction_recurrences_amount_positive"),
        Index("ux_transaction_recurrences_public_id", "public_id", unique=True),
        Index("ix_transaction_recurrences_due", "active", "next_occurrence_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(26), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    type: Mapped[str] = mapped_column(
        ENUM("income", "expense", name="transaction_type", create_type=False), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="BRL")
    description: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    frequency: Mapped[str] = mapped_column(recurrence_frequency_enum, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_occurrence_date: Mapped[date] = mapped_column(Date, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
