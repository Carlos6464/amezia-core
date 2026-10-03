import uuid
from collections.abc import Callable
from dataclasses import dataclass

from src.application.transaction.dtos import CategorySummary, TransactionWithCategory
from src.domain.category.repository import CategoryRepository
from src.domain.shared.value_objects import PublicId
from src.domain.transaction.exceptions import TransactionNotFoundError
from src.domain.transaction.repository import TransactionRepository
from src.infrastructure.storage.backblaze_client import BackblazeStorageClient


@dataclass
class DeleteReceiptInput:
    user_id: uuid.UUID
    public_id: PublicId


class DeleteReceiptUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Remove o comprovante anexado a uma transação — apaga o
    objeto do Backblaze B2 e limpa `receipt_key`. No-op (sem erro, sem
    tocar no Backblaze) se a transação já não tiver comprovante — o
    client de storage só é instanciado quando de fato há algo a apagar,
    para não exigir Backblaze configurado num delete que na prática não
    precisa dele.
    """

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        category_repository: CategoryRepository,
        storage_client_factory: Callable[[], BackblazeStorageClient],
    ) -> None:
        self._transaction_repository = transaction_repository
        self._category_repository = category_repository
        self._storage_client_factory = storage_client_factory

    async def execute(self, input_data: DeleteReceiptInput) -> TransactionWithCategory:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: `TransactionNotFoundError` (404) tanto para
        inexistente quanto de outro usuário (RN-01).
        """
        transaction = await self._transaction_repository.get_by_public_id(
            input_data.user_id, input_data.public_id
        )
        if transaction is None:
            raise TransactionNotFoundError(str(input_data.public_id))

        if transaction.receipt_key is not None:
            self._storage_client_factory().delete(transaction.receipt_key)
            transaction.receipt_key = None
            transaction = await self._transaction_repository.update(transaction)

        category = await self._category_repository.get_by_id(transaction.category_id)
        return TransactionWithCategory(
            transaction=transaction, category=CategorySummary.from_entity(category)
        )
