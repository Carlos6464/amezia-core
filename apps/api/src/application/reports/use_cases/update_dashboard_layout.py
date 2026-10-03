import uuid
from dataclasses import dataclass

from src.domain.user.exceptions import UserNotFoundError
from src.domain.user.repository import UserRepository
from src.domain.user.value_objects import DashboardCardPreference


@dataclass
class UpdateDashboardLayoutInput:
    user_id: uuid.UUID
    layout: list[DashboardCardPreference]


class UpdateDashboardLayoutUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Salva o layout personalizado do Dashboard do usuário
    autenticado — pedido direto do usuário, fora de qualquer
    build-context. Mesmo padrão de `UpdateBudgetUseCase`: sobrescreve o
    campo inteiro (não faz merge parcial) — o frontend sempre manda a
    lista completa dos 6 cards personalizáveis, então não há estado
    anterior pra preservar seletivamente.
    """

    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def execute(self, input_data: UpdateDashboardLayoutInput) -> list[DashboardCardPreference]:
        user = await self._user_repository.get_by_id(input_data.user_id)
        if user is None:
            raise UserNotFoundError(str(input_data.user_id))
        user.dashboard_layout = input_data.layout
        updated = await self._user_repository.update(user)
        return updated.dashboard_layout or []
