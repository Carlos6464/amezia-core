from dataclasses import dataclass
from typing import Protocol

from src.domain.conversation.value_objects import AiProvider, MessageRole


@dataclass(frozen=True)
class ChatMessage:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Uma entrada do histórico de conversa enviada ao provider
    de chat — só `user`/`assistant` (a instrução de sistema viaja à
    parte, ver `ChatCompletionPort.complete`).
    """

    role: MessageRole
    content: str


@dataclass(frozen=True)
class ChatCompletionResult:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Resultado de uma chamada de chat completo (build-context-10
    §2.2) — `input_tokens`/`output_tokens` vêm direto da metadata de uso
    que Gemini/Grok já devolvem na resposta (`usage_metadata`/`usage`),
    capturados no client concreto (`GeminiChatClient`/`GrokChatClient`) e
    repassados aqui sem recalcular. Substitui a tupla `(str, AiProvider)`
    que `ChatCompletionPort.complete` devolvia antes deste build-context —
    mudança aditiva, quem só lia `content`/`provider` continua
    funcionando igual.
    """

    content: str
    provider: AiProvider
    model: str
    input_tokens: int
    output_tokens: int


class ChatCompletionPort(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Porta de domínio para geração de resposta de chat —
    implementada por `ChatCompletionGateway`
    (infrastructure/ai/chat_completion_gateway.py), que resolve o
    fallback Gemini → Grok internamente. O domínio depende só deste
    contrato, nunca dos SDKs concretos.
    """

    async def complete(
        self, system_instruction: str, messages: list[ChatMessage]
    ) -> ChatCompletionResult: ...


class EmbeddingGeneratorPort(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Porta de domínio para geração de embeddings — implementada
    por `GeminiEmbeddingClient` (infrastructure/ai/gemini_client.py).
    Embeddings usam exclusivamente Gemini (Grok não é fallback de
    embedding, build-context-04 §2.5).
    """

    async def generate(self, text: str) -> list[float]: ...
