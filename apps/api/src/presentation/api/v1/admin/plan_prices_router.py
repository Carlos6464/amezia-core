from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.subscription.use_cases.create_or_update_plan_price import (
    CreateOrUpdatePlanPriceInput,
    CreateOrUpdatePlanPriceUseCase,
)
from src.application.subscription.use_cases.list_plan_prices import ListPlanPricesUseCase
from src.domain.subscription.entities import BillingCycle, Plan
from src.domain.subscription.exceptions import PlanLimitsNotFoundError
from src.domain.user.entities import User
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemyPlanLimitsRepository,
    SqlAlchemyPlanPriceRepository,
)
from src.infrastructure.database.session import get_db
from src.infrastructure.payment.stripe_client import StripeGateway
from src.presentation.api.v1.admin.schemas import (
    CreatePlanPriceRequest,
    PaidPlanLiteral,
    PlanPriceResponse,
    PlanPricesCatalogResponse,
)
from src.presentation.api.v1.dependencies.auth import get_current_admin_user

router = APIRouter(prefix="/admin/plan-prices", tags=["admin"])


@router.get("", response_model=PlanPricesCatalogResponse)
async def list_plan_prices(
    _current_admin: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db)
) -> PlanPricesCatalogResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: GET /admin/plan-prices — histórico completo (ativos e
    arquivados) dos preços de Pro/Premium, revisado em 2026-09-10 a
    pedido do usuário (antes eram 4 `STRIPE_PRICE_*` fixos no `.env`,
    sem visibilidade nenhuma pelo sistema).
    """
    use_case = ListPlanPricesUseCase(SqlAlchemyPlanPriceRepository(db))
    catalog = await use_case.execute()
    return PlanPricesCatalogResponse(
        pro=[PlanPriceResponse.from_entity(p) for p in catalog[Plan.PRO]],
        premium=[PlanPriceResponse.from_entity(p) for p in catalog[Plan.PREMIUM]],
    )


@router.post("/{plan}", response_model=PlanPriceResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_plan_price(
    plan: PaidPlanLiteral,
    payload: CreatePlanPriceRequest,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlanPriceResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: POST /admin/plan-prices/{plan} — cria/edita o preço de
    um plano pago pra um ciclo de cobrança, 100% via API (sem passar
    pelo dashboard do Stripe). Como um Price do Stripe é imutável em
    valor, "editar" sempre cria um Price novo e arquiva o anterior da
    mesma combinação (plano, ciclo) — nunca uma atualização in-place.
    """
    use_case = CreateOrUpdatePlanPriceUseCase(
        SqlAlchemyPlanLimitsRepository(db), SqlAlchemyPlanPriceRepository(db), StripeGateway()
    )
    try:
        plan_price = await use_case.execute(
            CreateOrUpdatePlanPriceInput(
                plan=Plan(plan),
                billing_cycle=BillingCycle(payload.billing_cycle),
                unit_amount_cents=payload.unit_amount_cents,
                currency=payload.currency,
            )
        )
    except PlanLimitsNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found") from exc

    await db.commit()
    return PlanPriceResponse.from_entity(plan_price)
