from datetime import UTC, datetime

from src.domain.subscription.entities import BillingCycle
from src.domain.subscription.repository import PlanPriceRepository, SubscriptionRepository


async def compute_mrr_cents(
    subscription_repository: SubscriptionRepository, plan_price_repository: PlanPriceRepository
) -> int:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: Soma o valor mensalizado de toda assinatura paga
    `active`/`trialing` (build-context-11 §2.1) — anual entra dividido
    por 12. Compartilhado por `GetAdminStatsUseCase` (Visão Geral) e
    `GetAdminPaymentsUseCase` (tela de Pagamentos), pra nunca divergir o
    número de MRR exibido nas duas telas. Assinatura sem preço ativo
    cadastrado pro seu `(plan, billing_cycle)` não contribui, em vez de
    quebrar o cálculo.
    """
    subscriptions = await subscription_repository.list_active_paid()
    total = 0
    for subscription in subscriptions:
        if subscription.billing_cycle is None:
            continue
        price = await plan_price_repository.get_active(subscription.plan, subscription.billing_cycle)
        if price is None:
            continue
        total += (
            price.unit_amount_cents
            if subscription.billing_cycle == BillingCycle.MONTHLY
            else round(price.unit_amount_cents / 12)
        )
    return total


async def compute_churn_rate(subscription_repository: SubscriptionRepository) -> float:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: Cancelamentos deste mês ÷ base do início do mês, em
    percentual (build-context-11 §2.1) — `0.0` quando não havia base
    nenhuma no início do mês. Compartilhado pelos mesmos 2 use cases que
    `compute_mrr_cents`.
    """
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    active_at_start, canceled_this_month = await subscription_repository.count_churn_for_month(
        month_start
    )
    if active_at_start == 0:
        return 0.0
    return round((canceled_this_month / active_at_start) * 100, 2)
