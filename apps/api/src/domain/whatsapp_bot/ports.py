from dataclasses import dataclass
from typing import Any, Protocol

from src.domain.user.value_objects import Language


class WhatsappGatewayPort(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Porta de domínio para envio de mensagem via Evolution API
    — implementada estruturalmente por `EvolutionApiClient`
    (infrastructure/whatsapp/evolution_client.py, build-context-06),
    sem adapter/wrapper (mesmo espírito de `JobEnqueuer`/`ArqRedis`,
    application/shared/ports.py). Download de mídia **não** passa por
    aqui — ver `MediaDecryptorPort` abaixo: o endpoint de mídia da
    Evolution API (`get_media_base64`, removido desta porta em
    2026-08-15) se mostrou não confiável entre versões no projeto irmão
    (`/home/adriano/Documentos/projetos/Amezia`, DIARIO.md) e nunca foi
    validado contra uma instância real neste projeto.
    """

    async def send_text(self, name: str, phone: str, text: str) -> None: ...


class MediaDecryptorPort(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Porta de domínio para decriptação de mídia do WhatsApp
    direto do CDN — implementada por `WhatsappMediaDecryptor`
    (infrastructure/whatsapp/media_decryptor.py). Porta na frente do
    protocolo WhatsApp/Baileys (HKDF-SHA256 + AES-256-CBC), não da
    Evolution API — usada por `HandleExpenseStateUseCase` quando o
    webhook não embute o base64 do áudio inline (caso mais comum na
    prática, confirmado pelo projeto irmão).
    """

    async def download_and_decrypt_audio(self, url: str, media_key: Any) -> bytes | None: ...


@dataclass(frozen=True)
class TranscriptionResult:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Resultado de uma transcrição de áudio (build-context-10
    §2.2, feature `bot_audio_transcription`) — `input_tokens`/
    `output_tokens` vêm da metadata de uso que a resposta do Gemini já
    inclui, capturados em `GeminiAudioTranscriber`. Substitui o `str`
    que `AudioTranscriptionPort.transcribe` devolvia antes deste
    build-context.
    """

    text: str
    model: str
    input_tokens: int
    output_tokens: int


class AudioTranscriptionPort(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Porta de domínio para transcrição de áudio — implementada
    por `GeminiAudioTranscriber` (infrastructure/ai/gemini_client.py).
    Só Gemini transcreve (sem fallback Grok, build-context-07 §2.9),
    mesmo espírito de `EmbeddingGeneratorPort`
    (domain/conversation/ports.py) — único provider, ainda assim atrás
    de uma porta para os use cases nunca dependerem do SDK direto.
    """

    async def transcribe(self, audio_base64: str, mime_type: str) -> TranscriptionResult: ...


class MessageCatalogPort(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Porta de domínio para o catálogo de textos do bot
    (build-context-07 §2.7) — implementada por `MessageCatalog`
    (infrastructure/whatsapp/messages/__init__.py). Os use cases do
    Bot WhatsApp dependem só deste contrato, nunca importam
    infrastructure/ diretamente (regra de dependência do Clean
    Architecture, PRD §5).
    """

    def get_message(self, key: str, language: Language, **kwargs: object) -> str: ...

    def render_menu(self, language: Language) -> str: ...
