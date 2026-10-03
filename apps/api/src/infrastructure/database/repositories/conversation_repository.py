from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.domain.conversation.entities import Conversation as ConversationEntity
from src.domain.conversation.entities import ConversationMessage as ConversationMessageEntity
from src.domain.conversation.value_objects import AiProvider, ConversationChannel, MessageRole
from src.domain.shared.value_objects import PublicId
from src.infrastructure.database.models.conversation import Conversation as ConversationModel
from src.infrastructure.database.models.conversation import (
    ConversationMessage as ConversationMessageModel,
)


class SqlAlchemyConversationRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Implementação concreta de ConversationRepository via
    SQLAlchemy async — traduz entre as entidades de domínio
    Conversation/ConversationMessage e os models ORM. Operações
    escopadas a um usuário recebem `user_id` explicitamente e filtram
    `WHERE user_id = :user_id` (RN-01); métodos de mensagem recebem
    `conversation_id` já validado por quem chama.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, conversation: ConversationEntity) -> ConversationEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Persiste uma nova conversa — nasce sempre com
        `title=None` (só preenchido depois da 1ª resposta da IA).
        """
        model = ConversationModel(
            public_id=str(conversation.public_id),
            user_id=conversation.user_id,
            title=conversation.title,
            summary=conversation.summary,
            summarized_until_message_id=conversation.summarized_until_message_id,
            channel=conversation.channel.value,
            last_message_at=conversation.last_message_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, id: int) -> ConversationEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Busca por id interno, sem escopo de usuário — usado
        pelo job ARQ `generate_ai_response`, que já recebe o id
        confiável (nunca vindo direto do cliente HTTP).
        """
        model = await self._session.get(ConversationModel, id)
        return self._to_entity(model) if model else None

    async def get_by_public_id(
        self, user_id: uuid.UUID, public_id: PublicId
    ) -> ConversationEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Busca uma conversa por public_id, já escopada por
        user_id — conversa de outro usuário "não existe" do ponto de
        vista de quem pediu (RN-01).
        """
        result = await self._session.execute(
            select(ConversationModel).where(
                ConversationModel.user_id == user_id,
                ConversationModel.public_id == str(public_id),
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_most_recent_active(
        self, user_id: uuid.UUID, channel: ConversationChannel, active_since: datetime
    ) -> ConversationEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Busca a conversa mais recente do usuário no canal
        pedido cujo `last_message_at` esteja dentro da janela de
        continuação (build-context-04 §2.4) — base de
        `GetOrCreateActiveConversationUseCase`.
        """
        result = await self._session.execute(
            select(ConversationModel)
            .where(
                ConversationModel.user_id == user_id,
                ConversationModel.channel == channel.value,
                ConversationModel.last_message_at.is_not(None),
                ConversationModel.last_message_at >= active_since,
            )
            .order_by(ConversationModel.last_message_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list(
        self, user_id: uuid.UUID, page: int, page_size: int
    ) -> tuple[list[ConversationEntity], int]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Lista paginada, ordenada por `last_message_at DESC
        NULLS LAST` — conversas sem nenhuma mensagem ainda (recém
        criadas) aparecem por último.
        """
        count_result = await self._session.execute(
            select(func.count())
            .select_from(ConversationModel)
            .where(ConversationModel.user_id == user_id)
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            select(ConversationModel)
            .where(ConversationModel.user_id == user_id)
            .order_by(ConversationModel.last_message_at.desc().nulls_last())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._to_entity(model) for model in result.scalars().all()]
        return items, total

    async def update(self, conversation: ConversationEntity) -> ConversationEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Atualiza os campos mutáveis de uma conversa já
        existente — a entidade sempre vem de um `get_by_id`/
        `get_by_public_id` anterior, então `id` já está preenchido.
        """
        model = await self._session.get(ConversationModel, conversation.id)
        if model is None:
            raise ValueError(f"Conversation {conversation.id} not found")
        model.title = conversation.title
        model.summary = conversation.summary
        model.summarized_until_message_id = conversation.summarized_until_message_id
        model.last_message_at = conversation.last_message_at
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, user_id: uuid.UUID, public_id: PublicId) -> bool:
        """
        Autor: Carlos Adriano
        Data: 2026-08-12
        Descrição: Exclui a conversa (e, via `ON DELETE CASCADE`, suas
        mensagens) escopada por user_id (RN-01). Retorna `False` sem
        levantar exceção quando não encontra nada — quem chama decide
        se isso é um `ConversationNotFoundError`.
        """
        result = await self._session.execute(
            select(ConversationModel).where(
                ConversationModel.user_id == user_id,
                ConversationModel.public_id == str(public_id),
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def add_message(
        self, message: ConversationMessageEntity
    ) -> ConversationMessageEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Persiste uma mensagem (usuário ou assistente) — quem
        chama já garantiu que `conversation_id` pertence ao usuário
        certo (aggregate root, ver `domain/conversation/entities.py`).
        """
        model = ConversationMessageModel(
            public_id=str(message.public_id),
            conversation_id=message.conversation_id,
            role=message.role.value,
            content=message.content,
            provider_used=message.provider_used.value if message.provider_used else None,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_message_entity(model)

    async def get_message_by_id(self, id: int) -> ConversationMessageEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Busca por id interno — usado pelo job ARQ
        `generate_ai_response` para carregar a mensagem do usuário que
        disparou a geração da resposta.
        """
        model = await self._session.get(ConversationMessageModel, id)
        return self._to_message_entity(model) if model else None

    async def list_messages(
        self, conversation_id: int, page: int, page_size: int
    ) -> tuple[list[ConversationMessageEntity], int]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Lista paginada de mensagens em ordem cronológica
        (mais antiga primeiro) — usada pelo `GET
        /conversations/{public_id}/messages`.
        """
        count_result = await self._session.execute(
            select(func.count())
            .select_from(ConversationMessageModel)
            .where(ConversationMessageModel.conversation_id == conversation_id)
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            select(ConversationMessageModel)
            .where(ConversationMessageModel.conversation_id == conversation_id)
            .order_by(ConversationMessageModel.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._to_message_entity(model) for model in result.scalars().all()]
        return items, total

    async def list_messages_after(
        self, conversation_id: int, after_message_id: int | None
    ) -> list[ConversationMessageEntity]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Mensagens ainda não cobertas pelo `summary` da
        conversa (`after_message_id` é
        `conversations.summarized_until_message_id`) — sem paginação,
        usado para montar o prompt (janela recente verbatim) e para
        decidir se `SummarizeOldMessagesUseCase` deve rodar
        (build-context-04 §2.4).
        """
        conditions = [ConversationMessageModel.conversation_id == conversation_id]
        if after_message_id is not None:
            conditions.append(ConversationMessageModel.id > after_message_id)

        result = await self._session.execute(
            select(ConversationMessageModel).where(*conditions).order_by(
                ConversationMessageModel.id.asc()
            )
        )
        return [self._to_message_entity(model) for model in result.scalars().all()]

    async def get_last_messages(
        self, conversation_ids: list[int]
    ) -> dict[int, ConversationMessageEntity]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Última mensagem de cada conversa da lista, numa única
        query (`ROW_NUMBER() OVER (PARTITION BY conversation_id ...)`)
        em vez de N+1 — alimenta o trecho de prévia da listagem de
        conversas (`GET /conversations`).
        """
        if not conversation_ids:
            return {}

        row_number = (
            func.row_number()
            .over(
                partition_by=ConversationMessageModel.conversation_id,
                order_by=ConversationMessageModel.id.desc(),
            )
            .label("row_number")
        )
        ranked = (
            select(ConversationMessageModel, row_number)
            .where(ConversationMessageModel.conversation_id.in_(conversation_ids))
            .subquery()
        )
        message_alias = aliased(ConversationMessageModel, ranked)
        result = await self._session.execute(select(message_alias).where(ranked.c.row_number == 1))
        return {
            model.conversation_id: self._to_message_entity(model)
            for model in result.scalars().all()
        }

    async def list_distinct_active_user_ids_since(self, since: datetime) -> set[uuid.UUID]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Usuários distintos com pelo menos 1 mensagem enviada
        desde `since` — uma das 3 fontes de DAU/MAU do Admin
        (build-context-11 §2.2). Join simples `ConversationMessage` →
        `Conversation` pra chegar no `user_id` (mensagem não guarda
        `user_id` direto).
        """
        result = await self._session.execute(
            select(ConversationModel.user_id.distinct())
            .join(
                ConversationMessageModel,
                ConversationMessageModel.conversation_id == ConversationModel.id,
            )
            .where(ConversationMessageModel.created_at >= since)
        )
        return set(result.scalars().all())

    def _to_entity(self, model: ConversationModel) -> ConversationEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Converte o model SQLAlchemy na entidade de domínio
        Conversation — fronteira entre as duas camadas.
        """
        return ConversationEntity(
            id=model.id,
            public_id=PublicId(model.public_id),
            user_id=model.user_id,
            channel=ConversationChannel(model.channel),
            title=model.title,
            summary=model.summary,
            summarized_until_message_id=model.summarized_until_message_id,
            last_message_at=model.last_message_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_message_entity(self, model: ConversationMessageModel) -> ConversationMessageEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Converte o model SQLAlchemy na entidade de domínio
        ConversationMessage.
        """
        return ConversationMessageEntity(
            id=model.id,
            public_id=PublicId(model.public_id),
            conversation_id=model.conversation_id,
            role=MessageRole(model.role),
            content=model.content,
            provider_used=AiProvider(model.provider_used) if model.provider_used else None,
            created_at=model.created_at,
        )
