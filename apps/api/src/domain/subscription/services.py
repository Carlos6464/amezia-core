from src.domain.subscription.entities import PlanLimits, SubscriptionStatus

# Stripe usa mais estados do que o Amezia modela (`unpaid`,
# `incomplete_expired`, `paused`) — mapeados defensivamente para o estado
# mais próximo em vez de falhar, já que `SubscriptionStatus` só cobre os 5
# estados relevantes ao produto (build-context-09 §2.2).
_STRIPE_STATUS_FALLBACK: dict[str, SubscriptionStatus] = {
    "unpaid": SubscriptionStatus.PAST_DUE,
    "incomplete_expired": SubscriptionStatus.CANCELED,
    "paused": SubscriptionStatus.CANCELED,
}


def map_stripe_subscription_status(raw_status: str) -> SubscriptionStatus:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Traduz o `status` bruto de um objeto Subscription do
    Stripe para `SubscriptionStatus` — usado tanto por
    `StartCheckoutUseCase` (upgrade/downgrade via API direta) quanto
    por `HandleStripeWebhookUseCase` (eventos `customer.subscription.*`),
    para as duas fontes nunca divergirem na tradução.
    """
    try:
        return SubscriptionStatus(raw_status)
    except ValueError:
        return _STRIPE_STATUS_FALLBACK.get(raw_status, SubscriptionStatus.INCOMPLETE)


class PlanLimitService:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Domain Service sem I/O (build-context-09 §2.4, já citado
    em `systemPatterns.md` como exemplo de Domain Service) — resolve
    "o que o plano permite" a partir de um `PlanLimits` já carregado.
    Quem decide "o usuário já bateu o limite deste mês" cruzando isso
    com a contagem real de uso é o build-context-10 (IA) e o
    enforcement de Bot/CSV deste próprio build-context (§2.6); este
    serviço nunca lê dado de uso.
    """

    def whatsapp_bot_message_limit(self, limits: PlanLimits) -> int | None:
        return limits.whatsapp_bot_messages_per_month

    def csv_export_limit(self, limits: PlanLimits) -> int | None:
        return limits.csv_exports_per_month

    def ai_conversation_limit(self, limits: PlanLimits) -> int | None:
        return limits.ai_conversations_per_month

    def ai_report_limit(self, limits: PlanLimits) -> int | None:
        return limits.ai_reports_per_month
