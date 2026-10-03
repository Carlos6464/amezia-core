import uuid

from src.domain.conversation.ports import EmbeddingGeneratorPort
from src.domain.embedding.entities import Embedding, EmbeddingSourceType
from src.domain.embedding.repository import EmbeddingRepository
from src.domain.transaction.entities import Transaction
from src.domain.transaction.value_objects import TransactionType


def build_transaction_content(transaction: Transaction, category_name: str) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Monta o texto-fonte indexado para uma transação (ex.:
    "Compra de R$ 60,00 em Alimentação em 14/06/2026: Padaria",
    build-context-04 §2.4) — chamado pelos use cases do módulo de
    Transações, que ainda têm os campos em texto plano, antes de
    enfileirar o job `index_transaction_embedding`.
    """
    label = "Compra" if transaction.type == TransactionType.EXPENSE else "Receita"
    amount = f"{transaction.amount.to_decimal():.2f}".replace(".", ",")
    date_str = transaction.date.strftime("%d/%m/%Y")
    return f"{label} de R$ {amount} em {category_name} em {date_str}: {transaction.description}"


class IndexTransactionEmbeddingUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Indexa (ou remove) o embedding de uma transação — ponto de
    integração cross-module chamado pelo módulo de Transações
    (build-context-03) via job ARQ dedicado (`index_transaction_embedding`)
    sempre que uma transação é criada, atualizada ou excluída
    (build-context-04 §2.4). O texto-fonte (`content`) é montado por quem
    chama, que ainda tem os campos em texto plano.
    """

    def __init__(
        self,
        embedding_repository: EmbeddingRepository,
        embedding_generator: EmbeddingGeneratorPort,
    ) -> None:
        self._embedding_repository = embedding_repository
        self._embedding_generator = embedding_generator

    async def execute(self, user_id: uuid.UUID, transaction_id: int, content: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Gera o vetor e faz upsert (`UNIQUE (source_type,
        source_id)`) — chamado na criação e na edição de uma transação.
        """
        vector = await self._embedding_generator.generate(content)
        await self._embedding_repository.upsert(
            Embedding(
                user_id=user_id,
                source_type=EmbeddingSourceType.TRANSACTION,
                source_id=transaction_id,
                content=content,
                embedding=vector,
            )
        )

    async def remove(self, transaction_id: int) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Remove o embedding de uma transação excluída — sem
        isso, o RAG continuaria oferecendo contexto sobre um gasto que o
        usuário já apagou.
        """
        await self._embedding_repository.delete_by_source(
            EmbeddingSourceType.TRANSACTION, transaction_id
        )
