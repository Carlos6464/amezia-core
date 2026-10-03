import uuid

from src.application.embedding.use_cases.index_category_embedding import (
    IndexCategoryEmbeddingUseCase,
)
from src.infrastructure.ai.gemini_client import GeminiEmbeddingClient
from src.infrastructure.database.repositories.embedding_repository import (
    SqlAlchemyEmbeddingRepository,
)
from src.infrastructure.database.session import async_session_factory


async def index_category_embedding(
    ctx: dict, user_id: str | None, category_id: int, name: str
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Job ARQ próprio (build-context-12 §3.3) — enfileirado pelo
    módulo de Categorias (build-context-02) sempre que uma categoria é
    criada ou renomeada. `user_id` chega como `str | None` (argumentos de
    job ARQ são serializados) — `None` para categoria global.
    """
    async with async_session_factory() as session:
        use_case = IndexCategoryEmbeddingUseCase(
            SqlAlchemyEmbeddingRepository(session), GeminiEmbeddingClient()
        )
        await use_case.execute(uuid.UUID(user_id) if user_id else None, category_id, name)
        await session.commit()


async def delete_category_embedding(ctx: dict, category_id: int) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Job ARQ próprio — enfileirado por `DeleteCategoryUseCase`
    ao excluir uma categoria, para a checagem de duplicata semântica não
    continuar sugerindo uma categoria que não existe mais.
    """
    async with async_session_factory() as session:
        use_case = IndexCategoryEmbeddingUseCase(
            SqlAlchemyEmbeddingRepository(session), GeminiEmbeddingClient()
        )
        await use_case.remove(category_id)
        await session.commit()
