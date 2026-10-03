import uuid
from dataclasses import dataclass

from src.domain.conversation.entities import Conversation
from src.domain.conversation.repository import ConversationRepository
from src.domain.conversation.value_objects import ConversationChannel


@dataclass
class CreateConversationInput:
    user_id: uuid.UUID
    channel: ConversationChannel = ConversationChannel.WEB


class CreateConversationUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Cria uma conversa vazia (`title=None`) — usado tanto pelo
    endpoint `POST /conversations` quanto por
    `GetOrCreateActiveConversationUseCase`, quando não há conversa ativa
    dentro da janela de 24h.
    """

    def __init__(self, conversation_repository: ConversationRepository) -> None:
        self._conversation_repository = conversation_repository

    async def execute(self, input_data: CreateConversationInput) -> Conversation:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Monta a entidade `Conversation` (título nulo, sem
        mensagens ainda) e persiste.
        """
        conversation = Conversation(user_id=input_data.user_id, channel=input_data.channel)
        return await self._conversation_repository.create(conversation)
