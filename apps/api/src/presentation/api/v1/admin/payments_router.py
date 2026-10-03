from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.admin.use_cases.get_admin_payments import GetAdminPaymentsUseCase
from src.domain.user.entities import User
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemyPaymentEventRepository,
    SqlAlchemyPlanPriceRepository,
    SqlAlchemySubscriptionRepository,
)
from src.infrastructure.database.session import get_db
from src.presentation.api.v1.admin.schemas import AdminPaymentsResponse
from src.presentation.api.v1.dependencies.auth import get_current_admin_user

router = APIRouter(prefix="/admin/payments", tags=["admin"])


@router.get("", response_model=AdminPaymentsResponse)
async def get_admin_payments(
    _current_admin: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db)
) -> AdminPaymentsResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: GET /admin/payments (build-context-11 §2.4/§3.2) — KPIs
    financeiros + feed de eventos Stripe + tabela de pagamentos
    recentes, lendo só `payment_events`/`subscriptions` já persistidos
    via webhook (build-context-09) — nunca chama a API do Stripe ao
    vivo. Atrás de `get_current_admin_user` (RN-01, exceção documentada
    do módulo Admin).
    """
    use_case = GetAdminPaymentsUseCase(
        subscription_repository=SqlAlchemySubscriptionRepository(db),
        payment_event_repository=SqlAlchemyPaymentEventRepository(db),
        plan_price_repository=SqlAlchemyPlanPriceRepository(db),
    )
    result = await use_case.execute()
    return AdminPaymentsResponse.from_dto(result)
