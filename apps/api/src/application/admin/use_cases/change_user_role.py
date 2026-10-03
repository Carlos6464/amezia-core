import uuid
from dataclasses import dataclass

from src.application.admin.dtos import AdminUserRow
from src.domain.subscription.repository import SubscriptionRepository
from src.domain.user.entities import UserRole
from src.domain.user.exceptions import UserNotFoundError
from src.domain.user.repository import UserRepository


@dataclass
class ChangeUserRoleInput:
    user_id: uuid.UUID
    role: UserRole


class ChangeUserRoleUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Troca de papel (`user`/`admin`) de um usuário — única
    escrita deste módulo sobre o agregado `User` (build-context-06 §2.3).
    """

    def __init__(
        self, user_repository: UserRepository, subscription_repository: SubscriptionRepository
    ) -> None:
        self._user_repository = user_repository
        self._subscription_repository = subscription_repository

    async def execute(self, data: ChangeUserRoleInput) -> AdminUserRow:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Carrega o usuário, aplica o novo papel e persiste —
        404 via UserNotFoundError se o usuário não existir. Desde
        2026-09-15, também resolve a `Subscription` pra devolver
        `AdminUserRow` (plano efetivo/status de teste) em vez do `User`
        puro — a troca de papel em si não toca a assinatura.
        """
        user = await self._user_repository.get_by_id(data.user_id)
        if user is None:
            raise UserNotFoundError(str(data.user_id))
        user.role = data.role
        updated_user = await self._user_repository.update(user)
        subscription = await self._subscription_repository.get_by_user_id(data.user_id)
        return AdminUserRow(
            user=updated_user,
            effective_plan=subscription.resolve_effective_plan() if subscription else None,
            is_admin_test_access=(
                subscription.admin_test_access_granted_at is not None if subscription else False
            ),
        )
