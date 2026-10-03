from typing import Protocol


class PhoneHasherPort(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Porta de domínio para o hash determinístico de telefone
    (build-context-07 §2.2) — implementada por `PhoneHasher`
    (infrastructure/security/phone_hasher.py). `UpdateProfileUseCase`
    depende só deste contrato, nunca de HMAC/`PHONE_HASH_SECRET`
    diretamente (regra de dependência: application/ importa só de
    domain/).
    """

    def hash(self, phone: str) -> str: ...
