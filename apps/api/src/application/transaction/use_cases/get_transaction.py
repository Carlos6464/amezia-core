import uuid

from src.application.transaction.dtos import CategorySummary, TransactionWithCategory
from src.domain.category.repository import CategoryRepository
from src.domain.shared.value_objects import PublicId
from src.domain.transaction.exceptions import TransactionNotFoundError
from src.domain.transaction.repository import TransactionRepository


class GetTransactionUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Busca uma transação por public_id escopada ao usuário
    autenticado (RN-01) — usado no pré-preenchimento do formulário de
    edição. `category_id` (int interno) é resolvido via
    `CategoryRepository.get_by_id` (não `get_by_public_id`, que espera o
    ULID) para montar o resumo de categoria da resposta.
    """

    def __init__(
        self, transaction_repository: TransactionRepository, category_repository: CategoryRepository
    ) -> None:
        self._transaction_repository = transaction_repository
        self._category_repository = category_repository

    async def execute(self, user_id: uuid.UUID, public_id: PublicId) -> TransactionWithCategory:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: `TransactionNotFoundError` tanto para public_id
        inexistente quanto de outro usuário (RN-01) — a query do
        repositório já filtra por user_id, então a diferenciação nunca
        chega até aqui.
        """
        transaction = await self._transaction_repository.get_by_public_id(user_id, public_id)
        if transaction is None:
            raise TransactionNotFoundError(str(public_id))

        category = await self._category_repository.get_by_id(transaction.category_id)
        return TransactionWithCategory(
            transaction=transaction, category=CategorySummary.from_entity(category)
        )
