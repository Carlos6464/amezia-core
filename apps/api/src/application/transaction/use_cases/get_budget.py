import uuid

from src.domain.user.exceptions import UserNotFoundError
from src.domain.user.repository import UserRepository


class GetBudgetUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Lê o teto mensal (`monthly_budget_cents`) do perfil do
    usuário autenticado — global, não por categoria (build-context-03
    §2.9). Reaproveita `UserRepository` do build-context-01, sem tabela
    nova.
    """

    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def execute(self, user_id: uuid.UUID) -> int | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Retorna `None` quando o usuário ainda não configurou
        nenhum teto.
        """
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(str(user_id))
        return user.monthly_budget_cents
