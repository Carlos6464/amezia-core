import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.domain.admin_activity.entities import AdminActivityEvent
from src.domain.admin_activity.repository import AdminActivityRepository
from src.domain.subscription.entities import PaymentEvent, Plan, SubscriptionStatus
from src.domain.subscription.ports import PaymentGatewayPort
from src.domain.subscription.repository import (
    PaymentEventRepository,
    PlanPriceRepository,
    SubscriptionRepository,
)
from src.domain.subscription.services import map_stripe_subscription_status
from src.domain.user.repository import UserRepository

logger = logging.getLogger(__name__)

_PLAN_RANK = {Plan.FREE: 0, Plan.PRO: 1, Plan.PREMIUM: 2}

_HANDLED_EVENT_TYPES = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
}


@dataclass
class HandleStripeWebhookInput:
    payload: bytes
    sig_header: str


class HandleStripeWebhookUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: `POST /webhooks/stripe` (build-context-09 §2.5 passo
    5/T9) — processa os 5 eventos que sincronizam `subscriptions` com o
    estado real do Stripe. Idempotente via `stripe_event_id` de
    `payment_events` (mesmo espírito de `processed_bot_messages`/
    RN-04): reentrega do Stripe do mesmo evento não reprocessa nada.
    Eventos fora dos tipos conhecidos são reconhecidos (200) e
    ignorados, sem gravar auditoria — o endpoint pode estar inscrito em
    mais tipos do que os que o produto modela. `customer.subscription.
    created` (achado real, 2026-09-11) foi adicionado depois dos
    outros 4 — sem ele, a 1ª assinatura de um usuário nunca
    sincronizava `plan`/`billing_cycle`: o Stripe dispara `.created` na
    criação via Checkout, não `.updated` (esse só dispara depois, em
    mudanças subsequentes — upgrade, renovação, trial terminando), e
    `checkout.session.completed` sozinho só grava `stripe_subscription_id`
    — o `plan` continuava `free` pra sempre, mesmo com o pagamento
    aprovado no Stripe.
    """

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        payment_event_repository: PaymentEventRepository,
        plan_price_repository: PlanPriceRepository,
        payment_gateway: PaymentGatewayPort,
        user_repository: UserRepository,
        admin_activity_repository: AdminActivityRepository,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._payment_event_repository = payment_event_repository
        self._plan_price_repository = plan_price_repository
        self._payment_gateway = payment_gateway
        self._user_repository = user_repository
        self._admin_activity_repository = admin_activity_repository

    async def execute(self, input_data: HandleStripeWebhookInput) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Valida a assinatura, filtra por tipo de evento
        conhecido, checa idempotência e despacha pro handler certo —
        grava a auditoria em `payment_events` só depois de processar
        com sucesso.
        """
        event = self._payment_gateway.construct_webhook_event(
            input_data.payload, input_data.sig_header
        )
        event_id: str = event["id"]
        event_type: str = event["type"]

        if event_type not in _HANDLED_EVENT_TYPES:
            return
        if await self._payment_event_repository.exists_by_stripe_event_id(event_id):
            return

        data_object: dict[str, Any] = event["data"]["object"]
        user_id, amount_cents, currency = await self._dispatch(event_type, data_object)

        await self._payment_event_repository.create(
            PaymentEvent(
                stripe_event_id=event_id,
                event_type=event_type,
                user_id=user_id,
                amount_cents=amount_cents,
                currency=currency,
                raw_payload=event,
            )
        )

    async def _dispatch(
        self, event_type: str, data_object: dict[str, Any]
    ) -> tuple[uuid.UUID | None, int | None, str | None]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Despacha pro handler do evento — devolve
        `(user_id, amount_cents, currency)` pra alimentar a linha de
        auditoria em `payment_events`, sem duplicar essa resolução em
        cada handler.
        """
        if event_type == "checkout.session.completed":
            return await self._handle_checkout_completed(data_object)
        if event_type in ("customer.subscription.created", "customer.subscription.updated"):
            return await self._handle_subscription_updated(data_object)
        if event_type == "customer.subscription.deleted":
            return await self._handle_subscription_deleted(data_object)
        return await self._handle_invoice_payment_failed(data_object)

    async def _handle_checkout_completed(
        self, session: dict[str, Any]
    ) -> tuple[uuid.UUID | None, int | None, str | None]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: `checkout.session.completed` — ativa a assinatura,
        gravando `stripe_subscription_id` na Subscription já
        localizada por `stripe_customer_id` (criado por
        `StartCheckoutUseCase` antes de abrir a Checkout Session).
        `plan`/`status`/`current_period_end` chegam via
        `customer.subscription.created`/`.updated` (mesmo handler,
        `_handle_subscription_updated` — corrigido em 2026-09-11: o
        Stripe dispara `.created` na 1ª assinatura, não `.updated`)
        — evita 2ª chamada à API aqui só pra buscar o objeto completo.
        """
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        subscription = (
            await self._subscription_repository.get_by_stripe_customer_id(customer_id)
            if customer_id
            else None
        )
        if subscription is None:
            logger.warning("checkout.session.completed for unknown customer_id=%s", customer_id)
            return None, session.get("amount_total"), session.get("currency")

        subscription.stripe_subscription_id = subscription_id
        await self._subscription_repository.update(subscription)
        return subscription.user_id, session.get("amount_total"), session.get("currency")

    async def _handle_subscription_updated(
        self, stripe_subscription: dict[str, Any]
    ) -> tuple[uuid.UUID | None, int | None, str | None]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: `customer.subscription.created`/`.updated` (mesmo
        handler desde 2026-09-11 — o payload do objeto `Subscription` é
        idêntico nos dois eventos) — cobre 1ª assinatura, upgrade,
        downgrade, renovação e trial→ativo. `plan`/`billing_cycle` são
        resolvidos consultando `plan_prices` pelo `price.id` do 1º item
        (catálogo dinâmico, revisado em 2026-09-10 — o lookup funciona
        mesmo pra um Price já arquivado, já que um assinante existente
        pode continuar num preço antigo depois de uma edição no Admin).
        """
        subscription_id = stripe_subscription.get("id")
        subscription = await self._subscription_repository.get_by_stripe_subscription_id(
            subscription_id
        )
        if subscription is None:
            subscription = await self._subscription_repository.get_by_stripe_customer_id(
                stripe_subscription.get("customer")
            )
        if subscription is None:
            logger.warning(
                "customer.subscription.updated for unknown subscription_id=%s", subscription_id
            )
            return None, None, None

        old_plan = subscription.plan
        subscription.stripe_subscription_id = subscription_id
        subscription.status = map_stripe_subscription_status(stripe_subscription["status"])

        price_id = stripe_subscription["items"]["data"][0]["price"]["id"]
        plan_price = await self._plan_price_repository.get_by_stripe_price_id(price_id)
        if plan_price is not None:
            subscription.plan = plan_price.plan
            subscription.billing_cycle = plan_price.billing_cycle

        current_period_end = stripe_subscription.get("current_period_end")
        if current_period_end:
            subscription.current_period_end = datetime.fromtimestamp(current_period_end, tz=UTC)

        trial_end = stripe_subscription.get("trial_end")
        subscription.trial_ends_at = (
            datetime.fromtimestamp(trial_end, tz=UTC) if trial_end else None
        )

        await self._subscription_repository.update(subscription)
        if subscription.plan != old_plan:
            await self._record_plan_change_activity(subscription.user_id, old_plan, subscription.plan)
        return subscription.user_id, None, None

    async def _record_plan_change_activity(
        self, user_id: uuid.UUID, old_plan: Plan, new_plan: Plan
    ) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Grava `user_upgraded`/`user_downgraded` no feed do
        Admin (build-context-11 §2.3) quando `customer.subscription.updated`
        muda o plano — best-effort, nunca impede a sincronização da
        assinatura de completar.
        """
        try:
            user = await self._user_repository.get_by_id(user_id)
            name = user.name if user is not None else str(user_id)
            is_upgrade = _PLAN_RANK[new_plan] > _PLAN_RANK[old_plan]
            event_type = "user_upgraded" if is_upgrade else "user_downgraded"
            verb = "fez upgrade" if is_upgrade else "fez downgrade"
            await self._admin_activity_repository.create(
                AdminActivityEvent(
                    event_type=event_type,
                    user_id=user_id,
                    message=f"{name} {verb} {old_plan.value.capitalize()} → {new_plan.value.capitalize()}",
                )
            )
        except Exception:
            logger.warning("Failed to record admin activity for plan change", exc_info=True)

    async def _handle_subscription_deleted(
        self, stripe_subscription: dict[str, Any]
    ) -> tuple[uuid.UUID | None, int | None, str | None]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: `customer.subscription.deleted` — só dispara quando
        a assinatura de fato termina (a Stripe mantém `status=active`
        com `cancel_at_period_end=true` até lá, sem disparar este
        evento). Nesse momento o plano volta pra Free de verdade.
        """
        subscription_id = stripe_subscription.get("id")
        subscription = await self._subscription_repository.get_by_stripe_subscription_id(
            subscription_id
        )
        if subscription is None:
            logger.warning(
                "customer.subscription.deleted for unknown subscription_id=%s", subscription_id
            )
            return None, None, None

        canceled_plan = subscription.plan
        subscription.status = SubscriptionStatus.CANCELED
        subscription.plan = Plan.FREE
        subscription.billing_cycle = None
        await self._subscription_repository.update(subscription)
        await self._record_cancellation_activity(subscription.user_id, canceled_plan)
        return subscription.user_id, None, None

    async def _record_cancellation_activity(self, user_id: uuid.UUID, canceled_plan: Plan) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Grava `user_canceled` no feed do Admin
        (build-context-11 §2.3) — best-effort, nunca impede o
        cancelamento de completar.
        """
        try:
            user = await self._user_repository.get_by_id(user_id)
            name = user.name if user is not None else str(user_id)
            await self._admin_activity_repository.create(
                AdminActivityEvent(
                    event_type="user_canceled",
                    user_id=user_id,
                    message=f"{name} cancelou a assinatura {canceled_plan.value.capitalize()}",
                )
            )
        except Exception:
            logger.warning("Failed to record admin activity for cancellation", exc_info=True)

    async def _handle_invoice_payment_failed(
        self, invoice: dict[str, Any]
    ) -> tuple[uuid.UUID | None, int | None, str | None]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: `invoice.payment_failed` — marca `status=past_due`,
        alimenta o alerta "pagamentos falharam" do Admin
        (build-context-11).
        """
        customer_id = invoice.get("customer")
        subscription = (
            await self._subscription_repository.get_by_stripe_customer_id(customer_id)
            if customer_id
            else None
        )
        amount_cents = invoice.get("amount_due")
        currency = invoice.get("currency")
        if subscription is None:
            logger.warning("invoice.payment_failed for unknown customer_id=%s", customer_id)
            return None, amount_cents, currency

        subscription.status = SubscriptionStatus.PAST_DUE
        await self._subscription_repository.update(subscription)
        return subscription.user_id, amount_cents, currency
