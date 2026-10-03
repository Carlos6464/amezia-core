import uuid

from src.application.conversation.dtos import ConversationMessageListResult
from src.domain.conversation.exceptions import ConversationNotFoundError
from src.domain.conversation.repository import ConversationRepository
from src.domain.shared.value_objects import PublicId


class ListConversationMessagesUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Lista paginada das mensagens de uma conversa, em ordem
    cronológica — valida a posse da conversa antes de listar (RN-01).
    """

    def __init__(self, conversation_repository: ConversationRepository) -> None:
        self._conversation_repository = conversation_repository

    async def execute(
        self, user_id: uuid.UUID, public_id: PublicId, page: int, page_size: int
    ) -> ConversationMessageListResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: `ConversationNotFoundError` (404) tanto para conversa
        inexistente quanto de outro usuário (RN-01) — só então lista as
        mensagens paginadas.
        """
        conversation = await self._conversation_repository.get_by_public_id(user_id, public_id)
        if conversation is None:
            raise ConversationNotFoundError(str(public_id))

        items, total = await self._conversation_repository.list_messages(
            conversation.id, page, page_size
        )
        return ConversationMessageListResult(items=items, total=total)
