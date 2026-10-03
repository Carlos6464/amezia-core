from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.user.dtos import AuthResult
from src.domain.user.exceptions import InvalidCredentialsError
from src.domain.user.repository import UserRepository
from src.infrastructure.security.jwt_service import JwtService
from src.infrastructure.security.password_hasher import PasswordHasher


@dataclass
class AdminLoginInput:
    email: str
    password: str


class AdminLoginUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Autentica só contas com `role=admin` na porta de entrada
    própria do painel administrativo (`/admin/login`, decisão de produto
    registrada em 2026-08-15: painéis cliente e admin são isolados, sem
    link cruzado entre os dois). Levanta o **mesmo** InvalidCredentialsError
    do login comum tanto para email/senha errados quanto para uma conta
    válida sem `role=admin` — a resposta HTTP fica indistinguível de
    "credenciais inválidas" nos dois casos, sem revelar que a conta
    existe mas não tem permissão de admin. Não reaproveita LoginUseCase
    por composição de propósito: chamar seu `execute()` gravaria
    `last_login_at` mesmo numa tentativa rejeitada por papel, um efeito
    colateral indevido numa conta que não conseguiu entrar aqui.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        jwt_service: JwtService,
    ) -> None:
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._jwt_service = jwt_service

    async def execute(self, data: AdminLoginInput) -> AuthResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Verifica email + senha + papel admin, nessa ordem, e só
        então atualiza last_login_at e emite os tokens de sessão (mesmo
        formato de LoginUseCase — sessão única, RN-08).
        """
        user = await self._user_repository.get_by_email(data.email)
        if user is None or user.password_hash is None:
            raise InvalidCredentialsError()
        if not self._password_hasher.verify(data.password, user.password_hash):
            raise InvalidCredentialsError()
        if user.role != "admin":
            raise InvalidCredentialsError()

        user.last_login_at = datetime.now(UTC)
        updated = await self._user_repository.update(user)

        access_token = self._jwt_service.create_access_token(
            str(updated.id), updated.role, updated.language.value
        )
        refresh_token = self._jwt_service.create_refresh_token(str(updated.id))
        return AuthResult(user=updated, access_token=access_token, refresh_token=refresh_token)
