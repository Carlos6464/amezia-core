import uuid
from dataclasses import dataclass
from datetime import date

from src.application.transaction.dtos import CategorySummary, TransactionWithCategory
from src.domain.category.entities import Category
from src.domain.transaction.entities import RecurrenceRule, Transaction
from src.domain.transaction.repository import RecurrenceRuleRepository, TransactionRepository
from src.domain.transaction.value_objects import (
    Money,
    PaymentStatus,
    RecurrenceFrequency,
    TransactionType,
    advance_occurrence,
)


@dataclass
class CreateRecurringTransactionInput:
    user_id: uuid.UUID
    category: Category
    type: TransactionType
    amount: Money
    description: str
    status: PaymentStatus
    start_date: date
    frequency: RecurrenceFrequency
    end_date: date | None


class CreateRecurringTransactionUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Cria uma RecurrenceRule (recorrência indefinida, "até
    cancelar") e materializa a primeira ocorrência de forma síncrona —
    o usuário vê o primeiro lançamento na hora, sem esperar o job ARQ
    cron rodar. Só essa 1ª ocorrência recebe o `status` escolhido no
    formulário (pode nascer paga, com comprovante); as ocorrências
    seguintes ficam a cargo do job generate_recurring_transactions
    (build-context-03 §2.7), que sempre as materializa como `PENDING`
    (ajuste de 2026-08-09 — ver `GenerateDueRecurrencesUseCase`), nunca
    herdando o status da regra. Chamado internamente por
    CreateTransactionUseCase quando o corpo da requisição traz
    `recurrence` — não tem endpoint HTTP próprio de criação (só
    `GET`/`DELETE /transactions/recurrences*`).
    """

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        recurrence_rule_repository: RecurrenceRuleRepository,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._recurrence_rule_repository = recurrence_rule_repository

    async def execute(self, input_data: CreateRecurringTransactionInput) -> TransactionWithCategory:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Persiste a regra com `next_occurrence_date` já
        avançado para a ocorrência seguinte (a primeira acabou de ser
        materializada abaixo) — se essa próxima data já passar do
        `end_date` informado, a regra nasce inativa (recorrência de uma
        ocorrência só, ex.: frequência mensal com fim no mês seguinte).
        """
        rule = RecurrenceRule(
            user_id=input_data.user_id,
            category_id=input_data.category.id,
            type=input_data.type,
            amount=input_data.amount,
            description=input_data.description,
            frequency=input_data.frequency,
            start_date=input_data.start_date,
            next_occurrence_date=input_data.start_date,
            end_date=input_data.end_date,
        )
        created_rule = await self._recurrence_rule_repository.create(rule)

        first_occurrence = Transaction(
            user_id=input_data.user_id,
            category_id=input_data.category.id,
            type=input_data.type,
            amount=input_data.amount,
            description=input_data.description,
            date=input_data.start_date,
            status=input_data.status,
            recurrence_rule_id=created_rule.id,
        )
        created_transaction = await self._transaction_repository.create(first_occurrence)

        next_date = advance_occurrence(input_data.start_date, input_data.frequency)
        if created_rule.end_date is not None and next_date > created_rule.end_date:
            created_rule.active = False
        else:
            created_rule.next_occurrence_date = next_date
        await self._recurrence_rule_repository.update(created_rule)

        return TransactionWithCategory(
            transaction=created_transaction,
            category=CategorySummary.from_entity(input_data.category),
        )
