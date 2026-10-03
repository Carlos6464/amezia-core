import uuid

from src.application.admin.dtos import AdminUserRow
from src.domain.subscription.repository import SubscriptionRepository
from src.domain.user.exceptions import UserNotFoundError
from src.domain.user.repository import UserRepository


class GetUserUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Detalhe de um usuário para o Admin (build-context-06
    §2.3) — este módulo não redefine `User`, só consulta o agregado já
    existente (build-context-01). Desde 2026-09-15, também resolve o
    plano efetivo e o status de acesso de teste via `Subscription`.
    """

    def __init__(
        self, user_repository: UserRepository, subscription_repository: SubscriptionRepository
    ) -> None:
        self._user_repository = user_repository
        self._subscription_repository = subscription_repository

    async def execute(self, user_id: uuid.UUID) -> AdminUserRow:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Busca o usuário pelo id — 404 via UserNotFoundError se
        não existir.
        """
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(str(user_id))
        subscription = await self._subscription_repository.get_by_user_id(user_id)
        return AdminUserRow(
            user=user,
            effective_plan=subscription.resolve_effective_plan() if subscription else None,
            is_admin_test_access=(
                subscription.admin_test_access_granted_at is not None if subscription else False
            ),
        )
