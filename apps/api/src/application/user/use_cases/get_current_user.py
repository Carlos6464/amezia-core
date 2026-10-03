import uuid

from src.domain.user.entities import User
from src.domain.user.exceptions import UserNotFoundError
from src.domain.user.repository import UserRepository


class GetCurrentUserUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Retorna o perfil do próprio usuário autenticado (user_id
    extraído do JWT — RN-01, nunca aceito vindo do client).
    """

    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def execute(self, user_id: uuid.UUID) -> User:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Carrega o usuário pelo id vindo do JWT; levanta
        UserNotFoundError se a conta não existir mais (ex.: excluída em
        outra aba/sessão).
        """
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        return user
