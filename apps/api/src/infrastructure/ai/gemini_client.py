import base64

from google import genai
from google.genai import types

from src.domain.conversation.ports import ChatMessage
from src.domain.conversation.value_objects import MessageRole
from src.domain.whatsapp_bot.ports import TranscriptionResult
from src.infrastructure.config import get_settings

_TRANSCRIPTION_INSTRUCTION = (
    "Transcribe this audio message verbatim, in its original language. "
    "Reply with only the transcription, no extra text, no quotes."
)

CHAT_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL = "gemini-embedding-001"


def _to_gemini_role(role: MessageRole) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Traduz o MessageRole do domínio para o vocabulário de role
    da API do Gemini — que chama o papel do assistente de "model", não
    "assistant" (diferente do resto do projeto e do formato OpenAI usado
    pelo Grok).
    """
    return "user" if role == MessageRole.USER else "model"


class GeminiChatClient:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Client do modelo de chat Gemini (`gemini-2.5-flash`) via
    SDK oficial `google-genai`, usado como provider primário de IA
    (build-context-04 §2.5). Consumido só por `ChatCompletionGateway`,
    nunca diretamente por um use case.
    """

    def __init__(self, api_key: str | None = None, timeout_seconds: int | None = None) -> None:
        settings = get_settings()
        self._client = genai.Client(api_key=api_key or settings.GEMINI_API_KEY)
        self._timeout_seconds = timeout_seconds or settings.AI_CHAT_TIMEOUT_SECONDS

    async def complete(self, system_instruction: str, messages: list[ChatMessage]) -> tuple[str, int, int]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Gera a resposta de chat — `system_instruction` (persona
        + instrução de idioma, RN-10) viaja separado do histórico via
        `GenerateContentConfig`, nunca como uma mensagem `user`/`model`.
        Timeout aplicado via `HttpOptions` (milissegundos) — estoura
        `TimeoutError`/erro do SDK, capturado pelo gateway para acionar o
        fallback. Devolve também `input_tokens`/`output_tokens` (build-
        context-10 §2.2) direto de `usage_metadata` da resposta — 0/0
        quando o SDK não a inclui, em vez de falhar a chamada por causa
        de um dado que é só observabilidade.
        """
        contents = [
            types.Content(role=_to_gemini_role(message.role), parts=[types.Part(text=message.content)])
            for message in messages
        ]
        response = await self._client.aio.models.generate_content(
            model=CHAT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                http_options=types.HttpOptions(timeout=self._timeout_seconds * 1000),
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned an empty response")

        usage = response.usage_metadata
        input_tokens = getattr(usage, "prompt_token_count", None) or 0
        output_tokens = getattr(usage, "candidates_token_count", None) or 0
        return response.text, input_tokens, output_tokens


class GeminiEmbeddingClient:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Client de embeddings via `gemini-embedding-001` (SDK
    `google-genai`) — implementa `EmbeddingGeneratorPort`. Trunca a saída
    para `EMBEDDING_DIMENSION` via Matryoshka Representation Learning
    (`output_dimensionality`), coerente com o `vector(768)` fixado na
    migration (build-context-04 §2.2). Único client de embedding do
    projeto — Grok não é fallback de embedding (§2.5).
    """

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self._client = genai.Client(api_key=api_key or settings.GEMINI_API_KEY)
        self._dimension = settings.EMBEDDING_DIMENSION

    async def generate(self, text: str) -> list[float]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Gera o vetor de embedding de um texto — usado tanto
        para indexar conteúdo (transação/mensagem) quanto para embedar a
        pergunta do usuário na hora da busca RAG (build-context-04 §2.3).
        """
        response = await self._client.aio.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=self._dimension),
        )
        if not response.embeddings:
            raise RuntimeError("Gemini returned no embeddings")
        return list(response.embeddings[0].values or [])


class GeminiAudioTranscriber:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Implementa `AudioTranscriptionPort`
    (domain/whatsapp_bot/ports.py) — transcreve o áudio recebido no modo
    Registrar do Bot WhatsApp (build-context-07 §2.9) via
    `gemini-2.5-flash`, o mesmo modelo de chat (multimodal, aceita áudio
    inline). Sem fallback Grok: só Gemini transcreve.
    """

    def __init__(self, api_key: str | None = None, timeout_seconds: int | None = None) -> None:
        settings = get_settings()
        self._client = genai.Client(api_key=api_key or settings.GEMINI_API_KEY)
        self._timeout_seconds = timeout_seconds or settings.AI_CHAT_TIMEOUT_SECONDS

    async def transcribe(self, audio_base64: str, mime_type: str) -> TranscriptionResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Decodifica o base64 recebido do webhook/CDN e envia o
        áudio inline (`types.Part.from_bytes`) junto com uma instrução de
        transcrição literal — sem `system_instruction` separada
        (diferente de `complete()`), já que aqui não há histórico de
        conversa, só uma instrução única. `temperature=0` para saída
        determinística (transcrição não é criativa — mesmo padrão do
        projeto irmão, `/home/adriano/Documentos/projetos/Amezia`).
        Devolve `input_tokens`/`output_tokens` (build-context-10 §2.2,
        feature `bot_audio_transcription`) junto com o texto.
        """
        audio_bytes = base64.b64decode(audio_base64)
        response = await self._client.aio.models.generate_content(
            model=CHAT_MODEL,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                _TRANSCRIPTION_INSTRUCTION,
            ],
            config=types.GenerateContentConfig(
                temperature=0,
                http_options=types.HttpOptions(timeout=self._timeout_seconds * 1000),
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned an empty transcription")

        usage = response.usage_metadata
        input_tokens = getattr(usage, "prompt_token_count", None) or 0
        output_tokens = getattr(usage, "candidates_token_count", None) or 0
        return TranscriptionResult(
            text=response.text, model=CHAT_MODEL, input_tokens=input_tokens, output_tokens=output_tokens
        )
