import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel

from src.application.subscription.use_cases.get_plan_catalog import PlanCatalogEntry
from src.domain.subscription.entities import PlanLimits, PlanPrice, Subscription

PlanLiteral = Literal["free", "pro", "premium"]
PaidPlanLiteral = Literal["pro", "premium"]
BillingCycleLiteral = Literal["monthly", "annual"]
SubscriptionStatusLiteral = Literal["trialing", "active", "past_due", "canceled", "incomplete"]


class CheckoutRequest(BaseModel):
    plan: PaidPlanLiteral
    billing_cycle: BillingCycleLiteral


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    plan: PlanLiteral
    effective_plan: PlanLiteral
    billing_cycle: BillingCycleLiteral | None
    status: SubscriptionStatusLiteral
    current_period_end: dt.datetime | None
    trial_ends_at: dt.datetime | None
    is_admin_test_access: bool

    @classmethod
    def from_entity(cls, subscription: Subscription) -> "SubscriptionResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Converte a entidade de domínio Subscription no
        schema de resposta HTTP — `effective_plan` é o plano resolvido
        (trata `legacy_pro_until` vencido), `plan` é o valor bruto
        armazenado, exposto pra transparência/depuração no frontend.
        `is_admin_test_access` (2026-09-15) sinaliza pro frontend
        esconder toda a área de gestão de plano/cobrança — quem tem
        acesso de teste concedido pelo admin não tem assinatura real
        nenhuma por trás, então não faz sentido deixar a pessoa ver/
        mexer em checkout, portal de cobrança ou upgrade/downgrade.
        """
        return cls(
            id=subscription.id,
            plan=subscription.plan.value,
            effective_plan=subscription.resolve_effective_plan().value,
            billing_cycle=subscription.billing_cycle.value if subscription.billing_cycle else None,
            status=subscription.status.value,
            current_period_end=subscription.current_period_end,
            trial_ends_at=subscription.trial_ends_at,
            is_admin_test_access=subscription.admin_test_access_granted_at is not None,
        )


class PlanLimitsResponse(BaseModel):
    plan: PlanLiteral
    ai_conversations_per_month: int | None
    ai_reports_per_month: int | None
    whatsapp_bot_messages_per_month: int | None
    csv_exports_per_month: int | None
    priority_support_enabled: bool

    @classmethod
    def from_entity(cls, plan_limits: PlanLimits) -> "PlanLimitsResponse":
        return cls(
            plan=plan_limits.plan.value,
            ai_conversations_per_month=plan_limits.ai_conversations_per_month,
            ai_reports_per_month=plan_limits.ai_reports_per_month,
            whatsapp_bot_messages_per_month=plan_limits.whatsapp_bot_messages_per_month,
            csv_exports_per_month=plan_limits.csv_exports_per_month,
            priority_support_enabled=plan_limits.priority_support_enabled,
        )


class GetMySubscriptionResponse(BaseModel):
    subscription: SubscriptionResponse
    plan_limits: PlanLimitsResponse


class CheckoutResponse(BaseModel):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Exatamente um dos dois campos vem preenchido —
    `checkout_url` (frontend redireciona pro Stripe) ou `subscription`
    (troca já aplicada via API direta, frontend só atualiza a tela).
    """

    checkout_url: str | None
    subscription: SubscriptionResponse | None


class BillingPortalResponse(BaseModel):
    url: str


class PlanCatalogPriceResponse(BaseModel):
    unit_amount_cents: int
    currency: str

    @classmethod
    def from_entity(cls, plan_price: PlanPrice) -> "PlanCatalogPriceResponse":
        return cls(unit_amount_cents=plan_price.unit_amount_cents, currency=plan_price.currency)


class PlanCatalogEntryResponse(BaseModel):
    plan: PlanLiteral
    limits: PlanLimitsResponse
    monthly: PlanCatalogPriceResponse | None
    annual: PlanCatalogPriceResponse | None

    @classmethod
    def from_entry(cls, entry: PlanCatalogEntry) -> "PlanCatalogEntryResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Converte um `PlanCatalogEntry` (application layer)
        no schema de resposta HTTP pública — `monthly`/`annual` ficam
        `null` quando o Admin ainda não cadastrou preço pra esse ciclo
        (Free nunca tem os dois; anual pode não existir ainda).
        """
        return cls(
            plan=entry.plan.value,
            limits=PlanLimitsResponse.from_entity(entry.limits),
            monthly=PlanCatalogPriceResponse.from_entity(entry.monthly_price)
            if entry.monthly_price
            else None,
            annual=PlanCatalogPriceResponse.from_entity(entry.annual_price)
            if entry.annual_price
            else None,
        )


class PlanCatalogResponse(BaseModel):
    free: PlanCatalogEntryResponse
    pro: PlanCatalogEntryResponse
    premium: PlanCatalogEntryResponse
