from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Import só para checagem de tipo (`from __future__ import annotations` acima
    # torna as anotações preguiçosas) — `value_objects.py` importa deste módulo,
    # um import de verdade aqui em cima criaria import circular.
    from src.domain.transaction.value_objects import RecurrenceFrequency


class TransactionNotFoundError(Exception):
    pass


class InvalidTransactionAmountError(Exception):
    pass


class InvalidTransactionPeriodError(Exception):
    pass


class RecurrenceRuleNotFoundError(Exception):
    pass


class InvalidReceiptFileError(Exception):
    pass


class ExpenseParsingFailedError(Exception):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Levantada por `RegisterExpenseViaBotUseCase`
    (build-context-07 §2.9) quando a IA não devolve um JSON válido, ou o
    `amount` extraído é ausente/inválido — `HandleExpenseStateUseCase`
    captura para compor a mensagem `expense.parse_failed`.
    """


class NoCategoryMatchError(Exception):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Levantada por `RegisterExpenseViaBotUseCase`
    (build-context-12 §3.1) quando a IA extrai valor/descrição/data com
    sucesso mas nenhuma categoria da lista enviada é uma boa combinação
    (a IA sinaliza isso devolvendo `"category": null`, em vez de ser
    forçada a chutar uma). Carrega o rascunho já extraído — incluindo
    `installment_total`/`recurrence_frequency`/`amount_is_total`, quando
    a própria mensagem original já deixou isso claro (ex.: "em 10
    vezes", "todo mês") — para `HandleExpenseStateUseCase` perguntar só
    a categoria de volta ao usuário, sem perder nem reperguntar o que já
    foi entendido. Diferente de `ExpenseParsingFailedError`, que
    representa uma falha real de parsing (JSON inválido ou valor
    ausente).
    """

    def __init__(
        self,
        amount: Decimal,
        description: str,
        expense_date: date,
        installment_total: int | None = None,
        recurrence_frequency: RecurrenceFrequency | None = None,
        amount_is_total: bool | None = None,
    ) -> None:
        super().__init__("no category match for extracted expense")
        self.amount = amount
        self.description = description
        self.expense_date = expense_date
        self.installment_total = installment_total
        self.recurrence_frequency = recurrence_frequency
        self.amount_is_total = amount_is_total

