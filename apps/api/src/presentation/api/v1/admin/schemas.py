import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from src.application.admin.dtos import AdminUserRow, FeedbackWithUser
from src.application.admin.use_cases.get_admin_activity import GetAdminActivityResult
from src.application.admin.use_cases.get_admin_payments import AdminPaymentsResult
from src.application.admin.use_cases.get_admin_stats import AdminStats, UsageByChannel
from src.application.ai_usage.use_cases.get_admin_ai_usage_overview import (
    AdminTopConsumerRow,
    GetAdminAiUsageOverviewOutput,
)
from src.domain.admin_activity.entities import AdminActivityEvent
from src.domain.ai_usage.repository import FeatureUsageTotal, ProviderUsageTotal
from src.domain.evolution.entities import EvolutionInstance
from src.domain.subscription.entities import PaymentEvent, PlanPrice
from src.domain.subscription.repository import PlanDistribution

UserRoleLiteral = Literal["user", "admin"]
ConnectionStatusLiteral = Literal["connecting", "connected", "disconnected"]
FeedbackChannelLiteral = Literal["web", "whatsapp"]
FeedbackTypeLiteral = Literal["praise", "suggestion", "bug", "other"]
PaidPlanLiteral = Literal["pro", "premium"]
BillingCycleLiteral = Literal["monthly", "annual"]

_WEBHOOK_EVENTS = ["CONNECTION_UPDATE", "QRCODE_UPDATED", "SEND_MESSAGE", "MESSAGES_UPSERT"]

_MICROS_PER_CENT = 10_000


def _micros_to_cents(micros: int) -> float:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: Converte micros de BRL (unidade de armazenamento interno
    de `ai_usage_events`, ver docstring de `AiUsageEvent` no domínio)
    pra centavos, SEM arredondar pra inteiro — devolve `float` de
    propósito. Uma única chamada de IA custa uma fração de centavo
    (ex.: R$0,0988), e a quebra por feature/provider do admin agrega
    poucos eventos por vez — arredondar aqui pra inteiro já zerava a
    maioria das linhas de novo (achado real, 2026-09-11: o total geral
    aparecia com um valor pequeno mas cada linha da quebra aparecia
    R$0,00, porque `round()` por linha some com frações de centavo que
    só fazem sentido quando exibidas com mais casas decimais). Quem
    decide quantas casas mostrar é o formatter do frontend
    (`formatCurrency`), não a API.
    """
    return micros / _MICROS_PER_CENT


class PaginatedResponse[T](BaseModel):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Schema de resposta paginada genérico (build-context-06
    §2.3) — definido uma vez aqui e reaproveitado pelas 3 listagens do
    módulo (usuários, instâncias Evolution, feedback), em vez de um
    schema próprio por listagem (padrão que os módulos anteriores usavam,
    ex. `TransactionListResponse`). Sintaxe de generics PEP 695 (Python
    3.12), sem precisar importar `Generic`/`TypeVar`.
    """

    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def build(cls, items: list[T], page: int, page_size: int, total: int) -> "PaginatedResponse[T]":
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Calcula `total_pages` a partir de `total`/`page_size`
        e monta a resposta — evita repetir essa conta em cada router.
        """
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return cls(items=items, page=page, page_size=page_size, total=total, total_pages=total_pages)


# --- Stats ---


class MonthlyUserPointResponse(BaseModel):
    month: dt.date
    count: int


class PlanDistributionResponse(BaseModel):
    free: int
    pro: int
    premium: int
    trial_pro: int

    @classmethod
    def from_entity(cls, distribution: PlanDistribution) -> "PlanDistributionResponse":
        return cls(
            free=distribution.free,
            pro=distribution.pro,
            premium=distribution.premium,
            trial_pro=distribution.trial_pro,
        )


class UsageByChannelResponse(BaseModel):
    web: int
    whatsapp: int

    @classmethod
    def from_dto(cls, usage: UsageByChannel) -> "UsageByChannelResponse":
        return cls(web=usage.web, whatsapp=usage.whatsapp)


class AdminStatsResponse(BaseModel):
    total_users: int
    users_with_phone: int
    total_feedbacks: int
    new_users_by_month: list[MonthlyUserPointResponse]
    active_users_daily: int
    active_users_monthly: int
    subscriptions_by_plan: PlanDistributionResponse
    mrr_cents: int
    churn_rate: float
    usage_by_channel: UsageByChannelResponse

    @classmethod
    def from_dto(cls, stats: AdminStats) -> "AdminStatsResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Converte a DTO de aplicação AdminStats no schema de
        resposta HTTP — build-context-11 estendeu com DAU/MAU,
        assinaturas por plano, MRR, churn e uso por canal.
        """
        return cls(
            total_users=stats.total_users,
            users_with_phone=stats.users_with_phone,
            total_feedbacks=stats.total_feedbacks,
            new_users_by_month=[
                MonthlyUserPointResponse(month=point.month, count=point.count)
                for point in stats.new_users_by_month
            ],
            active_users_daily=stats.active_users_daily,
            active_users_monthly=stats.active_users_monthly,
            subscriptions_by_plan=PlanDistributionResponse.from_entity(stats.subscriptions_by_plan),
            mrr_cents=stats.mrr_cents,
            churn_rate=stats.churn_rate,
            usage_by_channel=UsageByChannelResponse.from_dto(stats.usage_by_channel),
        )


# --- Activity feed (build-context-11) ---


class AdminActivityEventResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    user_id: uuid.UUID | None
    message: str
    created_at: dt.datetime

    @classmethod
    def from_entity(cls, event: AdminActivityEvent) -> "AdminActivityEventResponse":
        return cls(
            id=event.id,
            event_type=event.event_type,
            user_id=event.user_id,
            message=event.message,
            created_at=event.created_at,
        )


class AdminActivityListResponse(BaseModel):
    items: list[AdminActivityEventResponse]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def from_result(
        cls, result: GetAdminActivityResult, page: int, page_size: int
    ) -> "AdminActivityListResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Mesmo formato de `PaginatedResponse.build` (build-
        context-06 §2.3), mas com um schema próprio em vez do genérico
        — `AdminActivityEvent` é da camada de aplicação, não de
        domínio puro reaproveitável nos outros 3 lugares que usam
        `PaginatedResponse[T]`.
        """
        total_pages = (result.total + page_size - 1) // page_size if page_size else 0
        return cls(
            items=[AdminActivityEventResponse.from_entity(event) for event in result.items],
            page=page,
            page_size=page_size,
            total=result.total,
            total_pages=total_pages,
        )


# --- Payments (build-context-11) ---


class PaymentEventResponse(BaseModel):
    id: uuid.UUID
    stripe_event_id: str
    event_type: str
    user_id: uuid.UUID | None
    amount_cents: int | None
    currency: str | None
    created_at: dt.datetime

    @classmethod
    def from_entity(cls, event: PaymentEvent) -> "PaymentEventResponse":
        return cls(
            id=event.id,
            stripe_event_id=event.stripe_event_id,
            event_type=event.event_type,
            user_id=event.user_id,
            amount_cents=event.amount_cents,
            currency=event.currency,
            created_at=event.created_at,
        )


class AdminPaymentsResponse(BaseModel):
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: Resposta de `GET /admin/payments` (build-context-11
    §2.4) — MRR/ARR/churn/ticket médio calculados na hora, nunca
    armazenados; nunca chama a API do Stripe ao vivo, só lê
    `payment_events`/`subscriptions` já persistidos via webhook.
    """

    mrr_cents: int
    arr_cents: int
    churn_rate: float
    average_ticket_cents: int
    past_due_count: int
    recent_payments: list[PaymentEventResponse]
    recent_stripe_events: list[PaymentEventResponse]

    @classmethod
    def from_dto(cls, result: AdminPaymentsResult) -> "AdminPaymentsResponse":
        return cls(
            mrr_cents=result.mrr_cents,
            arr_cents=result.arr_cents,
            churn_rate=result.churn_rate,
            average_ticket_cents=result.average_ticket_cents,
            past_due_count=result.past_due_count,
            recent_payments=[PaymentEventResponse.from_entity(e) for e in result.recent_payments],
            recent_stripe_events=[
                PaymentEventResponse.from_entity(e) for e in result.recent_stripe_events
            ],
        )


# --- Users ---


EffectivePlanLiteral = Literal["free", "pro", "premium"]


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str | None
    role: UserRoleLiteral
    language: str
    created_at: dt.datetime
    last_login_at: dt.datetime | None
    effective_plan: EffectivePlanLiteral | None
    is_admin_test_access: bool

    @classmethod
    def from_entity(cls, row: AdminUserRow) -> "AdminUserResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Converte `AdminUserRow` (User + plano efetivo/status
        de teste, desde 2026-09-15) no schema de resposta HTTP do Admin
        — este módulo não redefine User, só expõe um subconjunto de
        leitura dela.
        """
        user = row.user
        return cls(
            id=user.id,
            name=user.name,
            email=str(user.email),
            phone=user.phone,
            role=user.role,
            language=user.language.value,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            effective_plan=row.effective_plan.value if row.effective_plan else None,
            is_admin_test_access=row.is_admin_test_access,
        )


class ChangeUserRoleRequest(BaseModel):
    role: UserRoleLiteral


class SetTestAccessRequest(BaseModel):
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Corpo de `PATCH /admin/users/{id}/test-access` —
    `enabled=true` concede acesso de teste Premium vitalício,
    `enabled=false` revoga (a conta volta pro plano real que tinha por
    baixo, sem nenhum outro passo manual).
    """

    enabled: bool


# --- Evolution instances ---


class EvolutionInstanceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    webhook_url: str = Field(min_length=1, max_length=500)


class EvolutionInstanceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    webhook_url: str | None = Field(default=None, min_length=1, max_length=500)
    is_active: bool | None = None


class EvolutionInstanceResponse(BaseModel):
    public_id: str
    name: str
    phone_number: str | None
    status: ConnectionStatusLiteral
    qr_code: str | None
    qr_code_expires_at: dt.datetime | None
    webhook_url: str
    webhook_secret_masked: str
    webhook_events: list[str]
    is_active: bool
    connected_at: dt.datetime | None
    last_message_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime

    @classmethod
    def from_entity(cls, instance: EvolutionInstance) -> "EvolutionInstanceResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Converte a entidade de domínio EvolutionInstance no
        schema de resposta HTTP. `webhook_secret_masked` nunca expõe o
        segredo real (RN-05) — só os últimos 4 caracteres, para o
        operador confirmar qual segredo está ativo sem poder copiá-lo.
        `webhook_events` é uma lista fixa somente-leitura (os 4 eventos
        que este módulo processa, §2.5) — não é um campo configurável
        persistido no domínio.
        """
        return cls(
            public_id=str(instance.public_id),
            name=instance.name,
            phone_number=instance.phone_number,
            status=instance.status.value,
            qr_code=instance.qr_code,
            qr_code_expires_at=instance.qr_code_expires_at,
            webhook_url=instance.webhook_url,
            webhook_secret_masked=_mask_secret(instance.webhook_secret),
            webhook_events=_WEBHOOK_EVENTS,
            is_active=instance.is_active,
            connected_at=instance.connected_at,
            last_message_at=instance.last_message_at,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
        )


def _mask_secret(secret: str) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Mascara um segredo para exibição — mantém só os últimos 4
    caracteres visíveis (RN-05, `webhook_secret` nunca trafega inteiro
    de volta pro cliente).
    """
    if len(secret) <= 4:
        return "*" * len(secret)
    return f"{'*' * (len(secret) - 4)}{secret[-4:]}"


# --- Feedback ---


class FeedbackUserSummaryResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    message: str
    channel: FeedbackChannelLiteral
    type: FeedbackTypeLiteral
    nps_score: int | None
    subject: str | None
    user: FeedbackUserSummaryResponse | None
    created_at: dt.datetime

    @classmethod
    def from_dto(cls, dto: FeedbackWithUser) -> "FeedbackResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-16
        Descrição: Converte a DTO FeedbackWithUser no schema de resposta
        HTTP — `user` só vem None se a conta já não existir mais (não
        deveria acontecer em uso normal, RN-03 faz cascade).
        """
        return cls(
            id=dto.feedback.id,
            message=dto.feedback.message,
            channel=dto.feedback.channel.value,
            type=dto.feedback.type.value,
            nps_score=dto.feedback.nps_score,
            subject=dto.feedback.subject,
            user=(
                FeedbackUserSummaryResponse(
                    id=dto.user.id, name=dto.user.name, email=str(dto.user.email)
                )
                if dto.user is not None
                else None
            ),
            created_at=dto.feedback.created_at,
        )


# --- Admin login ---


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


# --- Admin: catálogo de preços dos planos (revisado em 2026-09-10) ---


class CreatePlanPriceRequest(BaseModel):
    billing_cycle: BillingCycleLiteral
    unit_amount_cents: int = Field(gt=0)
    currency: str = Field(default="brl", min_length=3, max_length=3)


class PlanPriceResponse(BaseModel):
    id: uuid.UUID
    plan: PaidPlanLiteral
    billing_cycle: BillingCycleLiteral
    stripe_price_id: str
    unit_amount_cents: int
    currency: str
    active: bool
    created_at: dt.datetime

    @classmethod
    def from_entity(cls, plan_price: PlanPrice) -> "PlanPriceResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Converte a entidade de domínio PlanPrice no schema
        de resposta HTTP do Admin.
        """
        return cls(
            id=plan_price.id,
            plan=plan_price.plan.value,
            billing_cycle=plan_price.billing_cycle.value,
            stripe_price_id=plan_price.stripe_price_id,
            unit_amount_cents=plan_price.unit_amount_cents,
            currency=plan_price.currency,
            active=plan_price.active,
            created_at=plan_price.created_at,
        )


class PlanPricesCatalogResponse(BaseModel):
    pro: list[PlanPriceResponse]
    premium: list[PlanPriceResponse]


# --- Admin: uso e custo de IA (build-context-10) ---

AiFeatureLiteral = Literal[
    "agent_chat", "report_narrative", "bot_expense_parsing", "bot_audio_transcription"
]
AiProviderLiteral = Literal["gemini", "grok"]


class FeatureUsageTotalResponse(BaseModel):
    feature: AiFeatureLiteral
    event_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost_cents: float

    @classmethod
    def from_entity(cls, total: FeatureUsageTotal) -> "FeatureUsageTotalResponse":
        return cls(
            feature=total.feature.value,
            event_count=total.event_count,
            input_tokens=total.input_tokens,
            output_tokens=total.output_tokens,
            estimated_cost_cents=_micros_to_cents(total.estimated_cost_micros),
        )


class ProviderUsageTotalResponse(BaseModel):
    provider: AiProviderLiteral
    event_count: int
    estimated_cost_cents: float

    @classmethod
    def from_entity(cls, total: ProviderUsageTotal) -> "ProviderUsageTotalResponse":
        return cls(
            provider=total.provider.value,
            event_count=total.event_count,
            estimated_cost_cents=_micros_to_cents(total.estimated_cost_micros),
        )


class AdminTopConsumerResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    plan: PaidPlanLiteral | Literal["free"]
    ai_conversations: int
    ai_reports: int
    estimated_cost_cents: float

    @classmethod
    def from_dto(cls, row: AdminTopConsumerRow) -> "AdminTopConsumerResponse":
        return cls(
            user_id=row.user_id,
            name=row.name,
            email=row.email,
            plan=row.plan.value,
            ai_conversations=row.ai_conversations,
            ai_reports=row.ai_reports,
            estimated_cost_cents=_micros_to_cents(row.estimated_cost_micros),
        )


class AdminAiUsageOverviewResponse(BaseModel):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Resposta de `GET /admin/ai-usage/overview`
    (build-context-10 §2.6) — "estimado", nunca saldo real de conta
    (§2.4 do build-context-10), a UI do admin deixa isso explícito.
    """

    since: dt.datetime
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost_cents: float
    by_feature: list[FeatureUsageTotalResponse]
    by_provider: list[ProviderUsageTotalResponse]
    top_consumers: list[AdminTopConsumerResponse]

    @classmethod
    def from_dto(cls, output: GetAdminAiUsageOverviewOutput) -> "AdminAiUsageOverviewResponse":
        return cls(
            since=output.since,
            total_input_tokens=output.total_input_tokens,
            total_output_tokens=output.total_output_tokens,
            total_estimated_cost_cents=_micros_to_cents(output.total_estimated_cost_micros),
            by_feature=[FeatureUsageTotalResponse.from_entity(item) for item in output.by_feature],
            by_provider=[ProviderUsageTotalResponse.from_entity(item) for item in output.by_provider],
            top_consumers=[AdminTopConsumerResponse.from_dto(row) for row in output.top_consumers],
        )
