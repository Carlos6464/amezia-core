import logging

from src.domain.conversation.exceptions import AllProvidersUnavailableError
from src.domain.conversation.ports import ChatCompletionResult, ChatMessage
from src.domain.conversation.value_objects import AiProvider
from src.infrastructure.ai.gemini_client import CHAT_MODEL as GEMINI_CHAT_MODEL
from src.infrastructure.ai.gemini_client import GeminiChatClient
from src.infrastructure.ai.grok_client import CHAT_MODEL as GROK_CHAT_MODEL
from src.infrastructure.ai.grok_client import GrokChatClient

logger = logging.getLogger(__name__)


class ChatCompletionGateway:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Implementa `ChatCompletionPort` resolvendo o fallback de
    provider (build-context-04 §2.5) — tenta Gemini primeiro, cai para
    Grok em qualquer exceção/timeout/erro do provider primário. É o
    único ponto do sistema que sabe que existem dois providers; quem
    chama (`GenerateAiResponseUseCase`) só vê a porta de domínio.
    """

    def __init__(
        self,
        gemini_client: GeminiChatClient | None = None,
        grok_client: GrokChatClient | None = None,
    ) -> None:
        self._gemini_client = gemini_client or GeminiChatClient()
        self._grok_client = grok_client or GrokChatClient()

    async def complete(
        self, system_instruction: str, messages: list[ChatMessage]
    ) -> ChatCompletionResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Tenta Gemini, depois Grok, nessa ordem. Levanta
        `AllProvidersUnavailableError` se os dois falharem — capturada
        por `GenerateAiResponseUseCase` para disparar o evento
        `ai_response_failed` em vez de persistir uma resposta. Desde o
        build-context-10, o resultado inclui `input_tokens`/
        `output_tokens` (capturados no client concreto), usados por
        `RecordAiUsageUseCase` para custo/limite — o gateway só repassa,
        nunca recalcula.
        """
        try:
            content, input_tokens, output_tokens = await self._gemini_client.complete(
                system_instruction, messages
            )
            return ChatCompletionResult(
                content=content,
                provider=AiProvider.GEMINI,
                model=GEMINI_CHAT_MODEL,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception:
            logger.warning("Gemini chat completion failed, falling back to Grok", exc_info=True)

        try:
            content, input_tokens, output_tokens = await self._grok_client.complete(
                system_instruction, messages
            )
            return ChatCompletionResult(
                content=content,
                provider=AiProvider.GROK,
                model=GROK_CHAT_MODEL,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception:
            logger.warning("Grok chat completion failed, no provider available", exc_info=True)

        raise AllProvidersUnavailableError("Gemini and Grok both failed to generate a response")
