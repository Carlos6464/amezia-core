import uuid
from dataclasses import dataclass

from src.domain.user.entities import User
from src.domain.user.exceptions import PasswordAlreadySetError, UserNotFoundError
from src.domain.user.repository import UserRepository
from src.infrastructure.security.password_hasher import PasswordHasher


@dataclass
class SetPasswordInput:
    user_id: uuid.UUID
    new_password: str


class SetPasswordUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Define a senha local de uma conta só-OAuth pela primeira
    vez (`password_hash` ainda None) — diferente de ChangePasswordUseCase,
    que exige a senha atual e por isso não serve para esse caso. Corrige
    uma lacuna real: a tela de perfil escondia o formulário de senha
    inteiro para qualquer conta com Google vinculado, mesmo quando ela
    nunca teve uma senha local pra trocar (bug encontrado em 2026-08-15).
    Levanta PasswordAlreadySetError se a conta já tem `password_hash`
    (nesse caso o fluxo certo é ChangePasswordUseCase).
    """

    def __init__(self, user_repository: UserRepository, password_hasher: PasswordHasher) -> None:
        self._user_repository = user_repository
        self._password_hasher = password_hasher

    async def execute(self, data: SetPasswordInput) -> User:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Confere que a conta ainda não tem senha antes de
        gravar — recusa com PasswordAlreadySetError caso já tenha
        (nesse caso o fluxo certo é ChangePasswordUseCase).
        """
        user = await self._user_repository.get_by_id(data.user_id)
        if user is None:
            raise UserNotFoundError()
        if user.password_hash is not None:
            raise PasswordAlreadySetError()

        user.password_hash = self._password_hasher.hash(data.new_password)
        return await self._user_repository.update(user)
