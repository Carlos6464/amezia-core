import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.subscription.use_cases.create_or_update_plan_price import (
    CreateOrUpdatePlanPriceInput,
    CreateOrUpdatePlanPriceUseCase,
)
from src.application.subscription.use_cases.get_my_subscription import GetMySubscriptionUseCase
from src.application.subscription.use_cases.handle_stripe_webhook import (
    HandleStripeWebhookInput,
    HandleStripeWebhookUseCase,
)
from src.application.subscription.use_cases.list_plan_prices import ListPlanPricesUseCase
from src.application.subscription.use_cases.open_billing_portal import OpenBillingPortalUseCase
from src.application.subscription.use_cases.start_checkout import (
    StartCheckoutInput,
    StartCheckoutUseCase,
)
from src.application.whatsapp_bot.use_cases.process_incoming_whatsapp_message import (
    ProcessIncomingWhatsappMessageInput,
)
from src.domain.subscription.entities import BillingCycle, Plan, SubscriptionStatus
from src.domain.subscription.exceptions import (
    BillingCycleUnavailableError,
    NoBillingAccountError,
)
from src.domain.user.value_objects import Language
from src.infrastructure.config import get_settings
from src.infrastructure.database.models.admin_activity import AdminActivityLog as AdminActivityModel
from src.infrastructure.database.models.subscription import PaymentEvent as PaymentEventModel
from src.infrastructure.database.models.subscription import PlanLimits as PlanLimitsModel
from src.infrastructure.database.models.subscription import PlanPrice as PlanPriceModel
from src.infrastructure.database.models.subscription import Subscription as SubscriptionModel
from src.infrastructure.database.repositories.admin_activity_repository import (
    SqlAlchemyAdminActivityRepository,
)
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemyPaymentEventRepository,
    SqlAlchemyPlanLimitsRepository,
    SqlAlchemyPlanPriceRepository,
    SqlAlchemySubscriptionRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.whatsapp.messages import get_message
from tests.conftest import auth_headers
from tests.test_whatsapp_bot import (
    _build_use_case,
    _FakeAudioTranscriptionPort,
    _FakeChatCompletionPort,
    _FakeWhatsappGateway,
    _make_evolution_instance,
    _make_linked_user,
    _make_payload,
)

pytestmark = pytest.mark.asyncio


async def _seed_plan_price(
    db_session: AsyncSession,
    plan: Plan,
    billing_cycle: BillingCycle,
    *,
    stripe_price_id: str,
    unit_amount_cents: int = 2990,
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: `plan_prices` não tem seed via migration (catálogo
    dinâmico, gerenciado pelo Admin em runtime) — testes que exercitam
    `StartCheckoutUseCase`/`HandleStripeWebhookUseCase` precisam de uma
    linha ativa própria, diferente de `plan_limits` (seed fixo).
    Desativa primeiro qualquer preço já ativo da mesma combinação
    (índice parcial único só permite um) — este projeto não tem banco
    de teste separado (`tests/conftest.py`), e o Postgres de dev já tem
    os 2 preços mensais reais (Pro/Premium) importados via
    `scripts/backfill_existing_stripe_prices.py`; o `UPDATE`/`INSERT`
    aqui só existe dentro do savepoint do teste, revertido no teardown
    — mesmo padrão de `_make_evolution_instance` em
    `test_admin_evolution.py`.
    """
    await db_session.execute(
        update(PlanPriceModel)
        .where(
            PlanPriceModel.plan == plan.value,
            PlanPriceModel.billing_cycle == billing_cycle.value,
            PlanPriceModel.active.is_(True),
        )
        .values(active=False)
    )
    db_session.add(
        PlanPriceModel(
            plan=plan.value,
            billing_cycle=billing_cycle.value,
            stripe_price_id=stripe_price_id,
            unit_amount_cents=unit_amount_cents,
        )
    )
    await db_session.flush()


class _FakePaymentGateway:
    """Substituto de PaymentGatewayPort — nenhuma chamada real ao Stripe."""

    def __init__(self) -> None:
        self.created_customers: list[tuple[str, str]] = []
        self.created_products: list[str] = []
        self.created_prices: list[dict[str, Any]] = []
        self.archived_price_ids: list[str] = []
        self.checkout_calls: list[dict[str, Any]] = []
        self.modify_calls: list[tuple[str, str]] = []
        self.portal_calls: list[tuple[str, str]] = []
        self.next_checkout_url = "https://checkout.stripe.com/fake-session"
        self.next_modify_result: dict[str, Any] = {
            "status": "active",
            "current_period_end": int(time.time()) + 30 * 86400,
        }

    async def create_customer(self, email: str, name: str) -> str:
        customer_id = f"cus_fake_{len(self.created_customers) + 1}"
        self.created_customers.append((email, name))
        return customer_id

    async def create_product(self, name: str, description: str | None = None) -> str:
        product_id = f"prod_fake_{len(self.created_products) + 1}"
        self.created_products.append(name)
        return product_id

    async def create_price(
        self, *, product_id: str, unit_amount_cents: int, currency: str, interval: str
    ) -> str:
        price_id = f"price_fake_{len(self.created_prices) + 1}"
        self.created_prices.append(
            {
                "product_id": product_id,
                "unit_amount_cents": unit_amount_cents,
                "currency": currency,
                "interval": interval,
                "price_id": price_id,
            }
        )
        return price_id

    async def archive_price(self, stripe_price_id: str) -> None:
        self.archived_price_ids.append(stripe_price_id)

    async def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        trial_period_days: int,
        success_url: str,
        cancel_url: str,
    ) -> str:
        self.checkout_calls.append(
            {
                "customer_id": customer_id,
                "price_id": price_id,
                "trial_period_days": trial_period_days,
                "success_url": success_url,
                "cancel_url": cancel_url,
            }
        )
        return self.next_checkout_url

    async def modify_subscription(self, stripe_subscription_id: str, price_id: str) -> dict[str, Any]:
        self.modify_calls.append((stripe_subscription_id, price_id))
        return self.next_modify_result

    async def create_billing_portal_session(self, customer_id: str, return_url: str) -> str:
        self.portal_calls.append((customer_id, return_url))
        return "https://billing.stripe.com/fake-portal"

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> dict[str, Any]:
        return json.loads(payload)


def _stripe_event(event_id: str, event_type: str, data_object: dict[str, Any]) -> bytes:
    return json.dumps({"id": event_id, "type": event_type, "data": {"object": data_object}}).encode()


async def test_get_my_subscription_returns_free_plan_with_limits_for_new_user(
    client: AsyncClient, make_user: Any
) -> None:
    """Toda conta nova nasce com Subscription(plan=free) — RN-01, resolve pelo JWT."""
    _, token = await make_user()

    response = await client.get("/api/v1/subscriptions/me", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["subscription"]["plan"] == "free"
    assert body["subscription"]["effective_plan"] == "free"
    assert body["subscription"]["status"] == "active"
    assert body["plan_limits"]["plan"] == "free"
    assert body["plan_limits"]["ai_conversations_per_month"] == 10
    assert body["plan_limits"]["whatsapp_bot_messages_per_month"] == 60
    assert body["plan_limits"]["csv_exports_per_month"] == 2
    assert body["plan_limits"]["priority_support_enabled"] is False


async def test_get_my_subscription_reflects_admin_granted_test_access(
    client: AsyncClient, make_user: Any
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: `GET /subscriptions/me` já reflete `effective_plan=premium`
    e `is_admin_test_access=true` assim que o admin concede o acesso de
    teste (`PATCH /admin/users/{id}/test-access`) — mesmo sem nenhuma
    assinatura real no Stripe (`plan` bruto continua `free`). Confirma
    de ponta a ponta o motivo de existir o campo `is_admin_test_access`
    na resposta: o frontend usa ele pra esconder a área de plano/
    cobrança pra essa conta (pedido direto do usuário, fora de
    qualquer build-context).
    """
    target, target_token = await make_user(role="user")
    _, admin_token = await make_user(role="admin")

    await client.patch(
        f"/api/v1/admin/users/{target.id}/test-access",
        json={"enabled": True},
        headers=auth_headers(admin_token),
    )

    response = await client.get("/api/v1/subscriptions/me", headers=auth_headers(target_token))

    assert response.status_code == 200
    body = response.json()
    assert body["subscription"]["plan"] == "free"
    assert body["subscription"]["effective_plan"] == "premium"
    assert body["subscription"]["is_admin_test_access"] is True
    assert body["plan_limits"]["ai_conversations_per_month"] is None
    assert body["plan_limits"]["priority_support_enabled"] is True


async def test_registering_a_new_account_creates_a_free_subscription(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """
    `RegisterUserUseCase` nunca pula a criação da Subscription
    (build-context-09 §2.5). `db_session` não é usado diretamente, mas
    precisa ser pedido pra ativar o override de `get_db` — sem ele, o
    endpoint usaria o engine real do módulo (preso ao event loop do 1º
    teste que o importou), derrubando com "Future attached to a
    different loop" (mesma classe de bug documentada em
    `FakeArqPool`/`FakeRedisClient`, `techContext.md`).
    """
    email = f"new-{uuid.uuid4().hex[:10]}@example.com"
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Nova Conta", "email": email, "password": "senha12345"},
    )
    assert register_response.status_code == 201
    token = register_response.json()["access_token"]

    response = await client.get("/api/v1/subscriptions/me", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["subscription"]["plan"] == "free"


async def test_legacy_pro_until_in_the_past_resolves_to_free(
    client: AsyncClient, db_session: AsyncSession, make_user: Any
) -> None:
    """`resolve_effective_plan` trata legacy_pro_until vencido como Free (§2.7)."""
    user, token = await make_user()
    await db_session.execute(
        update(SubscriptionModel)
        .where(SubscriptionModel.user_id == user.id)
        .values(plan="pro", legacy_pro_until=datetime.now(UTC) - timedelta(days=1))
    )
    await db_session.flush()

    response = await client.get("/api/v1/subscriptions/me", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["subscription"]["plan"] == "pro"
    assert body["subscription"]["effective_plan"] == "free"
    assert body["plan_limits"]["plan"] == "free"


async def test_legacy_pro_until_in_the_future_still_resolves_to_pro(
    db_session: AsyncSession, make_user: Any
) -> None:
    user, _ = await make_user()
    await db_session.execute(
        update(SubscriptionModel)
        .where(SubscriptionModel.user_id == user.id)
        .values(plan="pro", legacy_pro_until=datetime.now(UTC) + timedelta(days=1))
    )
    await db_session.flush()

    use_case = GetMySubscriptionUseCase(
        SqlAlchemySubscriptionRepository(db_session), SqlAlchemyPlanLimitsRepository(db_session)
    )
    result = await use_case.execute(user.id)

    assert result.subscription.plan == Plan.PRO
    assert result.subscription.resolve_effective_plan() == Plan.PRO
    assert result.plan_limits.plan == Plan.PRO


async def test_start_checkout_for_new_subscription_creates_customer_and_returns_checkout_url(
    db_session: AsyncSession, make_user: Any
) -> None:
    user, _ = await make_user()
    await _seed_plan_price(
        db_session, Plan.PRO, BillingCycle.MONTHLY, stripe_price_id="price_pro_monthly_seed"
    )
    gateway = _FakePaymentGateway()
    use_case = StartCheckoutUseCase(
        SqlAlchemySubscriptionRepository(db_session),
        SqlAlchemyPlanLimitsRepository(db_session),
        SqlAlchemyPlanPriceRepository(db_session),
        SqlAlchemyUserRepository(db_session),
        gateway,
    )

    result = await use_case.execute(
        StartCheckoutInput(user_id=user.id, plan=Plan.PRO, billing_cycle=BillingCycle.MONTHLY)
    )

    assert result.checkout_url == gateway.next_checkout_url
    assert result.subscription is None
    assert len(gateway.created_customers) == 1
    assert gateway.checkout_calls[0]["price_id"] == "price_pro_monthly_seed"
    assert gateway.checkout_calls[0]["trial_period_days"] == 7

    subscription = await SqlAlchemySubscriptionRepository(db_session).get_by_user_id(user.id)
    assert subscription.stripe_customer_id is not None
    assert subscription.plan == Plan.FREE  # só o webhook ativa de fato


async def test_start_checkout_for_active_subscription_modifies_directly_without_checkout_url(
    db_session: AsyncSession, make_user: Any
) -> None:
    """Decisão confirmada em 2026-09-10 — upgrade/downgrade de assinatura já ativa não usa redirect."""
    user, _ = await make_user()
    await _seed_plan_price(
        db_session, Plan.PREMIUM, BillingCycle.MONTHLY, stripe_price_id="price_premium_monthly_seed"
    )
    await db_session.execute(
        update(SubscriptionModel)
        .where(SubscriptionModel.user_id == user.id)
        .values(
            plan="pro",
            billing_cycle="monthly",
            stripe_customer_id="cus_existing",
            stripe_subscription_id="sub_existing",
        )
    )
    await db_session.flush()
    gateway = _FakePaymentGateway()
    use_case = StartCheckoutUseCase(
        SqlAlchemySubscriptionRepository(db_session),
        SqlAlchemyPlanLimitsRepository(db_session),
        SqlAlchemyPlanPriceRepository(db_session),
        SqlAlchemyUserRepository(db_session),
        gateway,
    )

    result = await use_case.execute(
        StartCheckoutInput(user_id=user.id, plan=Plan.PREMIUM, billing_cycle=BillingCycle.MONTHLY)
    )

    assert result.checkout_url is None
    assert result.subscription is not None
    assert result.subscription.plan == Plan.PREMIUM
    assert result.subscription.status == SubscriptionStatus.ACTIVE
    assert gateway.modify_calls == [("sub_existing", "price_premium_monthly_seed")]
    assert gateway.checkout_calls == []


async def test_start_checkout_for_unavailable_billing_cycle_raises(
    db_session: AsyncSession, make_user: Any
) -> None:
    """Nenhum PlanPrice ativo cadastrado ainda pra essa combinação — 400, não 500."""
    user, _ = await make_user()
    use_case = StartCheckoutUseCase(
        SqlAlchemySubscriptionRepository(db_session),
        SqlAlchemyPlanLimitsRepository(db_session),
        SqlAlchemyPlanPriceRepository(db_session),
        SqlAlchemyUserRepository(db_session),
        _FakePaymentGateway(),
    )

    with pytest.raises(BillingCycleUnavailableError):
        await use_case.execute(
            StartCheckoutInput(user_id=user.id, plan=Plan.PRO, billing_cycle=BillingCycle.ANNUAL)
        )


async def test_open_billing_portal_without_stripe_customer_raises(
    db_session: AsyncSession, make_user: Any
) -> None:
    user, _ = await make_user()
    use_case = OpenBillingPortalUseCase(SqlAlchemySubscriptionRepository(db_session), _FakePaymentGateway())

    with pytest.raises(NoBillingAccountError):
        await use_case.execute(user.id)


async def test_open_billing_portal_with_stripe_customer_returns_url(
    db_session: AsyncSession, make_user: Any
) -> None:
    user, _ = await make_user()
    await db_session.execute(
        update(SubscriptionModel)
        .where(SubscriptionModel.user_id == user.id)
        .values(stripe_customer_id="cus_existing")
    )
    await db_session.flush()
    gateway = _FakePaymentGateway()
    use_case = OpenBillingPortalUseCase(SqlAlchemySubscriptionRepository(db_session), gateway)

    url = await use_case.execute(user.id)

    assert url == "https://billing.stripe.com/fake-portal"
    assert gateway.portal_calls == [("cus_existing", f"{get_settings().FRONTEND_URL}/settings/plans")]


async def test_webhook_checkout_completed_sets_stripe_subscription_id(
    db_session: AsyncSession, make_user: Any
) -> None:
    user, _ = await make_user()
    await db_session.execute(
        update(SubscriptionModel)
        .where(SubscriptionModel.user_id == user.id)
        .values(stripe_customer_id="cus_checkout_test")
    )
    await db_session.flush()
    use_case = HandleStripeWebhookUseCase(
        SqlAlchemySubscriptionRepository(db_session),
        SqlAlchemyPaymentEventRepository(db_session),
        SqlAlchemyPlanPriceRepository(db_session),
        _FakePaymentGateway(),
        SqlAlchemyUserRepository(db_session),
        SqlAlchemyAdminActivityRepository(db_session),
    )

    await use_case.execute(
        HandleStripeWebhookInput(
            payload=_stripe_event(
                "evt_1",
                "checkout.session.completed",
                {
                    "customer": "cus_checkout_test",
                    "subscription": "sub_new_123",
                    "amount_total": 4990,
                    "currency": "brl",
                },
            ),
            sig_header="fake",
        )
    )

    subscription = await SqlAlchemySubscriptionRepository(db_session).get_by_user_id(user.id)
    assert subscription.stripe_subscription_id == "sub_new_123"

    event = await db_session.execute(
        select(PaymentEventModel).where(PaymentEventModel.stripe_event_id == "evt_1")
    )
    payment_event = event.scalar_one()
    assert payment_event.user_id == user.id
    assert payment_event.amount_cents == 4990


async def test_webhook_subscription_updated_syncs_plan_status_and_period_end(
    db_session: AsyncSession, make_user: Any
) -> None:
    user, _ = await make_user()
    await _seed_plan_price(
        db_session, Plan.PREMIUM, BillingCycle.MONTHLY, stripe_price_id="price_premium_webhook_seed"
    )
    await db_session.execute(
        update(SubscriptionModel)
        .where(SubscriptionModel.user_id == user.id)
        .values(stripe_customer_id="cus_upd", stripe_subscription_id="sub_upd")
    )
    await db_session.flush()
    use_case = HandleStripeWebhookUseCase(
        SqlAlchemySubscriptionRepository(db_session),
        SqlAlchemyPaymentEventRepository(db_session),
        SqlAlchemyPlanPriceRepository(db_session),
        _FakePaymentGateway(),
        SqlAlchemyUserRepository(db_session),
        SqlAlchemyAdminActivityRepository(db_session),
    )
    period_end = int(time.time()) + 30 * 86400
    trial_end = int(time.time()) + 5 * 86400

    await use_case.execute(
        HandleStripeWebhookInput(
            payload=_stripe_event(
                "evt_2",
                "customer.subscription.updated",
                {
                    "id": "sub_upd",
                    "customer": "cus_upd",
                    "status": "trialing",
                    "current_period_end": period_end,
                    "trial_end": trial_end,
                    "items": {"data": [{"price": {"id": "price_premium_webhook_seed"}}]},
                },
            ),
            sig_header="fake",
        )
    )

    subscription = await SqlAlchemySubscriptionRepository(db_session).get_by_user_id(user.id)
    assert subscription.plan == Plan.PREMIUM
    assert subscription.billing_cycle == BillingCycle.MONTHLY
    assert subscription.status == SubscriptionStatus.TRIALING
    assert int(subscription.current_period_end.timestamp()) == period_end
    assert int(subscription.trial_ends_at.timestamp()) == trial_end


async def test_webhook_subscription_created_syncs_plan_on_first_subscription(
    db_session: AsyncSession, make_user: Any
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: Achado real (2026-09-11) — o Stripe dispara
    `customer.subscription.created`, não `.updated`, na 1ª assinatura
    de um usuário via Checkout. Sem tratar esse evento, `plan` nunca
    saía de `free` mesmo com `checkout.session.completed` processado
    com sucesso e o pagamento aprovado no Stripe. Mesmo cenário de
    `test_webhook_subscription_updated_syncs_plan_status_and_period_end`,
    só que sem `stripe_subscription_id` pré-existente (identifica a
    Subscription só por `stripe_customer_id`, igual uma 1ª assinatura
    de verdade) e com `customer.subscription.created` no lugar de
    `.updated`.
    """
    user, _ = await make_user()
    await _seed_plan_price(
        db_session, Plan.PRO, BillingCycle.MONTHLY, stripe_price_id="price_pro_created_seed"
    )
    await db_session.execute(
        update(SubscriptionModel)
        .where(SubscriptionModel.user_id == user.id)
        .values(stripe_customer_id="cus_new", stripe_subscription_id=None)
    )
    await db_session.flush()
    use_case = HandleStripeWebhookUseCase(
        SqlAlchemySubscriptionRepository(db_session),
        SqlAlchemyPaymentEventRepository(db_session),
        SqlAlchemyPlanPriceRepository(db_session),
        _FakePaymentGateway(),
        SqlAlchemyUserRepository(db_session),
        SqlAlchemyAdminActivityRepository(db_session),
    )
    period_end = int(time.time()) + 30 * 86400

    await use_case.execute(
        HandleStripeWebhookInput(
            payload=_stripe_event(
                "evt_sub_created",
                "customer.subscription.created",
                {
                    "id": "sub_new",
                    "customer": "cus_new",
                    "status": "active",
                    "current_period_end": period_end,
                    "trial_end": None,
                    "items": {"data": [{"price": {"id": "price_pro_created_seed"}}]},
                },
            ),
            sig_header="fake",
        )
    )

    subscription = await SqlAlchemySubscriptionRepository(db_session).get_by_user_id(user.id)
    assert subscription.plan == Plan.PRO
    assert subscription.billing_cycle == BillingCycle.MONTHLY
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.stripe_subscription_id == "sub_new"
    assert int(subscription.current_period_end.timestamp()) == period_end


async def test_webhook_subscription_updated_plan_change_records_admin_activity(
    db_session: AsyncSession, make_user: Any
) -> None:
    """Free -> Premium via webhook grava `user_upgraded` no feed do Admin (build-context-11 §2.3)."""
    user, _ = await make_user()
    await _seed_plan_price(
        db_session, Plan.PREMIUM, BillingCycle.MONTHLY, stripe_price_id="price_premium_activity_seed"
    )
    await db_session.execute(
        update(SubscriptionModel)
        .where(SubscriptionModel.user_id == user.id)
        .values(stripe_customer_id="cus_activity_upd", stripe_subscription_id="sub_activity_upd")
    )
    await db_session.flush()
    use_case = HandleStripeWebhookUseCase(
        SqlAlchemySubscriptionRepository(db_session),
        SqlAlchemyPaymentEventRepository(db_session),
        SqlAlchemyPlanPriceRepository(db_session),
        _FakePaymentGateway(),
        SqlAlchemyUserRepository(db_session),
        SqlAlchemyAdminActivityRepository(db_session),
    )

    await use_case.execute(
        HandleStripeWebhookInput(
            payload=_stripe_event(
                "evt_activity_upd",
                "customer.subscription.updated",
                {
                    "id": "sub_activity_upd",
                    "customer": "cus_activity_upd",
                    "status": "active",
                    "items": {"data": [{"price": {"id": "price_premium_activity_seed"}}]},
                },
            ),
            sig_header="fake",
        )
    )

    activity = await db_session.execute(
        select(AdminActivityModel).where(AdminActivityModel.user_id == user.id)
    )
    events = activity.scalars().all()
    assert len(events) == 1
    assert events[0].event_type == "user_upgraded"
    assert user.name in events[0].message


async def test_webhook_subscription_deleted_reverts_to_free(
    db_session: AsyncSession, make_user: Any
) -> None:
    user, _ = await make_user()
    await db_session.execute(
        update(SubscriptionModel)
        .where(SubscriptionModel.user_id == user.id)
        .values(
            plan="pro",
            billing_cycle="monthly",
            stripe_customer_id="cus_del",
            stripe_subscription_id="sub_del",
        )
    )
    await db_session.flush()
    use_case = HandleStripeWebhookUseCase(
        SqlAlchemySubscriptionRepository(db_session),
        SqlAlchemyPaymentEventRepository(db_session),
        SqlAlchemyPlanPriceRepository(db_session),
        _FakePaymentGateway(),
        SqlAlchemyUserRepository(db_session),
        SqlAlchemyAdminActivityRepository(db_session),
    )

    await use_case.execute(
        HandleStripeWebhookInput(
            payload=_stripe_event(
                "evt_3", "customer.subscription.deleted", {"id": "sub_del", "customer": "cus_del"}
            ),
            sig_header="fake",
        )
    )

    subscription = await SqlAlchemySubscriptionRepository(db_session).get_by_user_id(user.id)
    assert subscription.plan == Plan.FREE
    assert subscription.billing_cycle is None
    assert subscription.status == SubscriptionStatus.CANCELED

    activity = await db_session.execute(
        select(AdminActivityModel).where(AdminActivityModel.user_id == user.id)
    )
    events = activity.scalars().all()
    assert len(events) == 1
    assert events[0].event_type == "user_canceled"


async def test_webhook_invoice_payment_failed_marks_past_due(
    db_session: AsyncSession, make_user: Any
) -> None:
    user, _ = await make_user()
    await db_session.execute(
        update(SubscriptionModel)
        .where(SubscriptionModel.user_id == user.id)
        .values(stripe_customer_id="cus_fail")
    )
    await db_session.flush()
    use_case = HandleStripeWebhookUseCase(
        SqlAlchemySubscriptionRepository(db_session),
        SqlAlchemyPaymentEventRepository(db_session),
        SqlAlchemyPlanPriceRepository(db_session),
        _FakePaymentGateway(),
        SqlAlchemyUserRepository(db_session),
        SqlAlchemyAdminActivityRepository(db_session),
    )

    await use_case.execute(
        HandleStripeWebhookInput(
            payload=_stripe_event(
                "evt_4",
                "invoice.payment_failed",
                {"customer": "cus_fail", "amount_due": 4990, "currency": "brl"},
            ),
            sig_header="fake",
        )
    )

    subscription = await SqlAlchemySubscriptionRepository(db_session).get_by_user_id(user.id)
    assert subscription.status == SubscriptionStatus.PAST_DUE


async def test_webhook_same_event_id_is_processed_only_once(
    db_session: AsyncSession, make_user: Any
) -> None:
    """Idempotência via `payment_events.stripe_event_id` (mesmo espírito da RN-04)."""
    user, _ = await make_user()
    await db_session.execute(
        update(SubscriptionModel)
        .where(SubscriptionModel.user_id == user.id)
        .values(stripe_customer_id="cus_dup")
    )
    await db_session.flush()
    use_case = HandleStripeWebhookUseCase(
        SqlAlchemySubscriptionRepository(db_session),
        SqlAlchemyPaymentEventRepository(db_session),
        SqlAlchemyPlanPriceRepository(db_session),
        _FakePaymentGateway(),
        SqlAlchemyUserRepository(db_session),
        SqlAlchemyAdminActivityRepository(db_session),
    )
    payload = _stripe_event(
        "evt_dup", "invoice.payment_failed", {"customer": "cus_dup", "amount_due": 100, "currency": "brl"}
    )

    await use_case.execute(HandleStripeWebhookInput(payload=payload, sig_header="fake"))
    await use_case.execute(HandleStripeWebhookInput(payload=payload, sig_header="fake"))

    count = await db_session.execute(
        select(PaymentEventModel).where(PaymentEventModel.stripe_event_id == "evt_dup")
    )
    assert len(count.scalars().all()) == 1


async def test_webhook_unhandled_event_type_is_ignored(db_session: AsyncSession) -> None:
    use_case = HandleStripeWebhookUseCase(
        SqlAlchemySubscriptionRepository(db_session),
        SqlAlchemyPaymentEventRepository(db_session),
        SqlAlchemyPlanPriceRepository(db_session),
        _FakePaymentGateway(),
        SqlAlchemyUserRepository(db_session),
        SqlAlchemyAdminActivityRepository(db_session),
    )

    await use_case.execute(
        HandleStripeWebhookInput(
            payload=_stripe_event("evt_unknown", "customer.updated", {}), sig_header="fake"
        )
    )

    count = await db_session.execute(
        select(PaymentEventModel).where(PaymentEventModel.stripe_event_id == "evt_unknown")
    )
    assert count.scalars().all() == []


async def test_create_plan_price_creates_stripe_product_on_first_call(
    db_session: AsyncSession,
) -> None:
    """
    1ª vez que um preço é cadastrado pra um plano — cria o Produto no
    Stripe e grava em `plan_limits`. Zera `stripe_product_id` do Pro
    dentro da transação do teste primeiro — o Postgres de dev já tem o
    Produto real (`scripts/backfill_existing_stripe_prices.py`), e este
    teste especificamente quer exercitar o caminho "ainda não existe"
    (mesmo espírito de `_make_evolution_instance` desativando a
    instância ativa real antes de testar "ativar uma nova").
    """
    await db_session.execute(
        update(PlanLimitsModel).where(PlanLimitsModel.plan == "pro").values(stripe_product_id=None)
    )
    gateway = _FakePaymentGateway()
    use_case = CreateOrUpdatePlanPriceUseCase(
        SqlAlchemyPlanLimitsRepository(db_session),
        SqlAlchemyPlanPriceRepository(db_session),
        gateway,
    )

    plan_price = await use_case.execute(
        CreateOrUpdatePlanPriceInput(
            plan=Plan.PRO, billing_cycle=BillingCycle.MONTHLY, unit_amount_cents=2990
        )
    )

    assert plan_price.active is True
    assert plan_price.unit_amount_cents == 2990
    assert gateway.created_products == ["Amezia Pro"]
    assert gateway.created_prices[0]["interval"] == "month"

    plan_limits = await SqlAlchemyPlanLimitsRepository(db_session).get_by_plan(Plan.PRO)
    assert plan_limits.stripe_product_id == gateway.created_prices[0]["product_id"]
    active = await SqlAlchemyPlanPriceRepository(db_session).get_active(Plan.PRO, BillingCycle.MONTHLY)
    assert active is not None
    assert active.stripe_price_id == plan_price.stripe_price_id


async def test_create_plan_price_archives_previous_price_when_replacing(
    db_session: AsyncSession,
) -> None:
    """
    Editar um preço nunca é in-place — arquiva o Price antigo no
    Stripe e em `plan_prices`, ativa o novo. A 1ª chamada aqui já
    arquiva o Price real do Premium (importado via
    `backfill_existing_stripe_prices.py`) — reaproveitando o cenário
    real em vez de fingir que não existe, já que é exatamente o
    comportamento que importa testar (substituir um preço vigente).
    """
    gateway = _FakePaymentGateway()
    use_case = CreateOrUpdatePlanPriceUseCase(
        SqlAlchemyPlanLimitsRepository(db_session),
        SqlAlchemyPlanPriceRepository(db_session),
        gateway,
    )
    first = await use_case.execute(
        CreateOrUpdatePlanPriceInput(
            plan=Plan.PREMIUM, billing_cycle=BillingCycle.MONTHLY, unit_amount_cents=4990
        )
    )

    second = await use_case.execute(
        CreateOrUpdatePlanPriceInput(
            plan=Plan.PREMIUM, billing_cycle=BillingCycle.MONTHLY, unit_amount_cents=5990
        )
    )

    assert gateway.created_products == []  # Produto real já existia, reaproveitado
    assert gateway.archived_price_ids[-1] == first.stripe_price_id
    assert second.unit_amount_cents == 5990
    assert second.stripe_price_id != first.stripe_price_id

    plan_price_repository = SqlAlchemyPlanPriceRepository(db_session)
    active = await plan_price_repository.get_active(Plan.PREMIUM, BillingCycle.MONTHLY)
    assert active.id == second.id
    history = await plan_price_repository.list_for_plan(Plan.PREMIUM)
    history_ids = {p.id for p in history}
    assert {first.id, second.id} <= history_ids
    assert next(p.active for p in history if p.id == first.id) is False
    assert next(p.active for p in history if p.id == second.id) is True


async def test_list_plan_prices_groups_by_plan(db_session: AsyncSession) -> None:
    """
    A listagem inclui o histórico real (Pro/Premium já têm preço
    mensal importado) — a asserção verifica que o preço recém-ativado
    aparece como o item ativo, sem assumir que o plano começa vazio.
    """
    await _seed_plan_price(db_session, Plan.PRO, BillingCycle.MONTHLY, stripe_price_id="price_pro_list")
    use_case = ListPlanPricesUseCase(SqlAlchemyPlanPriceRepository(db_session))

    catalog = await use_case.execute()

    pro_active = [p for p in catalog[Plan.PRO] if p.active]
    assert len(pro_active) == 1
    assert pro_active[0].stripe_price_id == "price_pro_list"


async def test_admin_can_create_and_list_plan_prices_via_http(
    client: AsyncClient, db_session: AsyncSession, make_user: Any
) -> None:
    """
    GET /admin/plan-prices ponta a ponta contra o router real. Só a
    leitura é testada via HTTP aqui — o router monta `StripeGateway()`
    direto (sem `Depends`, mesmo padrão de `GoogleOAuthClient`), então
    o POST (que chamaria a API real do Stripe) é coberto só no nível
    de use case (`_FakePaymentGateway`, testes acima).
    """
    _, admin_token = await make_user(role="admin")
    await _seed_plan_price(db_session, Plan.PRO, BillingCycle.MONTHLY, stripe_price_id="price_http_seed")

    response = await client.get("/api/v1/admin/plan-prices", headers=auth_headers(admin_token))

    assert response.status_code == 200
    body = response.json()
    assert body["pro"][0]["stripe_price_id"] == "price_http_seed"


async def test_non_admin_cannot_list_plan_prices(client: AsyncClient, make_user: Any) -> None:
    _, token = await make_user()

    response = await client.get("/api/v1/admin/plan-prices", headers=auth_headers(token))

    assert response.status_code == 403


async def test_get_plan_catalog_is_public_and_includes_all_three_plans(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /subscriptions/plans não exige JWT (register-plan-page roda antes do cadastro existir)."""
    await _seed_plan_price(
        db_session, Plan.PRO, BillingCycle.MONTHLY, stripe_price_id="price_catalog_seed"
    )

    response = await client.get("/api/v1/subscriptions/plans")

    assert response.status_code == 200
    body = response.json()
    assert body["free"]["monthly"] is None
    assert body["free"]["limits"]["ai_conversations_per_month"] == 10
    assert body["pro"]["monthly"]["unit_amount_cents"] == 2990
    assert body["pro"]["annual"] is None  # nenhum preço anual cadastrado ainda
    assert body["premium"]["limits"]["priority_support_enabled"] is True


async def test_csv_export_is_blocked_after_monthly_limit(
    client: AsyncClient, db_session: AsyncSession, make_user: Any
) -> None:
    _, token = await make_user()
    await db_session.execute(
        update(PlanLimitsModel).where(PlanLimitsModel.plan == "free").values(csv_exports_per_month=1)
    )
    await db_session.flush()

    first = await client.get(
        "/api/v1/reports/export/csv",
        headers=auth_headers(token),
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
    )
    assert first.status_code == 200

    second = await client.get(
        "/api/v1/reports/export/csv",
        headers=auth_headers(token),
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
    )
    assert second.status_code == 403


async def test_whatsapp_bot_blocks_after_free_plan_message_limit(
    db_session: AsyncSession,
) -> None:
    phone = "5511999990099"
    user = await _make_linked_user(db_session, phone)
    db_session.add(SubscriptionModel(user_id=user.id))
    await db_session.execute(
        update(PlanLimitsModel)
        .where(PlanLimitsModel.plan == "free")
        .values(whatsapp_bot_messages_per_month=2)
    )
    await db_session.flush()
    instance = await _make_evolution_instance(db_session)
    gateway = _FakeWhatsappGateway()
    use_case = _build_use_case(
        db_session,
        chat_completion_port=_FakeChatCompletionPort(),
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    for i in range(3):
        await use_case.execute(
            ProcessIncomingWhatsappMessageInput(
                instance_id=instance.id,
                payload=_make_payload(f"MSG-LIMIT-{i}", phone, text="oi"),
            )
        )

    assert len(gateway.sent) == 3
    assert gateway.sent[2][2] == get_message("common.plan_limit_reached", Language.PT_BR)


async def test_whatsapp_bot_unlimited_plan_never_blocks(db_session: AsyncSession) -> None:
    """Premium (`whatsapp_bot_messages_per_month=None`) nunca conta/bloqueia."""
    phone = "5511999990199"
    user = await _make_linked_user(db_session, phone)
    db_session.add(SubscriptionModel(user_id=user.id, plan="premium"))
    await db_session.flush()
    instance = await _make_evolution_instance(db_session)
    gateway = _FakeWhatsappGateway()
    use_case = _build_use_case(
        db_session,
        chat_completion_port=_FakeChatCompletionPort(),
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    for i in range(3):
        await use_case.execute(
            ProcessIncomingWhatsappMessageInput(
                instance_id=instance.id,
                payload=_make_payload(f"MSG-UNLIMITED-{i}", phone, text="oi"),
            )
        )

    assert len(gateway.sent) == 3
    assert gateway.sent[2][2] != get_message("common.plan_limit_reached", Language.PT_BR)
