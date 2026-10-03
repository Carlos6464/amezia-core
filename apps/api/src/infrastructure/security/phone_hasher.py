import hashlib
import hmac
import re

from src.infrastructure.config import get_settings

_NON_DIGITS = re.compile(r"\D+")


def hash_phone(phone: str) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Gera o hash determinístico (HMAC-SHA256, hex) de um número
    de telefone — usado como índice paralelo a `users.phone`
    (EncryptedString, IV aleatório, não pesquisável por igualdade em
    SQL, RN-05). Normaliza removendo tudo que não é dígito antes de
    calcular o HMAC, para que o número salvo no perfil (`+55 11 99999-9999`,
    por exemplo) e o `remoteJid` recebido do webhook Evolution
    (`5511999999999@s.whatsapp.net`, sem `+`) produzam o mesmo hash
    independente de formatação. Chave dedicada (`PHONE_HASH_SECRET`),
    nunca `AES_ENCRYPTION_KEY` (build-context-07 §2.2).
    """
    settings = get_settings()
    if not settings.PHONE_HASH_SECRET:
        raise RuntimeError("PHONE_HASH_SECRET is not configured")
    normalized = _NON_DIGITS.sub("", phone)
    return hmac.new(
        settings.PHONE_HASH_SECRET.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256
    ).hexdigest()


class PhoneHasher:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Implementação de `PhoneHasherPort` (domain/user/ports.py)
    — wrapper fino sobre `hash_phone()`, injetado em `UpdateProfileUseCase`
    para a application layer nunca importar infrastructure/ diretamente
    (regra de dependência do Clean Architecture, PRD §5).
    """

    def hash(self, phone: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Delega para `hash_phone()` — existe só para satisfazer
        `PhoneHasherPort` sem a application layer importar esta função
        diretamente.
        """
        return hash_phone(phone)
