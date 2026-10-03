from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.feedback.use_cases.list_my_feedback import ListMyFeedbackUseCase
from src.application.feedback.use_cases.submit_feedback import (
    SubmitFeedbackInput,
    SubmitFeedbackUseCase,
)
from src.domain.feedback.value_objects import FeedbackChannel, FeedbackType
from src.domain.user.entities import User
from src.infrastructure.database.repositories.feedback_repository import (
    SqlAlchemyFeedbackRepository,
)
from src.infrastructure.database.session import get_db
from src.presentation.api.v1.dependencies.auth import get_current_user
from src.presentation.api.v1.feedback.schemas import (
    FeedbackCreateRequest,
    FeedbackListResponse,
    FeedbackResponse,
)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    payload: FeedbackCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: POST /feedback (build-context-08 §2.5) — cria um feedback
    do usuário autenticado. `channel` é sempre forçado para `web` aqui,
    nunca lido do corpo da requisição; `user_id` sempre vem do JWT
    (RN-01).
    """
    use_case = SubmitFeedbackUseCase(SqlAlchemyFeedbackRepository(db))
    feedback = await use_case.execute(
        SubmitFeedbackInput(
            user_id=current_user.id,
            channel=FeedbackChannel.WEB,
            message=payload.message,
            type=FeedbackType(payload.type) if payload.type else None,
            nps_score=payload.nps_score,
            subject=payload.subject,
        )
    )
    await db.commit()
    return FeedbackResponse.from_entity(feedback)


@router.get("/me", response_model=FeedbackListResponse)
async def list_my_feedback(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackListResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: GET /feedback/me (build-context-08 §2.5) — histórico
    paginado do próprio usuário autenticado, sempre filtrado por
    `user_id` do token (RN-01), ignorando qualquer filtro de outro
    usuário.
    """
    use_case = ListMyFeedbackUseCase(SqlAlchemyFeedbackRepository(db))
    result = await use_case.execute(current_user.id, page, page_size)
    return FeedbackListResponse.build(
        items=result.items, page=page, page_size=page_size, total=result.total
    )
