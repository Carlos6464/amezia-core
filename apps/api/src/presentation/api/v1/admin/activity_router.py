from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.admin.use_cases.get_admin_activity import GetAdminActivityUseCase
from src.domain.user.entities import User
from src.infrastructure.database.repositories.admin_activity_repository import (
    SqlAlchemyAdminActivityRepository,
)
from src.infrastructure.database.session import get_db
from src.presentation.api.v1.admin.schemas import AdminActivityListResponse
from src.presentation.api.v1.dependencies.auth import get_current_admin_user

router = APIRouter(prefix="/admin/activity", tags=["admin"])


@router.get("", response_model=AdminActivityListResponse)
async def list_admin_activity(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminActivityListResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-11
    Descrição: GET /admin/activity (build-context-11 §2.3/§2.4) — feed
    paginado de atividade recente (cadastro, upgrade/downgrade/
    cancelamento de assinatura), atrás de `get_current_admin_user`
    (RN-01, exceção documentada do módulo Admin).
    """
    use_case = GetAdminActivityUseCase(SqlAlchemyAdminActivityRepository(db))
    result = await use_case.execute(page, page_size)
    return AdminActivityListResponse.from_result(result, page, page_size)
