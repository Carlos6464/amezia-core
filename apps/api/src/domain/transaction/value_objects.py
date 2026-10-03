from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from src.domain.transaction.exceptions import (
    InvalidTransactionAmountError,
    InvalidTransactionPeriodError,
)


class TransactionType(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Tipo de lançamento financeiro — receita ou despesa.
    """

    INCOME = "income"
    EXPENSE = "expense"


class PaymentStatus(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Status de pagamento de uma transação (escopo expandido do
    build-context-03, revisado no mesmo dia a pedido do usuário — só dois
    estados, sem "confirmado": PENDING é um lançamento previsto ainda não
    pago; PAID (default) é o registro definitivo — mantém o comportamento
    histórico do MVP de que toda transação já representa dinheiro
    movimentado, a menos que o usuário marque explicitamente como
    pendente.
    """

    PENDING = "pending"
    PAID = "paid"


class RecurrenceFrequency(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Frequência de materialização de uma RecurrenceRule (ver
    domain/transaction/entities.py::RecurrenceRule).
    """

    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


@dataclass(frozen=True)
class Money:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Value object monetário — nunca representa valor como
    float. Guarda a unidade mínima (centavos) e a moeda; a conversão
    de/para Decimal só acontece nas fronteiras from_decimal/to_decimal.
    """

    amount_cents: int
    currency: str = "BRL"

    def __post_init__(self) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Valida que o valor é positivo — amount_cents <= 0
        nunca representa uma transação válida.
        """
        if self.amount_cents <= 0:
            raise InvalidTransactionAmountError(str(self.amount_cents))

    @classmethod
    def from_decimal(cls, amount: Decimal, currency: str = "BRL") -> "Money":
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Converte um Decimal (2 casas, unidade cheia — ex.
        50.90) vindo da borda HTTP para centavos, arredondando meio para
        cima quando necessário.
        """
        cents = int((amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        return cls(amount_cents=cents, currency=currency)

    def to_decimal(self) -> Decimal:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Converte de volta para Decimal (2 casas) — usado ao
        montar a resposta HTTP.
        """
        return (Decimal(self.amount_cents) / 100).quantize(Decimal("0.01"))

    def __add__(self, other: "Money") -> "Money":
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Soma dois valores monetários da mesma moeda — usado ao
        agregar o summary da listagem.
        """
        if self.currency != other.currency:
            raise ValueError("Cannot add Money with different currencies")
        return Money(amount_cents=self.amount_cents + other.amount_cents, currency=self.currency)


def _last_day_of_month(year: int, month: int) -> int:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Último dia do mês informado — usado por Period.date_range()
    e por add_months() para não estourar para o mês seguinte.
    """
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timedelta(days=1)).day


def add_months(base: date, months: int) -> date:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Soma N meses a uma data, preservando o dia quando possível
    e caindo no último dia do mês de destino quando o dia original não
    existir nele (ex.: 31/01 + 1 mês -> 28/02 ou 29/02, conforme o ano).
    Usado na geração de parcelas (mensal) e no avanço de recorrências
    mensais/anuais (Seção 2.7 do build-context-03).
    """
    total_month_index = base.month - 1 + months
    year = base.year + total_month_index // 12
    month = total_month_index % 12 + 1
    day = min(base.day, _last_day_of_month(year, month))
    return date(year, month, day)


def advance_occurrence(current: date, frequency: "RecurrenceFrequency") -> date:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Calcula a próxima data de ocorrência de uma RecurrenceRule
    a partir da frequência — reaproveitado tanto por
    CreateRecurringTransactionUseCase (avança logo após materializar a
    1ª ocorrência) quanto pelo job ARQ cron generate_recurring_transactions
    (avança a cada ocorrência subsequente), para não duplicar a regra em
    dois lugares.
    """
    if frequency == RecurrenceFrequency.WEEKLY:
        return current + timedelta(weeks=1)
    if frequency == RecurrenceFrequency.MONTHLY:
        return add_months(current, 1)
    return add_months(current, 12)


@dataclass(frozen=True)
class Period:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Período de filtro (ano, mês opcional) usado pelo
    ListTransactionsUseCase para computar o intervalo [primeiro_dia,
    último_dia]. Mês ausente cobre o ano inteiro.
    """

    year: int
    month: int | None = None

    def __post_init__(self) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Valida que o mês, quando informado, está no intervalo
        1-12.
        """
        if self.month is not None and not (1 <= self.month <= 12):
            raise InvalidTransactionPeriodError(str(self.month))

    def date_range(self) -> tuple[date, date]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Calcula o intervalo [primeiro_dia, último_dia] do
        período — mês específico ou o ano inteiro quando month é None.
        """
        if self.month is None:
            return date(self.year, 1, 1), date(self.year, 12, 31)
        last_day = _last_day_of_month(self.year, self.month)
        return date(self.year, self.month, 1), date(self.year, self.month, last_day)
