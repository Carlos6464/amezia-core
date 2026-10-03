import uuid
from dataclasses import dataclass

from src.application.shared.ports import JobEnqueuer
from src.domain.shared.value_objects import PublicId
from src.domain.transaction.exceptions import TransactionNotFoundError
from src.domain.transaction.repository import RecurrenceRuleRepository, TransactionRepository


@dataclass
class DeleteTransactionInput:
    user_id: uuid.UUID
    public_id: PublicId
    delete_all_occurrences: bool = False


class DeleteTransactionUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Exclui uma transação do próprio usuário — mesma checagem
    de posse implícita na query do repositório (RN-01). Com
    `delete_all_occurrences=True`, o comportamento depende do tipo de
    agrupamento da transação: se é uma ocorrência de recorrência, exclui
    todo o histórico já materializado da regra e desativa a regra
    (equivalente a CancelRecurrenceUseCase, mas com o histórico apagado —
    decisão do usuário de 2026-08-10: "excluir todas" precisa parar a
    geração de ocorrências futuras também, senão o job cron geraria uma
    nova no próximo ciclo, contradizendo a intenção de "excluir tudo");
    se é uma parcela de compra parcelada, exclui todas as parcelas do
    grupo (`installment_group_id`) — aqui não há regra/gerador para
    desativar, todas as parcelas já foram materializadas na criação
    (decisão de 2026-08-11, mesmo pedido do usuário de 2026-08-10
    generalizado para parcelamento, que tinha ficado de fora da primeira
    rodada). Desde build-context-04 (2026-08-11), a exclusão de uma
    transação avulsa (`delete_all_occurrences=False`) também remove seu
    embedding indexado; os caminhos de grupo/lote não limpam embeddings
    nesta rodada (decisão de escopo registrada no DIARIO.md).
    """

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        recurrence_rule_repository: RecurrenceRuleRepository,
        job_enqueuer: JobEnqueuer,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._recurrence_rule_repository = recurrence_rule_repository
        self._job_enqueuer = job_enqueuer

    async def execute(self, input_data: DeleteTransactionInput) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: `TransactionNotFoundError` (404) tanto para
        inexistente quanto de outro usuário. Com
        `delete_all_occurrences=True`, carrega a transação primeiro (pra
        descobrir `recurrence_rule_id`/`installment_group_id`) em vez de
        ir direto pro `delete()` de uma linha só; sem recorrência nem
        parcelamento associados, o flag é ignorado e cai no caminho
        normal. Os dois agrupamentos são mutuamente exclusivos (RN do
        módulo, validada na criação), então só um dos dois `if`s abaixo
        chega a executar.
        """
        if input_data.delete_all_occurrences:
            transaction = await self._transaction_repository.get_by_public_id(
                input_data.user_id, input_data.public_id
            )
            if transaction is None:
                raise TransactionNotFoundError(str(input_data.public_id))
            if transaction.recurrence_rule_id is not None:
                await self._transaction_repository.delete_by_recurrence_rule(
                    input_data.user_id, transaction.recurrence_rule_id
                )
                rule = await self._recurrence_rule_repository.get_by_id(
                    transaction.recurrence_rule_id
                )
                if rule is not None and rule.user_id == input_data.user_id:
                    rule.active = False
                    await self._recurrence_rule_repository.update(rule)
                return
            if transaction.installment_group_id is not None:
                await self._transaction_repository.delete_by_installment_group(
                    input_data.user_id, transaction.installment_group_id
                )
                return

        transaction = await self._transaction_repository.get_by_public_id(
            input_data.user_id, input_data.public_id
        )
        if transaction is None:
            raise TransactionNotFoundError(str(input_data.public_id))

        deleted = await self._transaction_repository.delete(
            input_data.user_id, input_data.public_id
        )
        if not deleted:
            raise TransactionNotFoundError(str(input_data.public_id))

        await self._job_enqueuer.enqueue_job("delete_transaction_embedding", transaction.id)
