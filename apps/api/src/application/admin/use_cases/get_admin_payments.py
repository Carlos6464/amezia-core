from dataclasses import dataclass

from src.application.subscription.metrics import compute_churn_rate, compute_mrr_cents
from src.domain.subscription.entities import PaymentEvent
from src.domain.subscription.repository import (
    PaymentEventRepository,
    PlanPriceRepository,
    SubscriptionRepository,
)

_RECENT_LIMIT = 20
_PAYMENT_EVENT_TYPES = ["checkout.session.completed"]


@dataclass
class AdminPaymentsResult:
    mrr_cents: int
    arr_cents: int
    churn_rate: float
    average_ticket_cents: int
    past_due_count: int
    recent_payments: list[PaymentEvent]
    recent_stripe_events: list[PaymentEvent]


class GetAdminPaymentsUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: `GET /admin/payments` (build-context-11 §2.4/T5) — KPIs
    (MRR/ARR/churn/ticket médio) + alerta de pagamentos falhados + feed
    de eventos Stripe + tabela de pagamentos recentes, tudo lido de
    `payment_events`/`subscriptions` (build-context-09) — nunca chama a
    API do Stripe ao vivo. MRR/ARR/churn são calculados aqui, nunca
    armazenados (mesma lógica de `GetAdminStatsUseCase`, via
    `application/subscription/metrics.py`, pra nunca divergir entre as
    2 telas).
    """

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        payment_event_repository: PaymentEventRepository,
        plan_price_repository: PlanPriceRepository,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._payment_event_repository = payment_event_repository
        self._plan_price_repository = plan_price_repository

    async def execute(self) -> AdminPaymentsResult:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Ticket médio = MRR ÷ nº de assinaturas pagas
        `active`/`trialing` (mesma população somada no MRR) — `0`
        quando não há nenhuma assinatura paga ainda.
        """
        mrr_cents = await compute_mrr_cents(self._subscription_repository, self._plan_price_repository)
        churn_rate = await compute_churn_rate(self._subscription_repository)
        paying_subscriptions = await self._subscription_repository.list_active_paid()
        average_ticket_cents = (
            round(mrr_cents / len(paying_subscriptions)) if paying_subscriptions else 0
        )
        past_due_count = await self._subscription_repository.count_past_due()
        recent_payments = await self._payment_event_repository.list_recent(
            _RECENT_LIMIT, event_types=_PAYMENT_EVENT_TYPES
        )
        recent_stripe_events = await self._payment_event_repository.list_recent(_RECENT_LIMIT)

        return AdminPaymentsResult(
            mrr_cents=mrr_cents,
            arr_cents=mrr_cents * 12,
            churn_rate=churn_rate,
            average_ticket_cents=average_ticket_cents,
            past_due_count=past_due_count,
            recent_payments=recent_payments,
            recent_stripe_events=recent_stripe_events,
        )
