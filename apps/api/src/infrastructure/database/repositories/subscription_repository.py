import uuid
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.subscription.entities import (
    BillingCycle,
    Plan,
    SubscriptionStatus,
)
from src.domain.subscription.entities import (
    BillingSettings as BillingSettingsEntity,
)
from src.domain.subscription.entities import (
    PaymentEvent as PaymentEventEntity,
)
from src.domain.subscription.entities import (
    PlanLimits as PlanLimitsEntity,
)
from src.domain.subscription.entities import (
    PlanPrice as PlanPriceEntity,
)
from src.domain.subscription.entities import (
    Subscription as SubscriptionEntity,
)
from src.domain.subscription.repository import PlanDistribution
from src.infrastructure.database.models.subscription import (
    BillingSettings as BillingSettingsModel,
)
from src.infrastructure.database.models.subscription import (
    CsvExportEvent as CsvExportEventModel,
)
from src.infrastructure.database.models.subscription import (
    PaymentEvent as PaymentEventModel,
)
from src.infrastructure.database.models.subscription import (
    PlanLimits as PlanLimitsModel,
)
from src.infrastructure.database.models.subscription import (
    PlanPrice as PlanPriceModel,
)
from src.infrastructure.database.models.subscription import (
    Subscription as SubscriptionModel,
)


def _to_subscription_entity(model: SubscriptionModel) -> SubscriptionEntity:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Converte o model SQLAlchemy de Subscription na entidade
    de domínio — reaproveitado pelos 3 métodos de leitura do
    repositório.
    """
    return SubscriptionEntity(
        id=model.id,
        user_id=model.user_id,
        plan=Plan(model.plan),
        billing_cycle=BillingCycle(model.billing_cycle) if model.billing_cycle else None,
        status=SubscriptionStatus(model.status),
        stripe_customer_id=model.stripe_customer_id,
        stripe_subscription_id=model.stripe_subscription_id,
        current_period_end=model.current_period_end,
        trial_ends_at=model.trial_ends_at,
        legacy_pro_until=model.legacy_pro_until,
        admin_test_access_granted_at=model.admin_test_access_granted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemySubscriptionRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Implementação concreta de `SubscriptionRepository`
    (build-context-09 §2.1/T6) via SQLAlchemy async.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, subscription: SubscriptionEntity) -> SubscriptionEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Persiste uma nova Subscription — chamada por
        `RegisterUserUseCase`/`LoginWithGoogleUseCase` no cadastro
        (sempre `plan=free`) e pelo backfill de usuários legados.
        """
        model = SubscriptionModel(
            id=subscription.id,
            user_id=subscription.user_id,
            plan=subscription.plan.value,
            billing_cycle=subscription.billing_cycle.value if subscription.billing_cycle else None,
            status=subscription.status.value,
            stripe_customer_id=subscription.stripe_customer_id,
            stripe_subscription_id=subscription.stripe_subscription_id,
            current_period_end=subscription.current_period_end,
            trial_ends_at=subscription.trial_ends_at,
            legacy_pro_until=subscription.legacy_pro_until,
            admin_test_access_granted_at=subscription.admin_test_access_granted_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_subscription_entity(model)

    async def get_by_user_id(self, user_id: uuid.UUID) -> SubscriptionEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Busca 1:1 pela conta — caminho usado por todo
        endpoint autenticado que resolve a assinatura do usuário do
        JWT (RN-01).
        """
        result = await self._session.execute(
            select(SubscriptionModel).where(SubscriptionModel.user_id == user_id)
        )
        model = result.scalar_one_or_none()
        return _to_subscription_entity(model) if model else None

    async def get_by_user_ids(self, user_ids: list[uuid.UUID]) -> list[SubscriptionEntity]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-15
        Descrição: Busca em lote — alimenta `ListUsersUseCase` (Admin),
        uma query só pra página inteira em vez de N+1. Lista vazia
        devolve lista vazia sem tocar o banco (evita um `IN ()` inválido).
        """
        if not user_ids:
            return []
        result = await self._session.execute(
            select(SubscriptionModel).where(SubscriptionModel.user_id.in_(user_ids))
        )
        return [_to_subscription_entity(model) for model in result.scalars().all()]

    async def get_by_stripe_customer_id(self, stripe_customer_id: str) -> SubscriptionEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Lookup reverso usado por `HandleStripeWebhookUseCase`
        — os eventos do Stripe trazem `customer`, nunca o `user_id` do
        Amezia diretamente.
        """
        result = await self._session.execute(
            select(SubscriptionModel).where(
                SubscriptionModel.stripe_customer_id == stripe_customer_id
            )
        )
        model = result.scalar_one_or_none()
        return _to_subscription_entity(model) if model else None

    async def get_by_stripe_subscription_id(
        self, stripe_subscription_id: str
    ) -> SubscriptionEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Lookup reverso pelo id da assinatura no Stripe —
        usado por `customer.subscription.updated`/`.deleted`, que já
        trazem o `id` da assinatura no próprio payload.
        """
        result = await self._session.execute(
            select(SubscriptionModel).where(
                SubscriptionModel.stripe_subscription_id == stripe_subscription_id
            )
        )
        model = result.scalar_one_or_none()
        return _to_subscription_entity(model) if model else None

    async def update(self, subscription: SubscriptionEntity) -> SubscriptionEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Persiste alterações numa Subscription já existente —
        principal ponto de escrita de `HandleStripeWebhookUseCase`
        (sincroniza `plan`/`status`/`current_period_end` a cada
        evento).
        """
        result = await self._session.execute(
            select(SubscriptionModel).where(SubscriptionModel.id == subscription.id)
        )
        model = result.scalar_one()
        model.plan = subscription.plan.value
        model.billing_cycle = subscription.billing_cycle.value if subscription.billing_cycle else None
        model.status = subscription.status.value
        model.stripe_customer_id = subscription.stripe_customer_id
        model.stripe_subscription_id = subscription.stripe_subscription_id
        model.current_period_end = subscription.current_period_end
        model.trial_ends_at = subscription.trial_ends_at
        model.legacy_pro_until = subscription.legacy_pro_until
        model.admin_test_access_granted_at = subscription.admin_test_access_granted_at
        await self._session.flush()
        await self._session.refresh(model)
        return _to_subscription_entity(model)

    async def get_plan_distribution(self) -> PlanDistribution:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Conta assinaturas por plano (build-context-11 §2.1)
        — `trial_pro` separado de `pro` (só Pro em trial; Premium em
        trial entra no bucket `premium`, a spec não define
        `trial_premium`).
        """
        result = await self._session.execute(
            select(
                func.count(
                    case((SubscriptionModel.plan == Plan.FREE.value, 1))
                ),
                func.count(
                    case(
                        (
                            (SubscriptionModel.plan == Plan.PRO.value)
                            & (SubscriptionModel.status != SubscriptionStatus.TRIALING.value),
                            1,
                        )
                    )
                ),
                func.count(case((SubscriptionModel.plan == Plan.PREMIUM.value, 1))),
                func.count(
                    case(
                        (
                            (SubscriptionModel.plan == Plan.PRO.value)
                            & (SubscriptionModel.status == SubscriptionStatus.TRIALING.value),
                            1,
                        )
                    )
                ),
            )
        )
        free, pro, premium, trial_pro = result.one()
        return PlanDistribution(free=free, pro=pro, premium=premium, trial_pro=trial_pro)

    async def list_active_paid(self) -> list[SubscriptionEntity]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Assinaturas de plano pago com status `active`/
        `trialing` — usado pra calcular MRR (build-context-11 §2.1),
        monetizando cada uma pelo preço ativo do seu
        `(plan, billing_cycle)` fora deste repositório (não faz sentido
        este repositório conhecer `plan_prices`).
        """
        result = await self._session.execute(
            select(SubscriptionModel).where(
                SubscriptionModel.plan != Plan.FREE.value,
                SubscriptionModel.status.in_(
                    [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value]
                ),
            )
        )
        return [_to_subscription_entity(model) for model in result.scalars().all()]

    async def count_churn_for_month(self, month_start: datetime) -> tuple[int, int]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: `(ativas_no_início_do_mês, canceladas_neste_mês)`,
        só planos pagos (build-context-11 §2.1). Usa
        `stripe_subscription_id IS NOT NULL` (nunca limpo por
        `HandleStripeWebhookUseCase._handle_subscription_deleted`) como
        marcador de "já foi uma assinatura paga de verdade" — `plan`/
        `billing_cycle`, ao contrário, voltam pra `free`/`None` no
        cancelamento, então não servem pra identificar quem cancelou
        neste mês. "Ativa no início do mês" é uma aproximação: existia
        antes de `month_start` e não estava cancelada antes disso
        (`updated_at` é o único rastro de quando o cancelamento
        aconteceu — não existe `canceled_at` dedicado).
        """
        active_at_start_result = await self._session.execute(
            select(func.count())
            .select_from(SubscriptionModel)
            .where(
                SubscriptionModel.stripe_subscription_id.is_not(None),
                SubscriptionModel.created_at < month_start,
                (SubscriptionModel.status != SubscriptionStatus.CANCELED.value)
                | (SubscriptionModel.updated_at >= month_start),
            )
        )
        canceled_this_month_result = await self._session.execute(
            select(func.count())
            .select_from(SubscriptionModel)
            .where(
                SubscriptionModel.stripe_subscription_id.is_not(None),
                SubscriptionModel.status == SubscriptionStatus.CANCELED.value,
                SubscriptionModel.updated_at >= month_start,
            )
        )
        return active_at_start_result.scalar_one(), canceled_this_month_result.scalar_one()

    async def count_past_due(self) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Assinaturas com `status=past_due` agora — alimenta o
        alerta de pagamentos falhados do Admin (build-context-11 §2.4).
        """
        result = await self._session.execute(
            select(func.count())
            .select_from(SubscriptionModel)
            .where(SubscriptionModel.status == SubscriptionStatus.PAST_DUE.value)
        )
        return result.scalar_one()


class SqlAlchemyPlanLimitsRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Implementação concreta de `PlanLimitsRepository` via
    SQLAlchemy async — leitura do catálogo `plan_limits` e do
    singleton `billing_settings`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_plan(self, plan: Plan) -> PlanLimitsEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Lê o catálogo `plan_limits` pelo plano efetivo —
        usado por `GetMySubscriptionUseCase`/`PlanLimitService` e pelo
        enforcement de Bot WhatsApp/CSV.
        """
        result = await self._session.execute(
            select(PlanLimitsModel).where(PlanLimitsModel.plan == plan.value)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return PlanLimitsEntity(
            plan=Plan(model.plan),
            ai_conversations_per_month=model.ai_conversations_per_month,
            ai_reports_per_month=model.ai_reports_per_month,
            whatsapp_bot_messages_per_month=model.whatsapp_bot_messages_per_month,
            csv_exports_per_month=model.csv_exports_per_month,
            priority_support_enabled=model.priority_support_enabled,
            stripe_product_id=model.stripe_product_id,
        )

    async def get_billing_settings(self) -> BillingSettingsEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: `billing_settings` é singleton (`id=1`, seed na
        migration) — sempre existe uma linha, nunca retorna `None`.
        """
        result = await self._session.execute(
            select(BillingSettingsModel).where(BillingSettingsModel.id == 1)
        )
        model = result.scalar_one()
        return BillingSettingsEntity(trial_days=model.trial_days, id=model.id)

    async def set_stripe_product_id(self, plan: Plan, stripe_product_id: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Grava o Produto Stripe recém-criado (ou reaproveitado)
        pra um plano — chamado por `CreateOrUpdatePlanPriceUseCase` na
        1ª vez que um preço é cadastrado pra esse plano.
        """
        result = await self._session.execute(
            select(PlanLimitsModel).where(PlanLimitsModel.plan == plan.value)
        )
        model = result.scalar_one()
        model.stripe_product_id = stripe_product_id
        await self._session.flush()


def _to_plan_price_entity(model: PlanPriceModel) -> PlanPriceEntity:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Converte o model SQLAlchemy de PlanPrice na entidade de
    domínio — reaproveitado pelos métodos de leitura de
    `SqlAlchemyPlanPriceRepository`.
    """
    return PlanPriceEntity(
        id=model.id,
        plan=Plan(model.plan),
        billing_cycle=BillingCycle(model.billing_cycle),
        stripe_price_id=model.stripe_price_id,
        unit_amount_cents=model.unit_amount_cents,
        currency=model.currency,
        active=model.active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyPlanPriceRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Implementação concreta de `PlanPriceRepository` via
    SQLAlchemy async — catálogo dinâmico de preços (revisado em
    2026-09-10, substitui os `STRIPE_PRICE_*` fixos do `.env`).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active(self, plan: Plan, billing_cycle: BillingCycle) -> PlanPriceEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Preço vigente — usado por `StartCheckoutUseCase`
        pra montar o checkout de um (plano, ciclo).
        """
        result = await self._session.execute(
            select(PlanPriceModel).where(
                PlanPriceModel.plan == plan.value,
                PlanPriceModel.billing_cycle == billing_cycle.value,
                PlanPriceModel.active.is_(True),
            )
        )
        model = result.scalar_one_or_none()
        return _to_plan_price_entity(model) if model else None

    async def get_by_stripe_price_id(self, stripe_price_id: str) -> PlanPriceEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Lookup por id do Stripe, ativo ou arquivado — usado
        por `HandleStripeWebhookUseCase` pra resolver (plano, ciclo)
        de uma assinatura, mesmo quando o Price original já foi
        substituído por um mais novo.
        """
        result = await self._session.execute(
            select(PlanPriceModel).where(PlanPriceModel.stripe_price_id == stripe_price_id)
        )
        model = result.scalar_one_or_none()
        return _to_plan_price_entity(model) if model else None

    async def list_for_plan(self, plan: Plan) -> list[PlanPriceEntity]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Histórico completo (ativos e arquivados) de um
        plano, mais recentes primeiro — alimenta a tela do Admin.
        """
        result = await self._session.execute(
            select(PlanPriceModel)
            .where(PlanPriceModel.plan == plan.value)
            .order_by(PlanPriceModel.created_at.desc())
        )
        return [_to_plan_price_entity(model) for model in result.scalars().all()]

    async def create(self, plan_price: PlanPriceEntity) -> PlanPriceEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Persiste um Price novo (sempre `active=True`) —
        chamado por `CreateOrUpdatePlanPriceUseCase` depois de criar o
        Price correspondente no Stripe.
        """
        model = PlanPriceModel(
            id=plan_price.id,
            plan=plan_price.plan.value,
            billing_cycle=plan_price.billing_cycle.value,
            stripe_price_id=plan_price.stripe_price_id,
            unit_amount_cents=plan_price.unit_amount_cents,
            currency=plan_price.currency,
            active=plan_price.active,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_plan_price_entity(model)

    async def deactivate(self, plan: Plan, billing_cycle: BillingCycle) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Arquiva (`active=False`) o preço vigente de um
        (plano, ciclo) — chamado antes de ativar um Price novo pra a
        mesma combinação (o índice parcial único não permite dois
        ativos ao mesmo tempo).
        """
        result = await self._session.execute(
            select(PlanPriceModel).where(
                PlanPriceModel.plan == plan.value,
                PlanPriceModel.billing_cycle == billing_cycle.value,
                PlanPriceModel.active.is_(True),
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.active = False
            await self._session.flush()


class SqlAlchemyPaymentEventRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Implementação concreta de `PaymentEventRepository` via
    SQLAlchemy async — auditoria/idempotência de webhook do Stripe.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists_by_stripe_event_id(self, stripe_event_id: str) -> bool:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Checagem de idempotência do webhook — primeiro passo
        de `HandleStripeWebhookUseCase.execute`, antes de processar
        qualquer evento.
        """
        result = await self._session.execute(
            select(func.count())
            .select_from(PaymentEventModel)
            .where(PaymentEventModel.stripe_event_id == stripe_event_id)
        )
        return result.scalar_one() > 0

    async def create(self, event: PaymentEventEntity) -> PaymentEventEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Grava a linha de auditoria de um evento já
        processado — chamada ao final de
        `HandleStripeWebhookUseCase.execute`.
        """
        model = PaymentEventModel(
            id=event.id,
            stripe_event_id=event.stripe_event_id,
            event_type=event.event_type,
            user_id=event.user_id,
            amount_cents=event.amount_cents,
            currency=event.currency,
            raw_payload=event.raw_payload,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return PaymentEventEntity(
            id=model.id,
            stripe_event_id=model.stripe_event_id,
            event_type=model.event_type,
            user_id=model.user_id,
            amount_cents=model.amount_cents,
            currency=model.currency,
            raw_payload=model.raw_payload,
            created_at=model.created_at,
        )

    async def list_recent(
        self, limit: int, event_types: list[str] | None = None
    ) -> list[PaymentEventEntity]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Últimos `limit` eventos, mais recente primeiro
        (build-context-11 §2.4) — `event_types` filtra por tipo quando
        informado (ex.: só `checkout.session.completed` pra "Pagamentos
        recentes"), sem filtro nenhum devolve qualquer tipo ("Eventos
        Stripe recentes").
        """
        query = select(PaymentEventModel).order_by(PaymentEventModel.created_at.desc()).limit(limit)
        if event_types is not None:
            query = query.where(PaymentEventModel.event_type.in_(event_types))
        result = await self._session.execute(query)
        return [
            PaymentEventEntity(
                id=model.id,
                stripe_event_id=model.stripe_event_id,
                event_type=model.event_type,
                user_id=model.user_id,
                amount_cents=model.amount_cents,
                currency=model.currency,
                raw_payload=model.raw_payload,
                created_at=model.created_at,
            )
            for model in result.scalars().all()
        ]


class SqlAlchemyCsvExportEventRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Implementação concreta de `CsvExportEventRepository` via
    SQLAlchemy async — contagem de exportações CSV por ciclo
    (build-context-09 §2.6).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_since(self, user_id: uuid.UUID, since: datetime) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Conta exportações do usuário desde `since` (início
        do mês atual) — usado por `enforce_csv_export_limit`.
        """
        result = await self._session.execute(
            select(func.count())
            .select_from(CsvExportEventModel)
            .where(CsvExportEventModel.user_id == user_id, CsvExportEventModel.created_at >= since)
        )
        return result.scalar_one()

    async def create(self, user_id: uuid.UUID) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Grava uma linha de exportação bem-sucedida — chamada
        pelo router só depois do CSV já ter sido gerado.
        """
        self._session.add(CsvExportEventModel(user_id=user_id))
        await self._session.flush()
