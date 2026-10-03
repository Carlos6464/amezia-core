import uuid
from dataclasses import dataclass

from src.domain.user.exceptions import (
    InvalidCredentialsError,
    PasswordNotSetError,
    UserNotFoundError,
)
from src.domain.user.repository import UserRepository
from src.infrastructure.security.password_hasher import PasswordHasher


@dataclass
class ChangePasswordInput:
    user_id: uuid.UUID
    current_password: str
    new_password: str


class ChangePasswordUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Troca de senha do usuário autenticado — exige a senha atual.
    `PasswordNotSetError` se a conta é só-OAuth (sem password_hash).
    """

    def __init__(self, user_repository: UserRepository, password_hasher: PasswordHasher) -> None:
        self._user_repository = user_repository
        self._password_hasher = password_hasher

    async def execute(self, data: ChangePasswordInput) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Confere a senha atual antes de trocar — recusa contas
        só-OAuth (sem password_hash) e senha atual incorreta.
        """
        user = await self._user_repository.get_by_id(data.user_id)
        if user is None:
            raise UserNotFoundError()
        if user.password_hash is None:
            raise PasswordNotSetError()
        if not self._password_hasher.verify(data.current_password, user.password_hash):
            raise InvalidCredentialsError()

        user.password_hash = self._password_hasher.hash(data.new_password)
        await self._user_repository.update(user)
