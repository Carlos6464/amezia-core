import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class Plan(str, Enum):
    FREE = "free"
    PRO = "pro"
    PREMIUM = "premium"


class BillingCycle(str, Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class SubscriptionStatus(str, Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"


@dataclass
class Subscription:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Entidade de domínio da assinatura (build-context-09 §2.2)
    — relação 1:1 com User, toda conta tem uma linha, mesmo no Free.
    `status` espelha o objeto Subscription do Stripe (nunca calculado
    localmente, só atualizado via webhook); `legacy_pro_until` (§2.7) é
    exclusivo do cohort de usuários que já usavam o produto antes do
    lançamento do módulo — concede Pro irrestrito sem passar por Stripe
    até essa data. `admin_test_access_granted_at` (2026-09-15) é um
    mecanismo irmão, mas para uso ativo do admin (não um cohort
    histórico): concede Premium vitalício a uma conta específica,
    escolhida manualmente pelo admin pra testar o produto, também sem
    passar por Stripe — nunca toca `plan`/`stripe_customer_id`/
    `stripe_subscription_id`, então é totalmente reversível (desligar =
    a conta volta pro que ela realmente tinha por baixo) e nunca
    interfere com cobrança real.
    """

    user_id: uuid.UUID
    plan: Plan = Plan.FREE
    billing_cycle: BillingCycle | None = None
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    current_period_end: datetime | None = None
    trial_ends_at: datetime | None = None
    legacy_pro_until: datetime | None = None
    admin_test_access_granted_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def resolve_effective_plan(self, now: datetime | None = None) -> Plan:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Resolve o plano que efetivamente vale agora.
        `admin_test_access_granted_at` preenchido (2026-09-15) vence
        qualquer outra regra — devolve Premium na hora, mesmo que
        `plan` real seja Free — porque é uma concessão manual e
        deliberada do admin, não algo que deva depender de nenhum
        outro estado da conta. Senão, `legacy_pro_until` vencido volta
        pra Free automaticamente (build-context-09 §2.7), sem exigir
        job assíncrono dedicado, mesmo padrão de
        `WhatsappSession.is_expired`. Enquanto `legacy_pro_until` está
        no futuro (ou é `None`), o plano armazenado (`self.plan`) vale
        como está — refletido pelos webhooks do Stripe para contas
        pagas reais.
        """
        if self.admin_test_access_granted_at is not None:
            return Plan.PREMIUM
        reference = now or datetime.now(UTC)
        if self.legacy_pro_until is not None and self.legacy_pro_until < reference:
            return Plan.FREE
        return self.plan


@dataclass
class PlanLimits:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Configuração de limites por plano (build-context-09 §2.2)
    — catálogo editável pelo admin, não constante hardcoded. `None` em
    qualquer campo `int | None` significa ilimitado. Sem campo de
    categoria privada — decisão de escopo #1 do build-context-09, sem
    limite de categoria em nenhum plano.
    """

    plan: Plan
    ai_conversations_per_month: int | None
    ai_reports_per_month: int | None
    whatsapp_bot_messages_per_month: int | None
    csv_exports_per_month: int | None
    priority_support_enabled: bool
    stripe_product_id: str | None = None


@dataclass
class PlanPrice:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Catálogo dinâmico de preços (revisado em 2026-09-10, a
    pedido do usuário) — cada linha espelha um Price real do Stripe,
    gerenciado via `CreateOrUpdatePlanPriceUseCase` (Admin), nunca um
    valor fixo em `.env`. Um `Price` do Stripe é **imutável** em valor
    (a API não permite editar `unit_amount`/`currency`/`recurring`
    depois de criado) — "editar" sempre significa criar uma linha nova
    com `active=True` e arquivar a anterior (`active=False`), nunca uma
    atualização in-place do valor. No máximo uma linha ativa por
    `(plan, billing_cycle)` (índice parcial único na migration).
    """

    plan: Plan
    billing_cycle: BillingCycle
    stripe_price_id: str
    unit_amount_cents: int
    currency: str = "brl"
    active: bool = True
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class BillingSettings:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Configuração singleton de cobrança (build-context-09
    §2.2) — uma linha fixa (`id=1`), `trial_days` editável pelo admin.
    """

    trial_days: int = 7
    id: int = 1


@dataclass
class PaymentEvent:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Log de auditoria de um webhook do Stripe já processado
    (build-context-09 §2.3) — `stripe_event_id` único sustenta a
    idempotência de `HandleStripeWebhookUseCase` (mesmo espírito de
    `processed_bot_messages`/RN-04). `raw_payload` guarda o corpo bruto
    do evento sem normalizar em colunas específicas — cada `event_type`
    do Stripe tem formato próprio, e o objetivo aqui é auditoria/
    exibição (fonte do build-context-11), não regra de negócio em cima
    do payload.
    """

    stripe_event_id: str
    event_type: str
    user_id: uuid.UUID | None = None
    amount_cents: int | None = None
    currency: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
