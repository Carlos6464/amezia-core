import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.admin.dtos import AdminUserRow
from src.domain.admin_activity.entities import AdminActivityEvent
from src.domain.admin_activity.repository import AdminActivityRepository
from src.domain.subscription.exceptions import SubscriptionNotFoundError
from src.domain.subscription.repository import SubscriptionRepository
from src.domain.user.exceptions import UserNotFoundError
from src.domain.user.repository import UserRepository

logger = logging.getLogger(__name__)


@dataclass
class SetAdminTestAccessInput:
    user_id: uuid.UUID
    enabled: bool


class SetAdminTestAccessUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Concede ou revoga o acesso de teste Premium vitalício de
    um usuário — decisão manual do admin, pra testar o produto sem criar
    nenhuma cobrança real (pedido direto do usuário, fora de qualquer
    build-context). Só grava/limpa `Subscription.
    admin_test_access_granted_at`; nunca toca `plan`/`stripe_customer_id`/
    `stripe_subscription_id` — revogar sempre devolve a conta exatamente
    ao que ela tinha por baixo (Free, na maioria dos casos, ou uma
    assinatura paga real se o usuário também for um assinante de
    verdade), sem exigir nenhum outro passo manual de limpeza.
    """

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        admin_activity_repository: AdminActivityRepository,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._admin_activity_repository = admin_activity_repository

    async def execute(self, data: SetAdminTestAccessInput) -> AdminUserRow:
        """
        Autor: Carlos Adriano
        Data: 2026-09-15
        Descrição: 404 via `UserNotFoundError`/`SubscriptionNotFoundError`
        se o usuário ou a assinatura não existirem (toda conta ganha uma
        `Subscription` no cadastro — não existir é um estado inesperado).
        Grava o feed de atividade do Admin best-effort, mesmo padrão de
        `HandleStripeWebhookUseCase._record_plan_change_activity` — nunca
        impede a concessão/revogação de completar.
        """
        user = await self._user_repository.get_by_id(data.user_id)
        if user is None:
            raise UserNotFoundError(str(data.user_id))

        subscription = await self._subscription_repository.get_by_user_id(data.user_id)
        if subscription is None:
            raise SubscriptionNotFoundError(str(data.user_id))

        subscription.admin_test_access_granted_at = datetime.now(UTC) if data.enabled else None
        updated = await self._subscription_repository.update(subscription)

        await self._record_activity(user_id=user.id, user_name=user.name, enabled=data.enabled)

        return AdminUserRow(
            user=user,
            effective_plan=updated.resolve_effective_plan(),
            is_admin_test_access=updated.admin_test_access_granted_at is not None,
        )

    async def _record_activity(self, user_id: uuid.UUID, user_name: str, enabled: bool) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-15
        Descrição: Feed "Atividade recente" do Admin — best-effort,
        nunca derruba a concessão/revogação por causa de uma falha aqui.
        """
        try:
            event_type = "admin_test_access_granted" if enabled else "admin_test_access_revoked"
            verb = "concedeu" if enabled else "revogou"
            await self._admin_activity_repository.create(
                AdminActivityEvent(
                    event_type=event_type,
                    user_id=user_id,
                    message=f"Admin {verb} acesso de teste Premium vitalício para {user_name}",
                )
            )
        except Exception:
            logger.warning("Failed to record admin activity for test access change", exc_info=True)
