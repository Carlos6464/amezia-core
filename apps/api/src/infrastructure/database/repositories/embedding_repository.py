from __future__ import annotations

import uuid

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import select

from src.domain.embedding.entities import Embedding as EmbeddingEntity
from src.domain.embedding.entities import EmbeddingSourceType
from src.domain.embedding.repository import EmbeddingMatch
from src.infrastructure.database.models.embedding import Embedding as EmbeddingModel


class SqlAlchemyEmbeddingRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Implementação concreta de EmbeddingRepository via
    SQLAlchemy async + pgvector. `search_similar` sempre filtra por
    `user_id` (RN-01) antes de rankear por distância de cosseno — nenhum
    usuário recebe contexto injetado a partir de dados de outro usuário.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, embedding: EmbeddingEntity) -> EmbeddingEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Upsert idempotente via `ON CONFLICT (source_type,
        source_id)` (build-context-04 §2.2) — reindexar a mesma origem
        (ex.: transação editada) atualiza o vetor/conteúdo existente em
        vez de duplicar a linha.
        """
        stmt = (
            pg_insert(EmbeddingModel)
            .values(
                user_id=embedding.user_id,
                source_type=embedding.source_type.value,
                source_id=embedding.source_id,
                content=embedding.content,
                embedding=embedding.embedding,
            )
            .on_conflict_do_update(
                index_elements=["source_type", "source_id"],
                set_={
                    "user_id": embedding.user_id,
                    "content": embedding.content,
                    "embedding": embedding.embedding,
                },
            )
            .returning(EmbeddingModel.id, EmbeddingModel.created_at)
        )
        result = await self._session.execute(stmt)
        row = result.one()
        await self._session.flush()
        return EmbeddingEntity(
            id=row.id,
            user_id=embedding.user_id,
            source_type=embedding.source_type,
            source_id=embedding.source_id,
            content=embedding.content,
            embedding=embedding.embedding,
            created_at=row.created_at,
        )

    async def delete_by_source(self, source_type: EmbeddingSourceType, source_id: int) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Remove o embedding de uma origem excluída (ex.:
        transação apagada) — evita que o RAG continue oferecendo
        contexto sobre dado que não existe mais. Idempotente: fonte sem
        embedding indexado não gera erro.
        """
        await self._session.execute(
            delete(EmbeddingModel).where(
                EmbeddingModel.source_type == source_type.value,
                EmbeddingModel.source_id == source_id,
            )
        )
        await self._session.flush()

    async def search_similar(
        self,
        user_id: uuid.UUID,
        query_vector: list[float],
        pool_size: int,
        threshold: float,
        top_k: int,
    ) -> list[EmbeddingMatch]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Busca por similaridade de cosseno em duas etapas
        (build-context-04 §2.3): (1) pool dos `pool_size` candidatos
        mais próximos do usuário, via índice HNSW (`ORDER BY embedding
        <=> query_vector`); (2) desse pool, filtra por `threshold` e
        devolve os `top_k` mais similares. `cosine_distance` do
        pgvector retorna distância (0 = idêntico); `similarity = 1 -
        distância`.
        """
        distance = EmbeddingModel.embedding.cosine_distance(query_vector)
        candidates = (
            select(
                EmbeddingModel.source_type,
                EmbeddingModel.source_id,
                EmbeddingModel.content,
                (1 - distance).label("similarity"),
            )
            .where(EmbeddingModel.user_id == user_id)
            .order_by(distance)
            .limit(pool_size)
            .subquery()
        )
        result = await self._session.execute(
            select(candidates)
            .where(candidates.c.similarity >= threshold)
            .order_by(candidates.c.similarity.desc())
            .limit(top_k)
        )
        return [
            EmbeddingMatch(
                source_type=EmbeddingSourceType(row.source_type),
                source_id=row.source_id,
                content=row.content,
                similarity=row.similarity,
            )
            for row in result.all()
        ]

    async def search_similar_categories(
        self,
        user_id: uuid.UUID,
        query_vector: list[float],
        threshold: float,
        top_k: int,
    ) -> list[EmbeddingMatch]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Checagem de duplicata semântica de categoria
        (build-context-12 §3.3/§3.1 passo 3) — mesmo mecanismo de
        `search_similar` (similaridade de cosseno via pgvector), mas o
        filtro é "minhas categorias privadas OU as globais"
        (`user_id = :user_id OR user_id IS NULL`) em vez de um único
        `user_id` estrito: categoria global não é dado de outro usuário
        (RN-01 não se aplica), é intencionalmente compartilhada. Sem
        etapa de pool + top_k separados como o RAG — volume de
        categorias por usuário é baixo (dezenas, não milhares), uma
        única passada já é barata.
        """
        distance = EmbeddingModel.embedding.cosine_distance(query_vector)
        result = await self._session.execute(
            select(
                EmbeddingModel.source_type,
                EmbeddingModel.source_id,
                EmbeddingModel.content,
                (1 - distance).label("similarity"),
            )
            .where(
                EmbeddingModel.source_type == EmbeddingSourceType.CATEGORY.value,
                (EmbeddingModel.user_id == user_id) | (EmbeddingModel.user_id.is_(None)),
                (1 - distance) >= threshold,
            )
            .order_by(distance)
            .limit(top_k)
        )
        return [
            EmbeddingMatch(
                source_type=EmbeddingSourceType(row.source_type),
                source_id=row.source_id,
                content=row.content,
                similarity=row.similarity,
            )
            for row in result.all()
        ]
