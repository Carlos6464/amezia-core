import uuid
from dataclasses import dataclass

from src.application.user.use_cases.request_password_reset import password_fingerprint
from src.domain.user.exceptions import InvalidOrExpiredTokenError
from src.domain.user.repository import UserRepository
from src.infrastructure.security.jwt_service import JwtService
from src.infrastructure.security.password_hasher import PasswordHasher


@dataclass
class ResetPasswordInput:
    token: str
    new_password: str


class ResetPasswordUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Valida o token de reset (assinatura, type ==
    "password_reset", expiração e fingerprint da senha atual) e define a
    nova senha. O fingerprint desatualizado invalida tokens de reset
    anteriores ao troca de senha mais recente (build-context-01 §2.6).
    """

    def __init__(
        self,
        user_repository: UserRepository,
        jwt_service: JwtService,
        password_hasher: PasswordHasher,
    ) -> None:
        self._user_repository = user_repository
        self._jwt_service = jwt_service
        self._password_hasher = password_hasher

    async def execute(self, data: ResetPasswordInput) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Valida o token de reset (assinatura, tipo, expiração e
        fingerprint de senha) e substitui o password_hash pelo da nova
        senha.
        """
        payload = self._jwt_service.decode(data.token, "password_reset")
        if payload is None:
            raise InvalidOrExpiredTokenError()

        user = await self._user_repository.get_by_id(uuid.UUID(payload["sub"]))
        if user is None or user.password_hash is None:
            raise InvalidOrExpiredTokenError()

        if password_fingerprint(user.password_hash) != payload.get("pwd_fp"):
            raise InvalidOrExpiredTokenError()

        user.password_hash = self._password_hasher.hash(data.new_password)
        await self._user_repository.update(user)
