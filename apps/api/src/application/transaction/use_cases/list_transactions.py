import uuid
from dataclasses import dataclass

from src.application.transaction.dtos import CategorySummary, TransactionWithCategory
from src.domain.category.repository import CategoryRepository
from src.domain.transaction.repository import TransactionFilters, TransactionRepository
from src.domain.user.repository import UserRepository


@dataclass
class TransactionListResult:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Resultado de ListTransactionsUseCase — items da página
    atual + total/soma do conjunto filtrado completo (não só a página) +
    teto mensal, quando o filtro resolve para um único mês.
    """

    items: list[TransactionWithCategory]
    total: int
    total_amount_cents: int
    budget_limit_cents: int | None
    budget_used_percentage: float | None


class ListTransactionsUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Lista paginada de transações do usuário autenticado, com
    filtros de tipo/status/período aplicados em SQL e busca textual `q`
    resolvida em memória — `description` é criptografado em repouso
    (RN-05), então não é possível `WHERE description ILIKE ...` contra o
    ciphertext; a mecânica de fato (join com categorias, decriptação
    transparente via EncryptedString, filtro e paginação em Python)
    mora em `SqlAlchemyTransactionRepository`, este use case só decide
    *que* isso precisa acontecer (build-context-03 §2.5). Também calcula
    `summary` sobre o conjunto filtrado completo, nunca só a página
    corrente — inclui o teto mensal (§2.9) quando o período filtrado
    resolve para um único mês.
    """

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        category_repository: CategoryRepository,
        user_repository: UserRepository,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._category_repository = category_repository
        self._user_repository = user_repository

    async def execute(
        self, user_id: uuid.UUID, filters: TransactionFilters, page: int, page_size: int
    ) -> TransactionListResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Busca a página + o total/soma do conjunto completo, e
        hidrata cada item com o resumo da categoria via um único lookup
        em lote (`list_visible_to`) — evita N+1 consultas de categoria
        por transação.
        """
        items, total = await self._transaction_repository.list(user_id, filters, page, page_size)
        total_amount_cents = await self._transaction_repository.sum_amount(user_id, filters)

        categories = await self._category_repository.list_visible_to(user_id)
        category_by_id = {category.id: category for category in categories}

        results = [
            TransactionWithCategory(
                transaction=transaction,
                category=CategorySummary.from_entity(category_by_id[transaction.category_id]),
            )
            for transaction in items
        ]

        budget_limit_cents, budget_used_percentage = await self._compute_budget(
            user_id, filters, total_amount_cents
        )

        return TransactionListResult(
            items=results,
            total=total,
            total_amount_cents=total_amount_cents,
            budget_limit_cents=budget_limit_cents,
            budget_used_percentage=budget_used_percentage,
        )

    async def _compute_budget(
        self, user_id: uuid.UUID, filters: TransactionFilters, total_amount_cents: int
    ) -> tuple[int | None, float | None]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Teto mensal só faz sentido comparado a exatamente um
        mês — período de ano inteiro ou sem filtro não tem "o mês" para
        comparar, viram (None, None). Sem teto configurado, o limite
        também vem None (percentual não pode ser calculado).
        """
        if filters.period is None or filters.period.month is None:
            return None, None

        user = await self._user_repository.get_by_id(user_id)
        if user is None or user.monthly_budget_cents is None:
            return None, None

        percentage = (total_amount_cents / user.monthly_budget_cents) * 100
        return user.monthly_budget_cents, percentage
