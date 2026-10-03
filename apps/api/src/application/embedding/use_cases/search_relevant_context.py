import uuid

from src.domain.conversation.ports import EmbeddingGeneratorPort
from src.domain.embedding.repository import EmbeddingMatch, EmbeddingRepository


class SearchRelevantContextUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Embeda a pergunta do usuário e busca os trechos mais
    relevantes do seu próprio histórico (transações e mensagens
    anteriores) via `EmbeddingRepository.search_similar` — o motor do RAG
    (build-context-04 §2.3). `user_id` é sempre passado ao repositório,
    que filtra antes de rankear (RN-01).
    """

    def __init__(
        self,
        embedding_repository: EmbeddingRepository,
        embedding_generator: EmbeddingGeneratorPort,
        pool_size: int,
        threshold: float,
        top_k: int,
    ) -> None:
        self._embedding_repository = embedding_repository
        self._embedding_generator = embedding_generator
        self._pool_size = pool_size
        self._threshold = threshold
        self._top_k = top_k

    async def execute(self, user_id: uuid.UUID, query_text: str) -> list[EmbeddingMatch]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Pool de `pool_size` candidatos → filtro por
        `threshold` de similaridade de cosseno → `top_k` finais,
        conforme a query conceitual do build-context-04 §2.3.
        """
        query_vector = await self._embedding_generator.generate(query_text)
        return await self._embedding_repository.search_similar(
            user_id,
            query_vector,
            pool_size=self._pool_size,
            threshold=self._threshold,
            top_k=self._top_k,
        )
