from dataclasses import dataclass
from typing import Any, Literal

IncomingMessageKind = Literal["text", "audio"]


@dataclass(frozen=True)
class IncomingMessage:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Conteúdo normalizado de uma mensagem recebida do webhook
    Evolution (build-context-07 §2.6) — o orquestrador extrai isso uma
    vez do payload bruto e passa para o handler do estado atual. `text`
    é sempre preenchido para `kind="text"`. Para `kind="audio"`: quando a
    Evolution embute o base64 inline no payload (nem sempre acontece, na
    prática — ver `media_decryptor.py`), `audio_base64` já vem
    preenchido, caminho rápido sem download extra; caso contrário,
    `audio_media_url`/`audio_media_key` (do próprio `audioMessage`/
    `pttMessage` do webhook) permitem baixar e decriptar direto do CDN
    do WhatsApp (`MediaDecryptorPort`), sem depender de nenhum endpoint
    da Evolution API.
    """

    kind: IncomingMessageKind
    text: str | None = None
    audio_base64: str | None = None
    audio_media_url: str | None = None
    audio_media_key: Any | None = None
    audio_mime_type: str = "audio/ogg"
