import uuid

from src.application.conversation.dtos import ConversationListResult, ConversationSummary
from src.domain.conversation.repository import ConversationRepository


class ListConversationsUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Lista paginada das conversas do usuário autenticado,
    ordenada por `last_message_at DESC NULLS LAST` (build-context-04
    §2.7), já acompanhada da última mensagem de cada uma (prévia da
    listagem).
    """

    def __init__(self, conversation_repository: ConversationRepository) -> None:
        self._conversation_repository = conversation_repository

    async def execute(
        self, user_id: uuid.UUID, page: int, page_size: int
    ) -> ConversationListResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Busca a página de conversas e, numa segunda query em
        lote (`get_last_messages`), a última mensagem de cada uma —
        monta o par `ConversationSummary` usado pela prévia da listagem.
        """
        conversations, total = await self._conversation_repository.list(user_id, page, page_size)
        last_messages = await self._conversation_repository.get_last_messages(
            [conversation.id for conversation in conversations if conversation.id is not None]
        )
        items = [
            ConversationSummary(
                conversation=conversation, last_message=last_messages.get(conversation.id)
            )
            for conversation in conversations
        ]
        return ConversationListResult(items=items, total=total)
