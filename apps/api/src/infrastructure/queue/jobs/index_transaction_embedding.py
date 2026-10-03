import uuid

from src.application.embedding.use_cases.index_transaction_embedding import (
    IndexTransactionEmbeddingUseCase,
)
from src.infrastructure.ai.gemini_client import GeminiEmbeddingClient
from src.infrastructure.database.repositories.embedding_repository import (
    SqlAlchemyEmbeddingRepository,
)
from src.infrastructure.database.session import async_session_factory


async def index_transaction_embedding(
    ctx: dict, user_id: str, transaction_id: int, content: str
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Job ARQ próprio (build-context-04 §2.4) — enfileirado
    pelo módulo de Transações (build-context-03) sempre que uma
    transação é criada ou atualizada. `user_id` chega como `str`
    (argumentos de job ARQ são serializados) e é convertido de volta
    para `UUID` aqui.
    """
    async with async_session_factory() as session:
        use_case = IndexTransactionEmbeddingUseCase(
            SqlAlchemyEmbeddingRepository(session), GeminiEmbeddingClient()
        )
        await use_case.execute(uuid.UUID(user_id), transaction_id, content)
        await session.commit()


async def delete_transaction_embedding(ctx: dict, transaction_id: int) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Job ARQ próprio — enfileirado pelo módulo de Transações ao
    excluir uma transação, para o RAG não continuar oferecendo contexto
    sobre um gasto que não existe mais.
    """
    async with async_session_factory() as session:
        use_case = IndexTransactionEmbeddingUseCase(
            SqlAlchemyEmbeddingRepository(session), GeminiEmbeddingClient()
        )
        await use_case.remove(transaction_id)
        await session.commit()
