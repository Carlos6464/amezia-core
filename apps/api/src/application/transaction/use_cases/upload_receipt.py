import uuid
from collections.abc import Callable
from dataclasses import dataclass

from src.application.transaction.dtos import CategorySummary, TransactionWithCategory
from src.domain.category.repository import CategoryRepository
from src.domain.shared.value_objects import PublicId
from src.domain.transaction.exceptions import InvalidReceiptFileError, TransactionNotFoundError
from src.domain.transaction.repository import TransactionRepository
from src.infrastructure.storage.backblaze_client import BackblazeStorageClient

ALLOWED_RECEIPT_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_RECEIPT_SIZE_BYTES = 5 * 1024 * 1024


@dataclass
class UploadReceiptInput:
    user_id: uuid.UUID
    public_id: PublicId
    filename: str
    content_type: str
    content: bytes


class UploadReceiptUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Envia o comprovante ao Backblaze B2 e grava `receipt_key`
    na transação (build-context-03 §2.8). Valida tipo/tamanho no
    servidor — nunca confia só no `accept` do `<input>` do cliente.
    Substitui o comprovante anterior, se houver (remove o objeto antigo
    do bucket antes de subir o novo).
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

    async def execute(self, input_data: UploadReceiptInput) -> TransactionWithCategory:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: `InvalidReceiptFileError` (422) para tipo/tamanho
        inválido; `TransactionNotFoundError` (404) para transação
        inexistente ou de outro usuário (RN-01) — validado antes de
        qualquer chamada ao Backblaze, para não gastar upload à toa.
        """
        if input_data.content_type not in ALLOWED_RECEIPT_CONTENT_TYPES:
            raise InvalidReceiptFileError(f"Unsupported content type: {input_data.content_type}")
        if len(input_data.content) > MAX_RECEIPT_SIZE_BYTES:
            raise InvalidReceiptFileError("File exceeds the 5MB limit")

        transaction = await self._transaction_repository.get_by_public_id(
            input_data.user_id, input_data.public_id
        )
        if transaction is None:
            raise TransactionNotFoundError(str(input_data.public_id))

        extension = (
            input_data.filename.rsplit(".", 1)[-1].lower() if "." in input_data.filename else "bin"
        )
        key = f"receipts/{input_data.user_id}/{input_data.public_id}/{uuid.uuid4()}.{extension}"

        storage_client = self._storage_client_factory()
        if transaction.receipt_key is not None:
            storage_client.delete(transaction.receipt_key)

        storage_client.upload(key, input_data.content, input_data.content_type)
        transaction.receipt_key = key
        updated = await self._transaction_repository.update(transaction)

        category = await self._category_repository.get_by_id(updated.category_id)
        return TransactionWithCategory(
            transaction=updated, category=CategorySummary.from_entity(category)
        )
