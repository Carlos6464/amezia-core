from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.admin.use_cases.list_feedback import ListFeedbackUseCase
from src.domain.feedback.value_objects import FeedbackChannel
from src.domain.user.entities import User
from src.infrastructure.database.repositories.feedback_repository import (
    SqlAlchemyFeedbackRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.session import get_db
from src.presentation.api.v1.admin.schemas import (
    FeedbackChannelLiteral,
    FeedbackResponse,
    PaginatedResponse,
)
from src.presentation.api.v1.dependencies.auth import get_current_admin_user

router = APIRouter(prefix="/admin/feedback", tags=["admin"])


@router.get("", response_model=PaginatedResponse[FeedbackResponse])
async def list_feedback(
    channel: FeedbackChannelLiteral | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[FeedbackResponse]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: GET /admin/feedback — listagem paginada de feedbacks
    (build-context-06 §2.3/§2.9), filtros de canal e busca no texto da
    mensagem.
    """
    use_case = ListFeedbackUseCase(SqlAlchemyFeedbackRepository(db), SqlAlchemyUserRepository(db))
    result = await use_case.execute(
        page, page_size, FeedbackChannel(channel) if channel else None, search
    )
    return PaginatedResponse.build(
        items=[FeedbackResponse.from_dto(item) for item in result.items],
        page=page,
        page_size=page_size,
        total=result.total,
    )
