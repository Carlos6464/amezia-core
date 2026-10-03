import uuid
from dataclasses import dataclass

from src.domain.shared.value_objects import PublicId
from src.domain.transaction.repository import TransactionRepository


@dataclass
class DeleteTransactionsBulkInput:
    user_id: uuid.UUID
    public_ids: list[PublicId]


@dataclass
class DeleteTransactionsBulkResult:
    deleted_count: int
    requested_count: int


class DeleteTransactionsBulkUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Exclui várias transações do próprio usuário numa única
    operação — idempotente por design: public_ids que não existem ou não
    pertencem ao usuário são silenciosamente ignorados (não geram erro).
    É assim que o usuário exclui um grupo de parcelas inteiro: seleciona
    todas as linhas com o mesmo `installment_group_id` na listagem.
    """

    def __init__(self, transaction_repository: TransactionRepository) -> None:
        self._transaction_repository = transaction_repository

    async def execute(self, input_data: DeleteTransactionsBulkInput) -> DeleteTransactionsBulkResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: `requested_count` reflete o que o cliente pediu;
        `deleted_count` o que de fato existia e pertencia ao usuário —
        a diferença entre os dois é informativa, não um erro.
        """
        deleted_count = await self._transaction_repository.delete_many(
            input_data.user_id, input_data.public_ids
        )
        return DeleteTransactionsBulkResult(
            deleted_count=deleted_count, requested_count=len(input_data.public_ids)
        )
