import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from src.domain.shared.value_objects import PublicId
from src.domain.transaction.value_objects import (
    Money,
    PaymentStatus,
    RecurrenceFrequency,
    TransactionType,
)


@dataclass
class Transaction:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Entidade de domínio de um lançamento financeiro (receita
    ou despesa) de um usuário. Parcelamento e recorrência (build-context-03
    §2.7) são representados por campos opcionais — cada parcela/ocorrência
    é uma Transaction independente, editável/excluível sozinha, não um
    agregado com filhos.
    """

    user_id: uuid.UUID
    category_id: int
    type: TransactionType
    amount: Money
    description: str
    date: date
    status: PaymentStatus = PaymentStatus.PAID
    payment_method: str | None = None
    receipt_key: str | None = None
    paid_at: date | None = None
    installment_group_id: uuid.UUID | None = None
    installment_number: int | None = None
    installment_total: int | None = None
    recurrence_rule_id: int | None = None
    id: int | None = None
    public_id: PublicId = field(default_factory=PublicId.generate)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_installment(self) -> bool:
        return self.installment_group_id is not None

    @property
    def is_recurring_occurrence(self) -> bool:
        return self.recurrence_rule_id is not None


@dataclass
class RecurrenceRule:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Regra de recorrência indefinida ("até cancelar") — não
    pré-gera transações futuras; um job ARQ cron diário
    (generate_recurring_transactions) materializa uma Transaction por vez
    quando next_occurrence_date chega (build-context-03 §2.7). Cancelar
    (active=False) não apaga o histórico já materializado.
    """

    user_id: uuid.UUID
    category_id: int
    type: TransactionType
    amount: Money
    description: str
    frequency: RecurrenceFrequency
    start_date: date
    next_occurrence_date: date
    end_date: date | None = None
    active: bool = True
    id: int | None = None
    public_id: PublicId = field(default_factory=PublicId.generate)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
