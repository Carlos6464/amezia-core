import uuid

from src.domain.user.exceptions import UserNotFoundError
from src.domain.user.repository import UserRepository
from src.domain.user.value_objects import DashboardCardPreference


class GetDashboardLayoutUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Lê o layout personalizado do Dashboard (quais cards
    ficam visíveis e em que ordem) do perfil do usuário autenticado —
    pedido direto do usuário, fora de qualquer build-context. Mesmo
    padrão de `GetBudgetUseCase` (`application/transaction/use_cases/`):
    a preferência mora em `User`, mas o use case pertence ao módulo
    (Reports/Dashboard) que a consome, não ao dono literal do campo.
    """

    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def execute(self, user_id: uuid.UUID) -> list[DashboardCardPreference] | None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-15
        Descrição: Retorna `None` quando o usuário nunca personalizou o
        Dashboard — o frontend cai no layout padrão (todos os cards
        visíveis, ordem original) nesse caso.
        """
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(str(user_id))
        return user.dashboard_layout
