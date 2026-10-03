from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from src.domain.embedding.entities import Embedding, EmbeddingSourceType


@dataclass(frozen=True)
class EmbeddingMatch:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Um resultado da busca por similaridade — o embedding
    original não é necessário para quem consome o RAG, só a origem, o
    texto-fonte e o score (build-context-04 §2.3).
    """

    source_type: EmbeddingSourceType
    source_id: int
    content: str
    similarity: float


class EmbeddingRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Interface de persistência/busca de Embedding —
    implementada em
    infrastructure/database/repositories/embedding_repository.py.
    `search_similar` sempre filtra por `user_id` (RN-01) antes de
    rankear por distância de cosseno via pgvector.
    """

    async def upsert(self, embedding: Embedding) -> Embedding: ...

    async def delete_by_source(self, source_type: EmbeddingSourceType, source_id: int) -> None: ...

    async def search_similar(
        self,
        user_id: uuid.UUID,
        query_vector: list[float],
        pool_size: int,
        threshold: float,
        top_k: int,
    ) -> list[EmbeddingMatch]: ...

    async def search_similar_categories(
        self,
        user_id: uuid.UUID,
        query_vector: list[float],
        threshold: float,
        top_k: int,
    ) -> list[EmbeddingMatch]: ...
