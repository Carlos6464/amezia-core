import uuid

from src.domain.conversation.ports import EmbeddingGeneratorPort
from src.domain.embedding.repository import EmbeddingMatch, EmbeddingRepository


class CheckCategoryDuplicateUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Checagem de duplicata semântica de categoria
    (build-context-12 §3.1 passo 3) — embeda o nome digitado pelo
    usuário no bot e busca a categoria mais parecida (globais + privadas
    do próprio usuário) via `EmbeddingRepository.search_similar_categories`.
    Mesmo mecanismo do RAG do Agente (`SearchRelevantContextUseCase`),
    escopo menor: sem pool/top_k, só o candidato mais próximo acima do
    limiar.
    """

    def __init__(
        self,
        embedding_repository: EmbeddingRepository,
        embedding_generator: EmbeddingGeneratorPort,
        threshold: float,
    ) -> None:
        self._embedding_repository = embedding_repository
        self._embedding_generator = embedding_generator
        self._threshold = threshold

    async def execute(self, user_id: uuid.UUID, typed_name: str) -> EmbeddingMatch | None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: `None` quando nenhuma categoria existente passa do
        limiar de similaridade — sinal de que `typed_name` é
        genuinamente uma categoria nova, não uma duplicata disfarçada.
        """
        vector = await self._embedding_generator.generate(typed_name)
        matches = await self._embedding_repository.search_similar_categories(
            user_id, vector, threshold=self._threshold, top_k=1
        )
        return matches[0] if matches else None
