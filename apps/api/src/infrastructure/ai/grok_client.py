from openai import AsyncOpenAI

from src.domain.conversation.ports import ChatMessage
from src.infrastructure.config import get_settings

GROK_BASE_URL = "https://api.x.ai/v1"
CHAT_MODEL = "grok-4"


class GrokChatClient:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Client de chat da xAI (Grok) — provider de fallback
    (build-context-04 §2.5), consumido só via `ChatCompletionGateway`.
    A API da xAI é compatível com o formato OpenAI, então reaproveita o
    SDK oficial `openai` apontado para o `base_url` da xAI, em vez de um
    SDK proprietário.
    """

    def __init__(self, api_key: str | None = None, timeout_seconds: int | None = None) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=api_key or settings.GROK_API_KEY,
            base_url=GROK_BASE_URL,
            timeout=timeout_seconds or settings.AI_CHAT_TIMEOUT_SECONDS,
        )

    async def complete(self, system_instruction: str, messages: list[ChatMessage]) -> tuple[str, int, int]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Gera a resposta de chat no formato OpenAI (`role`
        `system`/`user`/`assistant`) — diferente do Gemini, aqui o papel
        do assistente é literalmente "assistant", então `MessageRole`
        mapeia direto para `role.value` sem tradução. Devolve também
        `input_tokens`/`output_tokens` (build-context-10 §2.2) direto de
        `response.usage`, no mesmo formato que a API da OpenAI expõe.
        """
        chat_messages = [{"role": "system", "content": system_instruction}] + [
            {"role": message.role.value, "content": message.content} for message in messages
        ]
        response = await self._client.chat.completions.create(
            model=CHAT_MODEL, messages=chat_messages
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Grok returned an empty response")

        usage = response.usage
        input_tokens = getattr(usage, "prompt_tokens", None) or 0 if usage else 0
        output_tokens = getattr(usage, "completion_tokens", None) or 0 if usage else 0
        return content, input_tokens, output_tokens
