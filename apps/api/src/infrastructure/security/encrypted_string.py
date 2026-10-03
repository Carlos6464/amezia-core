from functools import lru_cache

from cryptography.fernet import Fernet
from sqlalchemy import String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from src.infrastructure.config import get_settings


@lru_cache
def _get_fernet() -> Fernet:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Instancia o Fernet a partir de AES_ENCRYPTION_KEY, cacheado
    por processo (@lru_cache) para não reconstruir a chave a cada
    encrypt/decrypt.
    """
    settings = get_settings()
    if not settings.AES_ENCRYPTION_KEY:
        raise RuntimeError("AES_ENCRYPTION_KEY is not configured")
    return Fernet(settings.AES_ENCRYPTION_KEY.encode())


class EncryptionService:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Utilitário de criptografia AES (Fernet — AES128-CBC + HMAC,
    IV aleatório a cada chamada) para campos sensíveis (RN-05). Usado
    diretamente pelo `EncryptedString` e reaproveitável pelos módulos 03
    (description), 04 (title/summary) e 06/07 (token/webhook_secret).
    """

    def encrypt(self, value: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Cifra um texto puro. Cada chamada gera um IV aleatório
        novo — o mesmo `value` cifrado duas vezes produz ciphertexts
        diferentes.
        """
        return _get_fernet().encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Decifra um ciphertext gerado por `encrypt`, devolvendo o
        texto puro original.
        """
        return _get_fernet().decrypt(value.encode()).decode()


class EncryptedString(TypeDecorator):
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Tipo SQLAlchemy que cifra/decifra um campo de texto sensível
    (AES/Fernet, RN-05) de forma transparente no bind/result — a aplicação
    sempre lê e escreve texto puro; o ciphertext só existe no banco. Como o
    IV é aleatório a cada gravação, o valor não é pesquisável por igualdade
    em SQL (WHERE campo = ...) — buscas precisam decriptar em memória.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Hook do SQLAlchemy chamado antes de gravar no banco
        (Python → SQL) — cifra o valor. `None` passa direto (coluna
        nullable).
        """
        if value is None:
            return None
        return EncryptionService().encrypt(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Hook do SQLAlchemy chamado ao ler do banco (SQL →
        Python) — decifra o ciphertext de volta para texto puro.
        """
        if value is None:
            return None
        return EncryptionService().decrypt(value)
