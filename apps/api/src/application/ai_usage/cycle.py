from datetime import UTC, datetime

from src.domain.subscription.entities import BillingCycle, Subscription
from src.domain.transaction.value_objects import add_months


def resolve_cycle_start(subscription: Subscription | None) -> datetime:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Resolve o início do ciclo de uso corrente
    (build-context-10 §2.5) — compartilhado por `CheckAiUsageLimitUseCase`
    e `GetMyAiUsageUseCase`, pra nunca divergir o que cada um considera
    "ciclo". Usuário com assinatura já cobrada via Stripe (`current_period_end`
    preenchido) usa o mesmo ciclo do Stripe (dia de aniversário da
    assinatura, mensal ou anual conforme `billing_cycle`) — "voltando"
    `current_period_end` um ciclo pra trás. Usuário Free (nunca passou
    por checkout, `current_period_end` sempre `None`) não tem nenhuma
    data de referência própria — cai no mês calendário (dia 1, 00:00),
    mesmo critério que `enforce_csv_export_limit` (build-context-09 §2.6)
    já usa hoje.
    """
    if subscription is not None and subscription.current_period_end is not None:
        months = 12 if subscription.billing_cycle == BillingCycle.ANNUAL else 1
        end = subscription.current_period_end
        cycle_start_date = add_months(end.date(), -months)
        return end.replace(year=cycle_start_date.year, month=cycle_start_date.month, day=cycle_start_date.day)

    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
