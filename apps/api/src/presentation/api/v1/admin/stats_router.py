from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.admin.use_cases.get_admin_stats import GetAdminStatsUseCase
from src.domain.user.entities import User
from src.infrastructure.database.repositories.ai_usage_repository import (
    SqlAlchemyAiUsageRepository,
)
from src.infrastructure.database.repositories.conversation_repository import (
    SqlAlchemyConversationRepository,
)
from src.infrastructure.database.repositories.feedback_repository import (
    SqlAlchemyFeedbackRepository,
)
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemyPlanPriceRepository,
    SqlAlchemySubscriptionRepository,
)
from src.infrastructure.database.repositories.transaction_repository import (
    SqlAlchemyTransactionRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.repositories.whatsapp_bot_repository import (
    SqlAlchemyProcessedBotMessageRepository,
)
from src.infrastructure.database.session import get_db
from src.presentation.api.v1.admin.schemas import AdminStatsResponse
from src.presentation.api.v1.dependencies.auth import get_current_admin_user

router = APIRouter(prefix="/admin/stats", tags=["admin"])


@router.get("", response_model=AdminStatsResponse)
async def get_admin_stats(
    _current_admin: User = Depends(get_current_admin_user), db: AsyncSession = Depends(get_db)
) -> AdminStatsResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: GET /admin/stats — KPIs globais da Visão Geral do Admin
    (build-context-06 §2.3, estendido pelo build-context-11 §2.1 —
    DAU/MAU, assinaturas por plano, MRR, churn, uso por canal), atrás
    de `get_current_admin_user` (RN-01, exceção documentada deste
    módulo).
    """
    use_case = GetAdminStatsUseCase(
        user_repository=SqlAlchemyUserRepository(db),
        feedback_repository=SqlAlchemyFeedbackRepository(db),
        transaction_repository=SqlAlchemyTransactionRepository(db),
        conversation_repository=SqlAlchemyConversationRepository(db),
        processed_bot_message_repository=SqlAlchemyProcessedBotMessageRepository(db),
        subscription_repository=SqlAlchemySubscriptionRepository(db),
        plan_price_repository=SqlAlchemyPlanPriceRepository(db),
        ai_usage_repository=SqlAlchemyAiUsageRepository(db),
    )
    stats = await use_case.execute()
    return AdminStatsResponse.from_dto(stats)
