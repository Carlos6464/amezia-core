import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.feedback.entities import Feedback as FeedbackEntity
from src.domain.feedback.value_objects import FeedbackChannel, FeedbackType
from src.infrastructure.database.models.feedback import Feedback as FeedbackModel


class SqlAlchemyFeedbackRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Implementação concreta de FeedbackRepository via SQLAlchemy
    async — traduz entre a entidade de domínio Feedback e o model ORM.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, feedback: FeedbackEntity) -> FeedbackEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Persiste um novo feedback — reaproveitado pelos canais
        web (router) e whatsapp (handler do bot).
        """
        model = self._to_model(feedback)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def list_by_user(
        self, user_id: uuid.UUID, page: int, page_size: int
    ) -> tuple[list[FeedbackEntity], int]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Histórico paginado do próprio usuário (RN-01), mais
        recentes primeiro — alimenta a aba "Histórico" da tela web.
        """
        count_result = await self._session.execute(
            select(func.count())
            .select_from(FeedbackModel)
            .where(FeedbackModel.user_id == user_id)
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            select(FeedbackModel)
            .where(FeedbackModel.user_id == user_id)
            .order_by(FeedbackModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._to_entity(model) for model in result.scalars().all()]
        return items, total

    async def list_paginated(
        self, page: int, page_size: int, channel: FeedbackChannel | None, search: str | None
    ) -> tuple[list[FeedbackEntity], int]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Lista paginada para o Admin, mais recentes primeiro.
        Filtro de canal e busca (assunto/mensagem) inteiros em SQL —
        `message`/`subject` deixaram de ser criptografados
        (build-context-08, RN-05 corrigida), então não precisam mais de
        filtragem em memória como no `description` de Transaction.
        """
        conditions = []
        if channel is not None:
            conditions.append(FeedbackModel.channel == channel.value)
        if search:
            pattern = f"%{search}%"
            conditions.append(
                FeedbackModel.message.ilike(pattern) | FeedbackModel.subject.ilike(pattern)
            )

        count_result = await self._session.execute(
            select(func.count()).select_from(FeedbackModel).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            select(FeedbackModel)
            .where(*conditions)
            .order_by(FeedbackModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._to_entity(model) for model in result.scalars().all()]
        return items, total

    async def count_total(self) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Total de feedbacks — alimenta o card de KPI da Visão
        Geral do Admin (GetAdminStatsUseCase).
        """
        result = await self._session.execute(select(func.count()).select_from(FeedbackModel))
        return result.scalar_one()

    def _to_entity(self, model: FeedbackModel) -> FeedbackEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Converte o model SQLAlchemy (infraestrutura) na
        entidade de domínio Feedback.
        """
        return FeedbackEntity(
            id=model.id,
            user_id=model.user_id,
            message=model.message,
            channel=FeedbackChannel(model.channel),
            type=FeedbackType(model.type),
            nps_score=model.nps_score,
            subject=model.subject,
            created_at=model.created_at,
        )

    def _to_model(self, entity: FeedbackEntity) -> FeedbackModel:
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Converte a entidade de domínio Feedback num model
        SQLAlchemy novo (ainda não persistido) — usado só por `create`.
        """
        return FeedbackModel(
            id=entity.id,
            user_id=entity.user_id,
            message=entity.message,
            channel=entity.channel.value,
            type=entity.type.value,
            nps_score=entity.nps_score,
            subject=entity.subject,
        )
