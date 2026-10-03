"""
Autor: Carlos Adriano
Data: 2026-09-09
Descrição: Backfill único (build-context-12 §3.3) — gera o embedding do
nome de toda categoria já existente (globais e privadas), pra checagem
de duplicata semântica no bot funcionar desde o dia 1, não só pra
categorias criadas depois deste build-context. Idempotente
(`IndexCategoryEmbeddingUseCase.execute` faz upsert por `source_id`) —
seguro rodar mais de uma vez. Roda uma vez, manualmente, fora do ciclo
normal do Alembic (precisa chamar a API do Gemini, não dá pra fazer em
SQL puro de migration):

    docker compose run --rm -v "$(pwd)/apps/api:/app" -v /app/.venv api \\
        sh -c "uv sync --locked && PYTHONPATH=/app .venv/bin/python scripts/backfill_category_embeddings.py"
"""

import asyncio
import logging

from sqlalchemy import select

from src.application.embedding.use_cases.index_category_embedding import (
    IndexCategoryEmbeddingUseCase,
)
from src.infrastructure.ai.gemini_client import GeminiEmbeddingClient
from src.infrastructure.database.models.category import Category as CategoryModel
from src.infrastructure.database.repositories.embedding_repository import (
    SqlAlchemyEmbeddingRepository,
)
from src.infrastructure.database.session import async_session_factory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Itera todas as categorias (uma query só, sem paginação —
    volume é baixo, dezenas por usuário) e indexa o embedding de cada
    uma, uma sessão de banco por categoria pra um erro isolado não
    derrubar o backfill inteiro.
    """
    async with async_session_factory() as session:
        result = await session.execute(select(CategoryModel.id, CategoryModel.user_id, CategoryModel.name))
        categories = result.all()

    logger.info("Backfilling embeddings for %d categories", len(categories))
    for category_id, user_id, name in categories:
        async with async_session_factory() as session:
            use_case = IndexCategoryEmbeddingUseCase(
                SqlAlchemyEmbeddingRepository(session), GeminiEmbeddingClient()
            )
            try:
                await use_case.execute(user_id, category_id, name)
                await session.commit()
            except Exception:
                logger.exception("Failed to index embedding for category_id=%s (%s)", category_id, name)

    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
