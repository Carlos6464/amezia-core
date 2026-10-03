from dataclasses import dataclass

from src.application.admin.dtos import AdminUserRow
from src.domain.subscription.repository import SubscriptionRepository
from src.domain.user.repository import UserFilters, UserRepository


@dataclass
class ListUsersResult:
    items: list[AdminUserRow]
    total: int


class ListUsersUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Lista paginada de usuários para a tela Usuários do Admin
    (build-context-06 §2.3) — filtros de busca (nome/email), papel e
    vínculo de WhatsApp. Desde 2026-09-15, cada linha também traz o
    plano efetivo e o status de acesso de teste (`SubscriptionRepository.
    get_by_user_ids`, uma query em lote pra página inteira — não N+1).
    """

    def __init__(
        self, user_repository: UserRepository, subscription_repository: SubscriptionRepository
    ) -> None:
        self._user_repository = user_repository
        self._subscription_repository = subscription_repository

    async def execute(self, filters: UserFilters, page: int, page_size: int) -> ListUsersResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Delega a paginação/filtro inteiros ao repositório,
        resolve as `Subscription` da página em lote e junta os dois em
        `AdminUserRow`.
        """
        items, total = await self._user_repository.list_paginated(filters, page, page_size)
        subscriptions = await self._subscription_repository.get_by_user_ids(
            [user.id for user in items]
        )
        subscription_by_user_id = {sub.user_id: sub for sub in subscriptions}

        rows = [
            AdminUserRow(
                user=user,
                effective_plan=(
                    subscription_by_user_id[user.id].resolve_effective_plan()
                    if user.id in subscription_by_user_id
                    else None
                ),
                is_admin_test_access=(
                    subscription_by_user_id[user.id].admin_test_access_granted_at is not None
                    if user.id in subscription_by_user_id
                    else False
                ),
            )
            for user in items
        ]
        return ListUsersResult(items=rows, total=total)
