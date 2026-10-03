from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.subscription.use_cases.get_my_subscription import GetMySubscriptionUseCase
from src.application.subscription.use_cases.get_plan_catalog import GetPlanCatalogUseCase
from src.application.subscription.use_cases.open_billing_portal import OpenBillingPortalUseCase
from src.application.subscription.use_cases.start_checkout import (
    StartCheckoutInput,
    StartCheckoutUseCase,
)
from src.domain.subscription.entities import BillingCycle, Plan
from src.domain.subscription.exceptions import (
    BillingCycleUnavailableError,
    NoBillingAccountError,
    SubscriptionNotFoundError,
)
from src.domain.user.entities import User
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemyPlanLimitsRepository,
    SqlAlchemyPlanPriceRepository,
    SqlAlchemySubscriptionRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.session import get_db
from src.infrastructure.payment.stripe_client import StripeGateway
from src.presentation.api.v1.dependencies.auth import get_current_user
from src.presentation.api.v1.subscriptions.schemas import (
    BillingPortalResponse,
    CheckoutRequest,
    CheckoutResponse,
    GetMySubscriptionResponse,
    PlanCatalogEntryResponse,
    PlanCatalogResponse,
    PlanLimitsResponse,
    SubscriptionResponse,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/plans", response_model=PlanCatalogResponse)
async def get_plan_catalog(db: AsyncSession = Depends(get_db)) -> PlanCatalogResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: GET /subscriptions/plans — rota **pública** (sem JWT),
    catálogo de planos pra exibir preço/limites reais nas telas
    `register-plan-page` (antes da conta existir) e
    `settings-plans-page`. Só dado de catálogo (preço, limite), nunca
    dado de conta — RN-01 não se aplica aqui por não haver usuário
    nenhum envolvido.
    """
    use_case = GetPlanCatalogUseCase(
        SqlAlchemyPlanLimitsRepository(db), SqlAlchemyPlanPriceRepository(db)
    )
    entries = {entry.plan.value: PlanCatalogEntryResponse.from_entry(entry) for entry in await use_case.execute()}
    return PlanCatalogResponse(free=entries["free"], pro=entries["pro"], premium=entries["premium"])


@router.get("/me", response_model=GetMySubscriptionResponse)
async def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GetMySubscriptionResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: GET /subscriptions/me (build-context-09 §2.1, RN-01) —
    sempre resolve pelo usuário do JWT, nunca aceita `user_id` externo.
    """
    use_case = GetMySubscriptionUseCase(
        SqlAlchemySubscriptionRepository(db), SqlAlchemyPlanLimitsRepository(db)
    )
    try:
        result = await use_case.execute(current_user.id)
    except SubscriptionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found") from exc

    return GetMySubscriptionResponse(
        subscription=SubscriptionResponse.from_entity(result.subscription),
        plan_limits=PlanLimitsResponse.from_entity(result.plan_limits),
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def start_checkout(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: POST /subscriptions/checkout (build-context-09 §2.5
    passos 1-2) — cadastro com plano pago ou upgrade/downgrade de
    plano já assinado, mesmo endpoint nos dois casos.
    """
    use_case = StartCheckoutUseCase(
        SqlAlchemySubscriptionRepository(db),
        SqlAlchemyPlanLimitsRepository(db),
        SqlAlchemyPlanPriceRepository(db),
        SqlAlchemyUserRepository(db),
        StripeGateway(),
    )
    try:
        result = await use_case.execute(
            StartCheckoutInput(
                user_id=current_user.id,
                plan=Plan(payload.plan),
                billing_cycle=BillingCycle(payload.billing_cycle),
            )
        )
    except SubscriptionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found") from exc
    except BillingCycleUnavailableError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    await db.commit()
    return CheckoutResponse(
        checkout_url=result.checkout_url,
        subscription=(
            SubscriptionResponse.from_entity(result.subscription) if result.subscription else None
        ),
    )


@router.post("/billing-portal", response_model=BillingPortalResponse)
async def open_billing_portal(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillingPortalResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: POST /subscriptions/billing-portal (build-context-09
    §2.5 passo 3) — cria a sessão do Stripe Customer Portal
    (cancelamento, troca de cartão, histórico de fatura).
    """
    use_case = OpenBillingPortalUseCase(SqlAlchemySubscriptionRepository(db), StripeGateway())
    try:
        url = await use_case.execute(current_user.id)
    except SubscriptionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found") from exc
    except NoBillingAccountError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No billing account yet — never checked out"
        ) from exc

    return BillingPortalResponse(url=url)
