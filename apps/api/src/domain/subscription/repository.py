import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.domain.subscription.entities import (
    BillingCycle,
    BillingSettings,
    PaymentEvent,
    Plan,
    PlanLimits,
    PlanPrice,
    Subscription,
)


@dataclass
class PlanDistribution:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: Contagem de assinaturas por plano (build-context-11
    §2.1) — `trial_pro` é contado à parte de `pro` (mesmo espírito do
    protótipo, "Em trial: Trial Pro 13%"); trial de Premium entra no
    bucket `premium` — a spec só define esses 4 campos, sem
    `trial_premium`.
    """

    free: int
    pro: int
    premium: int
    trial_pro: int


class SubscriptionRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Interface de persistência de Subscription
    (build-context-09 §2.1) — implementada em
    infrastructure/database/repositories/subscription_repository.py.
    Os 3 lookups por Stripe id existem porque os webhooks (§2.5 passo
    5) só trazem `customer`/`subscription` do Stripe no payload, nunca
    o `user_id` do Amezia diretamente.
    """

    async def create(self, subscription: Subscription) -> Subscription: ...

    async def get_by_user_id(self, user_id: uuid.UUID) -> Subscription | None: ...

    async def get_by_user_ids(self, user_ids: list[uuid.UUID]) -> list[Subscription]:
        """
        Busca em lote (2026-09-15) — usada por `ListUsersUseCase` pra
        resolver o plano efetivo/status de teste de uma página inteira
        de usuários do Admin numa query só, em vez de um `get_by_user_id`
        por linha (N+1 evitável, diferente do top-10 de
        `GetAdminAiUsageOverviewUseCase`, que tolera N+1 por ser um
        recorte pequeno e fixo).
        """
        ...

    async def get_by_stripe_customer_id(self, stripe_customer_id: str) -> Subscription | None: ...

    async def get_by_stripe_subscription_id(
        self, stripe_subscription_id: str
    ) -> Subscription | None: ...

    async def update(self, subscription: Subscription) -> Subscription: ...

    async def get_plan_distribution(self) -> PlanDistribution:
        """Contagem de assinaturas por plano (build-context-11 §2.1) — alimenta o gráfico "Usuários por plano"."""
        ...

    async def list_active_paid(self) -> list[Subscription]:
        """
        Assinaturas de plano pago (`plan != free`) com status
        `active`/`trialing` — usado por `GetAdminStatsUseCase`/
        `GetAdminPaymentsUseCase` pra calcular MRR (build-context-11
        §2.1), monetizando cada uma pelo preço ativo do seu
        `(plan, billing_cycle)`.
        """
        ...

    async def count_churn_for_month(self, month_start: datetime) -> tuple[int, int]:
        """
        `(ativas_no_início_do_mês, canceladas_neste_mês)` — só planos
        pagos. "Cancelada neste mês" é `status=canceled` com
        `updated_at >= month_start` (proxy — não existe `canceled_at`
        dedicado). Base usada pelo cálculo de churn (build-context-11
        §2.1): cancelamentos ÷ base do início do período.
        """
        ...

    async def count_past_due(self) -> int:
        """Assinaturas com `status=past_due` agora — alimenta o alerta de pagamentos falhados (build-context-11 §2.4)."""
        ...


class PlanLimitsRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Interface de leitura do catálogo `plan_limits` (por
    plano) e da configuração singleton `billing_settings` — as duas
    tabelas de configuração editável pelo admin do build-context-09,
    sem FK pra usuário (não são dado de conta, são catálogo).
    """

    async def get_by_plan(self, plan: Plan) -> PlanLimits | None: ...

    async def get_billing_settings(self) -> BillingSettings: ...

    async def set_stripe_product_id(self, plan: Plan, stripe_product_id: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Grava o Produto Stripe recém-criado (ou reaproveitado)
        pra um plano — chamado por `CreateOrUpdatePlanPriceUseCase` na
        1ª vez que um preço é cadastrado pra esse plano.
        """
        ...


class PlanPriceRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Interface de persistência do catálogo dinâmico de preços
    `plan_prices` (revisado em 2026-09-10) — implementada em
    infrastructure/database/repositories/subscription_repository.py.
    """

    async def get_active(self, plan: Plan, billing_cycle: BillingCycle) -> PlanPrice | None:
        """Preço vigente pra um (plano, ciclo) — usado por `StartCheckoutUseCase` pra montar o checkout."""
        ...

    async def get_by_stripe_price_id(self, stripe_price_id: str) -> PlanPrice | None:
        """
        Lookup por id do Stripe, ativo ou arquivado — usado por
        `HandleStripeWebhookUseCase` pra resolver (plano, ciclo) de uma
        assinatura, mesmo quando o Price original já foi substituído.
        """
        ...

    async def list_for_plan(self, plan: Plan) -> list[PlanPrice]:
        """Todo o histórico de preços (ativos e arquivados) de um plano — alimenta a tela do Admin."""
        ...

    async def create(self, plan_price: PlanPrice) -> PlanPrice: ...

    async def deactivate(self, plan: Plan, billing_cycle: BillingCycle) -> None:
        """Arquiva (marca `active=False`) o preço vigente de um (plano, ciclo), se existir."""
        ...


class PaymentEventRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Interface de persistência de `payment_events`
    (build-context-09 §2.3) — `exists_by_stripe_event_id` sustenta a
    idempotência de `HandleStripeWebhookUseCase` (mesmo espírito de
    `processed_bot_messages`/RN-04, reentrega do Stripe não deve
    processar o mesmo evento duas vezes).
    """

    async def exists_by_stripe_event_id(self, stripe_event_id: str) -> bool: ...

    async def create(self, event: PaymentEvent) -> PaymentEvent: ...

    async def list_recent(self, limit: int, event_types: list[str] | None = None) -> list[PaymentEvent]:
        """
        Últimos `limit` eventos, mais recente primeiro (build-context-11
        §2.4) — usado por `GetAdminPaymentsUseCase` tanto pro feed
        "Eventos Stripe recentes" (`event_types=None`, qualquer tipo)
        quanto pra tabela "Pagamentos recentes" (`event_types=
        ["checkout.session.completed"]`, só eventos com dinheiro
        associado).
        """
        ...


class CsvExportEventRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Interface de persistência de `csv_export_events`
    (build-context-09 §2.3/§2.6) — tabela mínima só pra contar
    exportações de CSV por ciclo, sem guardar o arquivo/conteúdo
    exportado.
    """

    async def count_since(self, user_id: uuid.UUID, since: datetime) -> int: ...

    async def create(self, user_id: uuid.UUID) -> None: ...
