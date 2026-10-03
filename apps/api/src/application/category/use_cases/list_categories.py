import uuid

from src.application.category.dtos import CategoryWithUsage
from src.domain.category.repository import CategoryRepository
from src.domain.transaction.repository import TransactionRepository


class ListCategoriesUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Retorna as categorias visíveis ao usuário autenticado —
    globais + privadas dele (RN-01) — endpoint único, sem paginação
    (dataset pequeno: no máximo 7 globais + 3 privadas). Cada categoria
    vem com o uso agregado (quantidade de transações + total
    movimentado, ver `CategoryWithUsage`) — dado que só existe a partir
    do build-context-03 (Transações), então esse enriquecimento não
    fazia parte da entrega original de Categorias.
    """

    def __init__(
        self, category_repository: CategoryRepository, transaction_repository: TransactionRepository
    ) -> None:
        self._category_repository = category_repository
        self._transaction_repository = transaction_repository

    async def execute(self, user_id: uuid.UUID) -> list[CategoryWithUsage]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Busca as categorias e a agregação de uso numa query
        cada (independentes, sem N+1 — a agregação já vem pronta por
        categoria, `usage_by_category` faz um `GROUP BY` só). Categoria
        sem nenhuma transação (ausente do dict de uso) recebe
        `transaction_count=0`/`total_amount_cents=0` explicitamente.
        """
        categories = await self._category_repository.list_visible_to(user_id)
        usage = await self._transaction_repository.usage_by_category(user_id)
        return [
            CategoryWithUsage(
                category=category,
                transaction_count=usage.get(category.id, (0, 0))[0],
                total_amount_cents=usage.get(category.id, (0, 0))[1],
            )
            for category in categories
        ]
