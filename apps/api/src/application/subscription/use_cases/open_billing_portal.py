import uuid

from src.domain.subscription.exceptions import NoBillingAccountError, SubscriptionNotFoundError
from src.domain.subscription.ports import PaymentGatewayPort
from src.domain.subscription.repository import SubscriptionRepository
from src.infrastructure.config import get_settings


class OpenBillingPortalUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: `POST /subscriptions/billing-portal` (build-context-09
    §2.5 passo 3/T8) — cria uma sessão do Stripe Customer Portal.
    Cancelamento, troca de cartão e histórico de fatura acontecem
    dentro do Stripe, nunca em tela própria do Amezia.
    """

    def __init__(
        self, subscription_repository: SubscriptionRepository, payment_gateway: PaymentGatewayPort
    ) -> None:
        self._subscription_repository = subscription_repository
        self._payment_gateway = payment_gateway

    async def execute(self, user_id: uuid.UUID) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Valida que a conta já tem `stripe_customer_id`
        (já passou por um checkout) antes de pedir a sessão do portal
        — nunca cria um Customer aqui, isso é responsabilidade de
        `StartCheckoutUseCase`.
        """
        subscription = await self._subscription_repository.get_by_user_id(user_id)
        if subscription is None:
            raise SubscriptionNotFoundError(str(user_id))
        if subscription.stripe_customer_id is None:
            raise NoBillingAccountError(str(user_id))

        settings = get_settings()
        return_url = f"{settings.FRONTEND_URL}/settings/plans"
        return await self._payment_gateway.create_billing_portal_session(
            subscription.stripe_customer_id, return_url
        )
