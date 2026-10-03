from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from src.domain.conversation.entities import Conversation, ConversationMessage
from src.domain.conversation.value_objects import ConversationChannel
from src.domain.shared.value_objects import PublicId


class ConversationRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Interface de persistência do agregado Conversation
    (conversa + mensagens) — implementada em
    infrastructure/database/repositories/conversation_repository.py.
    Toda operação escopada a um usuário recebe `user_id` explicitamente
    e filtra por ele (RN-01); os métodos de mensagem recebem
    `conversation_id` já validado como pertencente ao usuário por quem
    chama, não repetem o filtro de novo.
    """

    async def create(self, conversation: Conversation) -> Conversation: ...

    async def get_by_id(self, id: int) -> Conversation | None: ...

    async def get_by_public_id(
        self, user_id: uuid.UUID, public_id: PublicId
    ) -> Conversation | None: ...

    async def get_most_recent_active(
        self, user_id: uuid.UUID, channel: ConversationChannel, active_since: datetime
    ) -> Conversation | None: ...

    async def list(
        self, user_id: uuid.UUID, page: int, page_size: int
    ) -> tuple[list[Conversation], int]: ...

    async def update(self, conversation: Conversation) -> Conversation: ...

    async def delete(self, user_id: uuid.UUID, public_id: PublicId) -> bool: ...

    async def add_message(self, message: ConversationMessage) -> ConversationMessage: ...

    async def get_message_by_id(self, id: int) -> ConversationMessage | None: ...

    async def list_messages(
        self, conversation_id: int, page: int, page_size: int
    ) -> tuple[list[ConversationMessage], int]: ...

    async def list_messages_after(
        self, conversation_id: int, after_message_id: int | None
    ) -> list[ConversationMessage]: ...

    async def get_last_messages(
        self, conversation_ids: list[int]
    ) -> dict[int, ConversationMessage]: ...

    async def list_distinct_active_user_ids_since(self, since: datetime) -> set[uuid.UUID]:
        """
        Usuários distintos com pelo menos 1 mensagem enviada desde
        `since` (`ConversationMessage.created_at`) — uma das 3 fontes
        de "usuário ativo" do DAU/MAU do Admin (build-context-11 §2.2).
        Cobre chat web e chat via bot (mesmo agregado `Conversation`,
        `channel` não importa aqui).
        """
        ...
