import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from src.domain.subscription.entities import BillingCycle, Plan, Subscription
from src.domain.subscription.exceptions import (
    BillingCycleUnavailableError,
    SubscriptionNotFoundError,
)
from src.domain.subscription.ports import PaymentGatewayPort
from src.domain.subscription.repository import (
    PlanLimitsRepository,
    PlanPriceRepository,
    SubscriptionRepository,
)
from src.domain.subscription.services import map_stripe_subscription_status
from src.domain.user.repository import UserRepository
from src.infrastructure.config import get_settings

_PAID_PLANS = {Plan.PRO, Plan.PREMIUM}


@dataclass
class StartCheckoutInput:
    user_id: uuid.UUID
    plan: Plan
    billing_cycle: BillingCycle


@dataclass
class StartCheckoutOutput:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Exatamente um dos dois campos vem preenchido —
    `checkout_url` (assinatura nova, frontend redireciona pro Stripe)
    ou `subscription` (troca de uma assinatura já ativa, resolvida via
    API direta, sem redirect — decisão confirmada com o usuário em
    2026-09-10, já que a Stripe não tem "modo de troca" dentro de uma
    Checkout Session).
    """

    checkout_url: str | None
    subscription: Subscription | None


class StartCheckoutUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: `POST /subscriptions/checkout` (build-context-09 §2.5
    passos 1-2/T7) — mesmo use case pro cadastro com plano pago e pro
    upgrade/downgrade de plano já assinado, diferenciado por já existir
    `stripe_subscription_id` na Subscription do usuário.
    """

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        plan_limits_repository: PlanLimitsRepository,
        plan_price_repository: PlanPriceRepository,
        user_repository: UserRepository,
        payment_gateway: PaymentGatewayPort,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._plan_limits_repository = plan_limits_repository
        self._plan_price_repository = plan_price_repository
        self._user_repository = user_repository
        self._payment_gateway = payment_gateway

    async def execute(self, input_data: StartCheckoutInput) -> StartCheckoutOutput:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Ponto de entrada único — resolve o Price ID e
        despacha pra troca direta (assinatura já ativa) ou checkout
        novo (1ª assinatura paga), conforme `stripe_subscription_id`
        já existir ou não na Subscription do usuário.
        """
        if input_data.plan not in _PAID_PLANS:
            raise ValueError(f"Cannot start checkout for plan={input_data.plan.value}")

        subscription = await self._subscription_repository.get_by_user_id(input_data.user_id)
        if subscription is None:
            raise SubscriptionNotFoundError(str(input_data.user_id))

        price_id = await self._resolve_price_id(input_data.plan, input_data.billing_cycle)

        if subscription.stripe_subscription_id is not None:
            return await self._modify_existing_subscription(
                subscription, input_data.plan, input_data.billing_cycle, price_id
            )
        return await self._start_new_checkout(
            subscription, input_data.plan, input_data.billing_cycle, price_id
        )

    async def _modify_existing_subscription(
        self,
        subscription: Subscription,
        plan: Plan,
        billing_cycle: BillingCycle,
        price_id: str,
    ) -> StartCheckoutOutput:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Upgrade/downgrade de uma assinatura já ativa — troca
        o preço direto via API (proration automática da Stripe),
        sincroniza `plan`/`billing_cycle`/`status`/`current_period_end`
        na hora, sem esperar o webhook (que ainda chega depois e
        confirma o mesmo estado, idempotente).
        """
        assert subscription.stripe_subscription_id is not None
        stripe_data = await self._payment_gateway.modify_subscription(
            subscription.stripe_subscription_id, price_id
        )
        subscription.plan = plan
        subscription.billing_cycle = billing_cycle
        subscription.status = map_stripe_subscription_status(stripe_data["status"])
        period_end = stripe_data.get("current_period_end")
        if period_end:
            subscription.current_period_end = datetime.fromtimestamp(period_end, tz=UTC)
        updated = await self._subscription_repository.update(subscription)
        return StartCheckoutOutput(checkout_url=None, subscription=updated)

    async def _start_new_checkout(
        self,
        subscription: Subscription,
        plan: Plan,
        billing_cycle: BillingCycle,
        price_id: str,
    ) -> StartCheckoutOutput:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: 1ª assinatura paga do usuário (cadastro com plano
        pago, ou upgrade de um Free "puro") — cria o Customer no Stripe
        se ainda não existir e devolve a URL de uma Checkout Session
        com `trial_period_days` vindo de `BillingSettings`.
        """
        if subscription.stripe_customer_id is None:
            user = await self._user_repository.get_by_id(subscription.user_id)
            assert user is not None
            customer_id = await self._payment_gateway.create_customer(str(user.email), user.name)
            subscription.stripe_customer_id = customer_id
            subscription = await self._subscription_repository.update(subscription)

        billing_settings = await self._plan_limits_repository.get_billing_settings()
        settings = get_settings()
        checkout_url = await self._payment_gateway.create_checkout_session(
            customer_id=subscription.stripe_customer_id,
            price_id=price_id,
            trial_period_days=billing_settings.trial_days,
            success_url=(
                f"{settings.FRONTEND_URL}/checkout-success"
                f"?plan={plan.value}&billing={billing_cycle.value}"
            ),
            cancel_url=f"{settings.FRONTEND_URL}/settings/plans",
        )
        return StartCheckoutOutput(checkout_url=checkout_url, subscription=None)

    async def _resolve_price_id(self, plan: Plan, billing_cycle: BillingCycle) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Lê o Price vigente de (plano, ciclo) no catálogo
        dinâmico `plan_prices` (revisado em 2026-09-10 — antes lia 4
        variáveis fixas do `.env`; agora o Admin cadastra/atualiza
        preços em runtime via `CreateOrUpdatePlanPriceUseCase`, sem
        redeploy). Nenhum preço ativo cadastrado ainda pra essa
        combinação (ex.: anual, até o admin criar) levanta
        `BillingCycleUnavailableError`.
        """
        plan_price = await self._plan_price_repository.get_active(plan, billing_cycle)
        if plan_price is None:
            raise BillingCycleUnavailableError(
                f"No active Stripe price configured for plan={plan.value} billing_cycle={billing_cycle.value}"
            )
        return plan_price.stripe_price_id
