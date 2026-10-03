import uuid

from src.application.transaction.dtos import CategorySummary, RecurrenceWithCategory
from src.domain.category.repository import CategoryRepository
from src.domain.transaction.repository import RecurrenceRuleRepository


class ListRecurrencesUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Lista as regras de recorrência ativas do usuário
    autenticado — usado no formulário de edição para mostrar o banner
    "gerada automaticamente por..." e permitir cancelar.
    """

    def __init__(
        self,
        recurrence_rule_repository: RecurrenceRuleRepository,
        category_repository: CategoryRepository,
    ) -> None:
        self._recurrence_rule_repository = recurrence_rule_repository
        self._category_repository = category_repository

    async def execute(self, user_id: uuid.UUID) -> list[RecurrenceWithCategory]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Hidrata cada regra com o resumo de categoria via um
        único lookup em lote (`list_visible_to`), mesmo padrão de
        ListTransactionsUseCase.
        """
        rules = await self._recurrence_rule_repository.list_active_for_user(user_id)
        if not rules:
            return []

        categories = await self._category_repository.list_visible_to(user_id)
        category_by_id = {category.id: category for category in categories}

        return [
            RecurrenceWithCategory(
                rule=rule, category=CategorySummary.from_entity(category_by_id[rule.category_id])
            )
            for rule in rules
        ]
