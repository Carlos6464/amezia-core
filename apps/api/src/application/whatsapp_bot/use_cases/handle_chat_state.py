from src.application.conversation.use_cases.generate_ai_response import (
    GenerateAiResponseInput,
    GenerateAiResponseUseCase,
)
from src.application.conversation.use_cases.get_or_create_active_conversation import (
    GetOrCreateActiveConversationInput,
    GetOrCreateActiveConversationUseCase,
)
from src.application.whatsapp_bot.dtos import IncomingMessage
from src.domain.ai_usage.exceptions import AiUsageLimitExceededError
from src.domain.conversation.entities import ConversationMessage
from src.domain.conversation.exceptions import AllProvidersUnavailableError
from src.domain.conversation.repository import ConversationRepository
from src.domain.conversation.value_objects import ConversationChannel, MessageRole
from src.domain.user.entities import User
from src.domain.whatsapp_bot.entities import WhatsappSession
from src.domain.whatsapp_bot.ports import MessageCatalogPort
from src.domain.whatsapp_bot.value_objects import BotMode


class HandleChatStateUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Handler do modo Chat (build-context-07 §2.9) — reaproveita
    a mesma conversa/janela de continuação de 24h do Agente IA
    (`GetOrCreateActiveConversationUseCase`, `channel=whatsapp`) e chama
    `GenerateAiResponseUseCase` de forma síncrona, dentro do próprio job
    ARQ deste módulo, sem passar por WebSocket (o fluxo web usa
    WebSocket; o bot já está rodando no worker e responde direto via
    Evolution API). Não introduz um novo "serviço" redundante: os dois
    use cases do Agente IA já são desacoplados de WebSocket por conta
    própria (build-context-04).
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        get_or_create_active_conversation_use_case: GetOrCreateActiveConversationUseCase,
        generate_ai_response_use_case: GenerateAiResponseUseCase,
        message_catalog: MessageCatalogPort,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._get_or_create_active_conversation_use_case = get_or_create_active_conversation_use_case
        self._generate_ai_response_use_case = generate_ai_response_use_case
        self._message_catalog = message_catalog

    async def execute(self, user: User, session: WhatsappSession, message: IncomingMessage) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Persiste a mensagem do usuário antes de gerar a
        resposta (mesmo padrão de `SendMessageUseCase`), já que
        `GenerateAiResponseUseCase` espera uma `ConversationMessage` já
        existente. `AllProvidersUnavailableError` (Gemini e Grok
        falharam) vira `chat.error`; `AiUsageLimitExceededError`
        (build-context-10 §2.5 — limite mensal de conversas do plano
        atingido) vira `chat.usageLimitExceeded`, convidando a fazer
        upgrade — nenhum dos dois propaga para o `try/except` genérico
        do orquestrador, que devolveria uma mensagem menos específica.
        """
        session.transition_to(BotMode.CHAT)

        conversation = await self._get_or_create_active_conversation_use_case.execute(
            GetOrCreateActiveConversationInput(user_id=user.id, channel=ConversationChannel.WHATSAPP)
        )
        assert conversation is not None

        user_message = await self._conversation_repository.add_message(
            ConversationMessage(
                conversation_id=conversation.id, role=MessageRole.USER, content=message.text or ""
            )
        )
        conversation.last_message_at = user_message.created_at
        await self._conversation_repository.update(conversation)

        try:
            assistant_message = await self._generate_ai_response_use_case.execute(
                GenerateAiResponseInput(conversation_id=conversation.id, message_id=user_message.id)
            )
        except AllProvidersUnavailableError:
            return self._message_catalog.get_message("chat.error", user.language)
        except AiUsageLimitExceededError:
            return self._message_catalog.get_message("chat.usageLimitExceeded", user.language)

        if assistant_message is None:
            return self._message_catalog.get_message("chat.error", user.language)

        return assistant_message.content
