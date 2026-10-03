from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ai_usage.use_cases.get_my_ai_usage import GetMyAiUsageUseCase
from src.domain.subscription.exceptions import PlanLimitsNotFoundError, SubscriptionNotFoundError
from src.domain.user.entities import User
from src.infrastructure.database.repositories.ai_usage_repository import (
    SqlAlchemyAiUsageRepository,
)
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemyPlanLimitsRepository,
    SqlAlchemySubscriptionRepository,
)
from src.infrastructure.database.session import get_db
from src.presentation.api.v1.ai_usage.schemas import GetMyAiUsageResponse
from src.presentation.api.v1.dependencies.auth import get_current_user

router = APIRouter(prefix="/ai-usage", tags=["ai-usage"])


@router.get("/me", response_model=GetMyAiUsageResponse)
async def get_my_ai_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GetMyAiUsageResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: GET /ai-usage/me (build-context-10 §2.6/T9, RN-01 —
    sempre pelo usuário do JWT) — uso do ciclo atual + histórico dos
    últimos meses, pra `settings-usage-page`.
    """
    use_case = GetMyAiUsageUseCase(
        SqlAlchemySubscriptionRepository(db),
        SqlAlchemyPlanLimitsRepository(db),
        SqlAlchemyAiUsageRepository(db),
    )
    try:
        result = await use_case.execute(current_user.id)
    except SubscriptionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found") from exc
    except PlanLimitsNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan limits not found") from exc

    return GetMyAiUsageResponse.from_dto(result)
