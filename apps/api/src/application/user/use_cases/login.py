from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.user.dtos import AuthResult
from src.domain.user.exceptions import InvalidCredentialsError
from src.domain.user.repository import UserRepository
from src.infrastructure.security.jwt_service import JwtService
from src.infrastructure.security.password_hasher import PasswordHasher


@dataclass
class LoginInput:
    email: str
    password: str


class LoginUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Autentica por email/senha. Recusa com InvalidCredentialsError
    tanto se o email não existe, a senha não confere, quanto se a conta é
    só-OAuth (password_hash None) — nunca revela qual dos três casos
    ocorreu. Atualiza last_login_at em caso de sucesso.
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

    async def execute(self, data: LoginInput) -> AuthResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Verifica email + senha, atualiza last_login_at e emite
        os tokens de sessão.
        """
        user = await self._user_repository.get_by_email(data.email)
        if user is None or user.password_hash is None:
            raise InvalidCredentialsError()
        if not self._password_hasher.verify(data.password, user.password_hash):
            raise InvalidCredentialsError()

        user.last_login_at = datetime.now(UTC)
        updated = await self._user_repository.update(user)

        access_token = self._jwt_service.create_access_token(
            str(updated.id), updated.role, updated.language.value
        )
        refresh_token = self._jwt_service.create_refresh_token(str(updated.id))
        return AuthResult(user=updated, access_token=access_token, refresh_token=refresh_token)
