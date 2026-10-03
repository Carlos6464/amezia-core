import re
from functools import lru_cache

import boto3

from src.infrastructure.config import get_settings

_ENDPOINT_REGION_RE = re.compile(r"^s3\.([a-z0-9-]+)\.backblazeb2\.com$")


def _resolve_region(endpoint_url: str, configured_region: str) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Se `BACKBLAZE_REGION` não for informada, deriva a região a
    partir do host do endpoint (`s3.<region>.backblazeb2.com`) em vez de
    depender da tolerância silenciosa do `boto3` a `region_name=""` — essa
    tolerância não é uma garantia documentada do SDK e não deve ser uma
    dependência implícita do projeto.
    """
    if configured_region:
        return configured_region
    host = endpoint_url.removeprefix("https://").removeprefix("http://").rstrip("/")
    match = _ENDPOINT_REGION_RE.match(host)
    return match.group(1) if match else configured_region


@lru_cache
def _get_s3_client():
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Instancia o client `boto3` contra a API S3-compatível do
    Backblaze B2 (endpoint customizado) — cacheado por processo, mesmo
    padrão do `_get_fernet()` em `encrypted_string.py`. Usa `boto3` (SDK
    padrão da AWS, amplamente documentado) em vez do SDK proprietário do
    Backblaze (`b2sdk`), porque o B2 expõe deliberadamente uma API
    compatível com S3 — ver `DIARIO.md` para o porquê dessa escolha.
    """
    settings = get_settings()
    if not settings.BACKBLAZE_ENDPOINT_URL:
        raise RuntimeError("Backblaze B2 is not configured")
    return boto3.client(
        "s3",
        endpoint_url=settings.BACKBLAZE_ENDPOINT_URL,
        aws_access_key_id=settings.BACKBLAZE_KEY_ID,
        aws_secret_access_key=settings.BACKBLAZE_APPLICATION_KEY,
        region_name=_resolve_region(settings.BACKBLAZE_ENDPOINT_URL, settings.BACKBLAZE_REGION),
    )


class BackblazeStorageClient:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Cliente de armazenamento de objetos (comprovante de
    transação) contra um bucket privado do Backblaze B2. Upload sempre
    passa pelo backend (decisão de produto — validação de tipo/tamanho
    no servidor); download usa URL assinada (presigned GET) gerada sob
    demanda, nunca persistida (build-context-03 §2.8).
    """

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.BACKBLAZE_BUCKET_NAME:
            raise RuntimeError("Backblaze B2 is not configured")
        self._bucket = settings.BACKBLAZE_BUCKET_NAME
        self._client = _get_s3_client()

    def upload(self, key: str, content: bytes, content_type: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Envia o arquivo já validado (tipo/tamanho — ver
        `UploadReceiptUseCase`) para o bucket, sob a chave informada.
        """
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=content, ContentType=content_type
        )

    def delete(self, key: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Remove o objeto do bucket — usado por
        `DeleteReceiptUseCase` e ao substituir um comprovante existente.
        """
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Gera uma URL de download temporária e assinada — o
        bucket é privado, então essa é a única forma do usuário
        visualizar/baixar o próprio comprovante direto do B2, sem passar
        banda pelo nosso backend.
        """
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=expires_in
        )
