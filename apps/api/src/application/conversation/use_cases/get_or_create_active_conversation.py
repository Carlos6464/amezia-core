import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.application.conversation.use_cases.create_conversation import (
    CreateConversationInput,
    CreateConversationUseCase,
)
from src.domain.conversation.entities import Conversation
from src.domain.conversation.repository import ConversationRepository
from src.domain.conversation.value_objects import ConversationChannel


@dataclass
class GetOrCreateActiveConversationInput:
    user_id: uuid.UUID
    channel: ConversationChannel = ConversationChannel.WEB


class GetOrCreateActiveConversationUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Mecanismo da "janela de continuação de 24h" (PRD §6.5) —
    reaproveita a conversa mais recente do usuário no canal pedido cujo
    `last_message_at` esteja a menos de `active_window_hours`; senão,
    cria uma nova (quando `create_if_missing=True`). Reaproveitado pelo
    Bot WhatsApp (build-context-07) no modo Chat, com `channel=whatsapp`.
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        create_conversation_use_case: CreateConversationUseCase,
        active_window_hours: int,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._create_conversation_use_case = create_conversation_use_case
        self._active_window_hours = active_window_hours

    async def execute(
        self, input_data: GetOrCreateActiveConversationInput, *, create_if_missing: bool = True
    ) -> Conversation | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: `create_if_missing=False` é o "modo leitura" usado por
        `GET /conversations/active` — devolve `None` em vez de criar uma
        conversa só porque o frontend perguntou se existe uma ativa.
        """
        active_since = datetime.now(UTC) - timedelta(hours=self._active_window_hours)
        existing = await self._conversation_repository.get_most_recent_active(
            input_data.user_id, input_data.channel, active_since
        )
        if existing is not None:
            return existing

        if not create_if_missing:
            return None

        return await self._create_conversation_use_case.execute(
            CreateConversationInput(user_id=input_data.user_id, channel=input_data.channel)
        )
