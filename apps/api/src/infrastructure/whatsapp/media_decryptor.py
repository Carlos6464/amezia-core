import base64
import logging
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

_AUDIO_INFO = b"WhatsApp Audio Keys"
_DOWNLOAD_TIMEOUT = 60.0


def _decode_media_key(raw: Any) -> bytes | None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Converte `mediaKey` para bytes independente do formato de
    serialização que a Evolution API/Baileys emite: `str` (base64), `list`
    (array de ints) ou `dict` (`Buffer.toJSON()` do Node.js, tanto
    `{"type": "Buffer", "data": [...]}` quanto `{"0": 18, "1": 158, ...}`
    com chaves numéricas como string).
    """
    if isinstance(raw, str):
        return base64.b64decode(raw)
    if isinstance(raw, list):
        return bytes(raw)
    if isinstance(raw, dict):
        data = raw.get("data")
        if isinstance(data, list):
            return bytes(data)
        if all(key.isdigit() for key in raw):
            return bytes(raw[key] for key in sorted(raw, key=int))
    logger.warning(
        "media_decryptor: mediaKey em formato desconhecido: %s", type(raw).__name__
    )
    return None


async def download_and_decrypt_audio(url: str, media_key_raw: Any) -> bytes | None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Baixa e decripta um áudio/PTT do WhatsApp direto do CDN,
    sem depender de nenhum endpoint da Evolution API — protocolo
    documentado publicamente do WhatsApp/Baileys: HKDF-SHA256 expande a
    `mediaKey` (32 bytes) em 112 bytes (`iv` = primeiros 16, `aes_key` =
    bytes 16-48), o arquivo `.enc` do CDN é AES-256-CBC com 10 bytes de
    MAC no final (removidos antes de decriptar, não validados). Porta do
    projeto irmão (`/home/adriano/Documentos/projetos/Amezia`), onde foi
    validado contra uma instância Evolution real depois do endpoint
    `POST /message/getBase64FromMediaMessage/{instance}` (equivalente ao
    que este projeto assumia) ter se confirmado inexistente na versão
    deployada (Evolution v2.3.7) — ver DIARIO.md 2026-08-15. Nunca
    levanta exceção — falhas viram `None`, logadas como warning.
    """
    try:
        media_key = _decode_media_key(media_key_raw)
        if not media_key:
            return None

        hkdf = HKDF(algorithm=hashes.SHA256(), length=112, salt=b"\x00" * 32, info=_AUDIO_INFO)
        expanded = hkdf.derive(media_key)
        iv = expanded[:16]
        aes_key = expanded[16:48]

        async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url)
            if not response.is_success:
                logger.warning(
                    "media_decryptor: CDN retornou %s ao baixar áudio", response.status_code
                )
                return None
            encrypted_bytes = response.content

        if len(encrypted_bytes) <= 10:
            logger.warning("media_decryptor: arquivo muito curto (%d bytes)", len(encrypted_bytes))
            return None

        encrypted_payload = encrypted_bytes[:-10]

        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(encrypted_payload) + decryptor.finalize()

        if not decrypted:
            logger.warning("media_decryptor: resultado vazio após decriptação")
            return None

        padding_length = decrypted[-1]
        if padding_length < 1 or padding_length > 16:
            logger.warning("media_decryptor: padding PKCS7 inválido: %d", padding_length)
            return decrypted
        return decrypted[:-padding_length]

    except Exception:
        logger.warning("media_decryptor: erro ao baixar/decriptar áudio", exc_info=True)
        return None


class WhatsappMediaDecryptor:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Implementação de `MediaDecryptorPort`
    (domain/whatsapp_bot/ports.py) — wrapper fino sobre
    `download_and_decrypt_audio()`, injetado em `HandleExpenseStateUseCase`
    para a application layer nunca importar infrastructure/ diretamente.
    """

    async def download_and_decrypt_audio(self, url: str, media_key: Any) -> bytes | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Delega para `download_and_decrypt_audio()` — existe só
        para satisfazer `MediaDecryptorPort` sem a application layer
        importar esta função diretamente.
        """
        return await download_and_decrypt_audio(url, media_key)
