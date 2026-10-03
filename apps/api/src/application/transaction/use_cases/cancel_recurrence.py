import uuid
from dataclasses import dataclass

from src.domain.shared.value_objects import PublicId
from src.domain.transaction.exceptions import RecurrenceRuleNotFoundError
from src.domain.transaction.repository import RecurrenceRuleRepository


@dataclass
class CancelRecurrenceInput:
    user_id: uuid.UUID
    public_id: PublicId


class CancelRecurrenceUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Cancela (desativa) uma regra de recorrência do próprio
    usuário — `active = False`, o job ARQ cron passa a ignorá-la. Não
    apaga a regra nem as transações já materializadas (build-context-03
    §2.7): cancelar não é excluir histórico.
    """

    def __init__(self, recurrence_rule_repository: RecurrenceRuleRepository) -> None:
        self._recurrence_rule_repository = recurrence_rule_repository

    async def execute(self, input_data: CancelRecurrenceInput) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: `RecurrenceRuleNotFoundError` (404) tanto para
        inexistente quanto de outro usuário (RN-01).
        """
        rule = await self._recurrence_rule_repository.get_by_public_id(
            input_data.user_id, input_data.public_id
        )
        if rule is None:
            raise RecurrenceRuleNotFoundError(str(input_data.public_id))
        rule.active = False
        await self._recurrence_rule_repository.update(rule)
