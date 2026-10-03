import uuid

from src.domain.user.repository import UserRepository


class DeleteAccountUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Exclui a própria conta. Neste build-context só existe a
    tabela `users`, então o cascade (RN-03) é só `DELETE FROM users` — as
    FKs `ON DELETE CASCADE` para transactions/conversations/etc. são
    responsabilidade das migrations dos módulos 02–08.
    """

    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def execute(self, user_id: uuid.UUID) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Remove a conta permanentemente (sem confirmação
        adicional além da já feita no frontend).
        """
        await self._user_repository.delete(user_id)
