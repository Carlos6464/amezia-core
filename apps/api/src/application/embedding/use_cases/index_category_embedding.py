import uuid

from src.domain.conversation.ports import EmbeddingGeneratorPort
from src.domain.embedding.entities import Embedding, EmbeddingSourceType
from src.domain.embedding.repository import EmbeddingRepository


class IndexCategoryEmbeddingUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Indexa o embedding do nome de uma categoria — ponto de
    integração cross-module chamado pelo módulo de Categorias
    (build-context-02) via job ARQ dedicado (`index_category_embedding`)
    sempre que uma categoria é criada ou renomeada (build-context-12
    §3.3). Base da checagem de duplicata semântica no registro de
    despesa via bot. `user_id=None` indexa uma categoria global (sem
    dono) — visível na busca de qualquer usuário (RN-01 não se aplica a
    dado compartilhado por design).
    """

    def __init__(
        self,
        embedding_repository: EmbeddingRepository,
        embedding_generator: EmbeddingGeneratorPort,
    ) -> None:
        self._embedding_repository = embedding_repository
        self._embedding_generator = embedding_generator

    async def execute(self, user_id: uuid.UUID | None, category_id: int, name: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Gera o vetor a partir só do nome da categoria (não há
        descrição/outro texto a embedar) e faz upsert (`UNIQUE
        (source_type, source_id)`) — chamado na criação e na renomeação.
        """
        vector = await self._embedding_generator.generate(name)
        await self._embedding_repository.upsert(
            Embedding(
                user_id=user_id,
                source_type=EmbeddingSourceType.CATEGORY,
                source_id=category_id,
                content=name,
                embedding=vector,
            )
        )

    async def remove(self, category_id: int) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Remove o embedding de uma categoria excluída — sem
        isso, a checagem de duplicata semântica (build-context-12 §3.1
        passo 3) continuaria sugerindo uma categoria que não existe mais.
        """
        await self._embedding_repository.delete_by_source(EmbeddingSourceType.CATEGORY, category_id)
