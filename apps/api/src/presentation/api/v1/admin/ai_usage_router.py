from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ai_usage.use_cases.get_admin_ai_usage_overview import (
    GetAdminAiUsageOverviewUseCase,
)
from src.domain.user.entities import User
from src.infrastructure.database.repositories.ai_usage_repository import (
    SqlAlchemyAiUsageRepository,
)
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemySubscriptionRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.session import get_db
from src.presentation.api.v1.admin.schemas import AdminAiUsageOverviewResponse
from src.presentation.api.v1.dependencies.auth import get_current_admin_user

router = APIRouter(prefix="/admin/ai-usage", tags=["admin"])


@router.get("/overview", response_model=AdminAiUsageOverviewResponse)
async def get_admin_ai_usage_overview(
    _current_admin: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db)
) -> AdminAiUsageOverviewResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: GET /admin/ai-usage/overview (build-context-10 §2.6/T9)
    — agregado do mês corrente + top consumidores, atrás de
    `get_current_admin_user` (RN-01, exceção documentada do módulo
    Admin).
    """
    use_case = GetAdminAiUsageOverviewUseCase(
        SqlAlchemyAiUsageRepository(db),
        SqlAlchemyUserRepository(db),
        SqlAlchemySubscriptionRepository(db),
    )
    result = await use_case.execute()
    return AdminAiUsageOverviewResponse.from_dto(result)
