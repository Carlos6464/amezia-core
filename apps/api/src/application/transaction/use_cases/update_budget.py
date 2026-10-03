import uuid
from dataclasses import dataclass

from src.domain.user.exceptions import UserNotFoundError
from src.domain.user.repository import UserRepository


@dataclass
class UpdateBudgetInput:
    user_id: uuid.UUID
    monthly_budget_cents: int | None


class UpdateBudgetUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Define ou limpa (`monthly_budget_cents = None`) o teto
    mensal do usuário autenticado.
    """

    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def execute(self, input_data: UpdateBudgetInput) -> int | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Persiste o novo valor via `UserRepository.update`
        (build-context-01, reaproveitado).
        """
        user = await self._user_repository.get_by_id(input_data.user_id)
        if user is None:
            raise UserNotFoundError(str(input_data.user_id))
        user.monthly_budget_cents = input_data.monthly_budget_cents
        updated = await self._user_repository.update(user)
        return updated.monthly_budget_cents
