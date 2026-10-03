import uuid
from dataclasses import dataclass

from src.domain.conversation.exceptions import ConversationNotFoundError
from src.domain.conversation.repository import ConversationRepository
from src.domain.embedding.entities import EmbeddingSourceType
from src.domain.embedding.repository import EmbeddingRepository
from src.domain.shared.value_objects import PublicId


@dataclass
class DeleteConversationInput:
    user_id: uuid.UUID
    public_id: PublicId


class DeleteConversationUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-12
    Descrição: Exclui uma conversa do próprio usuário (RN-01) — usado
    pelo botão de excluir da lista de conversas (grid), replicado do
    layout do projeto irmão. `conversation_messages` é removida via
    `ON DELETE CASCADE`; os embeddings de cada mensagem (`source_type
    = conversation_message`) não têm FK física (fonte polimórfica,
    build-context-04 §2.2) e por isso são removidos explicitamente
    aqui antes de excluir a conversa, para o RAG não continuar
    oferecendo contexto de mensagens que não existem mais.
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        embedding_repository: EmbeddingRepository,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._embedding_repository = embedding_repository

    async def execute(self, input_data: DeleteConversationInput) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-12
        Descrição: `ConversationNotFoundError` (404) tanto para
        inexistente quanto de outro usuário.
        """
        conversation = await self._conversation_repository.get_by_public_id(
            input_data.user_id, input_data.public_id
        )
        if conversation is None:
            raise ConversationNotFoundError(str(input_data.public_id))

        messages = await self._conversation_repository.list_messages_after(
            conversation.id, after_message_id=None
        )
        for message in messages:
            await self._embedding_repository.delete_by_source(
                EmbeddingSourceType.CONVERSATION_MESSAGE, message.id
            )

        await self._conversation_repository.delete(input_data.user_id, input_data.public_id)
