from dataclasses import dataclass

from src.domain.user.entities import User


@dataclass
class AuthResult:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Resultado comum aos use cases que autenticam o usuário
    (registro, login local, login Google) — o par user + access/refresh
    token que o router usa para montar a resposta e o cookie de refresh.
    """

    user: User
    access_token: str
    refresh_token: str
