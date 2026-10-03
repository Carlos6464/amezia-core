import uuid
from dataclasses import dataclass

from src.application.conversation.use_cases.get_or_create_active_conversation import (
    GetOrCreateActiveConversationInput,
    GetOrCreateActiveConversationUseCase,
)
from src.application.shared.ports import JobEnqueuer
from src.domain.conversation.entities import Conversation, ConversationMessage
from src.domain.conversation.exceptions import ConversationNotFoundError
from src.domain.conversation.repository import ConversationRepository
from src.domain.conversation.value_objects import ConversationChannel, MessageRole
from src.domain.shared.value_objects import PublicId


@dataclass
class SendMessageInput:
    user_id: uuid.UUID
    content: str
    conversation_public_id: PublicId | None = None


@dataclass
class SendMessageResult:
    conversation: Conversation
    message: ConversationMessage


class SendMessageUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Persiste a mensagem do usuário e enfileira a geração da
    resposta — nunca chama nenhum provider de IA diretamente
    (build-context-04 §2.4). Sem `conversation_public_id`, resolve/cria a
    conversa ativa via `GetOrCreateActiveConversationUseCase` (janela de
    24h) antes de persistir.
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        get_or_create_active_use_case: GetOrCreateActiveConversationUseCase,
        job_enqueuer: JobEnqueuer,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._get_or_create_active_use_case = get_or_create_active_use_case
        self._job_enqueuer = job_enqueuer

    async def execute(self, input_data: SendMessageInput) -> SendMessageResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: `ConversationNotFoundError` (404) quando
        `conversation_public_id` é informado mas não existe ou pertence
        a outro usuário (RN-01). Atualiza `last_message_at` na hora (não
        espera o job) para a janela de 24h já refletir esta mensagem
        mesmo antes da resposta da IA chegar.
        """
        if input_data.conversation_public_id is not None:
            conversation = await self._conversation_repository.get_by_public_id(
                input_data.user_id, input_data.conversation_public_id
            )
            if conversation is None:
                raise ConversationNotFoundError(str(input_data.conversation_public_id))
        else:
            conversation = await self._get_or_create_active_use_case.execute(
                GetOrCreateActiveConversationInput(
                    user_id=input_data.user_id, channel=ConversationChannel.WEB
                )
            )

        message = await self._conversation_repository.add_message(
            ConversationMessage(
                conversation_id=conversation.id, role=MessageRole.USER, content=input_data.content
            )
        )

        conversation.last_message_at = message.created_at
        conversation = await self._conversation_repository.update(conversation)

        await self._job_enqueuer.enqueue_job("generate_ai_response", conversation.id, message.id)

        return SendMessageResult(conversation=conversation, message=message)
