from datetime import date

from src.domain.transaction.entities import RecurrenceRule, Transaction
from src.domain.transaction.repository import RecurrenceRuleRepository, TransactionRepository
from src.domain.transaction.value_objects import PaymentStatus, advance_occurrence


class GenerateDueRecurrencesUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Materializa a próxima ocorrência de cada RecurrenceRule
    ativa cujo `next_occurrence_date` já chegou — chamado pelo job ARQ
    cron diário `generate_recurring_transactions`, nunca por uma rota
    HTTP. Mesma mecânica que CreateRecurringTransactionUseCase usa para
    a 1ª ocorrência (materializa, avança a data, encerra a regra se
    passar do `end_date`), reaproveitada aqui para as ocorrências
    seguintes (build-context-03 §2.7).
    """

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        recurrence_rule_repository: RecurrenceRuleRepository,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._recurrence_rule_repository = recurrence_rule_repository

    async def execute(self, as_of: date) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Retorna quantas transações foram geradas nesta
        execução — usado só para log/observabilidade do job.
        """
        due_rules = await self._recurrence_rule_repository.list_due(as_of)
        for rule in due_rules:
            await self._materialize(rule)
        return len(due_rules)

    async def _materialize(self, rule: RecurrenceRule) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Cria a transação da ocorrência e avança
        `next_occurrence_date` — ou encerra a regra (`active = False`)
        se a próxima data passar do `end_date` configurado. `status`
        sempre `PENDING`, nunca herdado do default da entidade
        (`PAID`) — uma ocorrência gerada automaticamente pelo job,
        sem nenhuma confirmação do usuário, não pode nascer como já
        paga (só a 1ª ocorrência, materializada na criação da
        recorrência, pode nascer com o status que o usuário escolheu).
        """
        transaction = Transaction(
            user_id=rule.user_id,
            category_id=rule.category_id,
            type=rule.type,
            amount=rule.amount,
            description=rule.description,
            date=rule.next_occurrence_date,
            status=PaymentStatus.PENDING,
            recurrence_rule_id=rule.id,
        )
        await self._transaction_repository.create(transaction)

        next_date = advance_occurrence(rule.next_occurrence_date, rule.frequency)
        if rule.end_date is not None and next_date > rule.end_date:
            rule.active = False
        else:
            rule.next_occurrence_date = next_date
        await self._recurrence_rule_repository.update(rule)
