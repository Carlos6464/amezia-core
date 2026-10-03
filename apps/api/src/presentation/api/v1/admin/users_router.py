import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.admin.use_cases.change_user_role import (
    ChangeUserRoleInput,
    ChangeUserRoleUseCase,
)
from src.application.admin.use_cases.delete_user import DeleteUserInput, DeleteUserUseCase
from src.application.admin.use_cases.get_user import GetUserUseCase
from src.application.admin.use_cases.list_users import ListUsersUseCase
from src.application.admin.use_cases.set_admin_test_access import (
    SetAdminTestAccessInput,
    SetAdminTestAccessUseCase,
)
from src.domain.subscription.exceptions import SubscriptionNotFoundError
from src.domain.user.entities import User
from src.domain.user.exceptions import CannotDeleteSelfError, UserNotFoundError
from src.domain.user.repository import UserFilters
from src.infrastructure.database.repositories.admin_activity_repository import (
    SqlAlchemyAdminActivityRepository,
)
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemySubscriptionRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.session import get_db
from src.presentation.api.v1.admin.schemas import (
    AdminUserResponse,
    ChangeUserRoleRequest,
    PaginatedResponse,
    SetTestAccessRequest,
    UserRoleLiteral,
)
from src.presentation.api.v1.dependencies.auth import get_current_admin_user

router = APIRouter(prefix="/admin/users", tags=["admin"])


def _parse_user_public_id(raw: str) -> uuid.UUID:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: `users.id` já é UUID (build-context-01) — não existe um
    `public_id`/ULID separado para User (este módulo não redefine o
    agregado). O path param segue chamado `public_id` para bater com o
    nome usado na spec do build-context-06, mas seu valor é o `id` real.
    Um UUID malformado é tratado como "não encontrado" (404), não como
    erro de validação — mesmo padrão de `_parse_transaction_public_id`.
    """
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc


@router.get("", response_model=PaginatedResponse[AdminUserResponse])
async def list_users(
    search: str | None = Query(default=None),
    role: UserRoleLiteral | None = Query(default=None),
    has_phone: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AdminUserResponse]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: GET /admin/users — listagem paginada com filtros de
    busca (nome/email), papel e vínculo de WhatsApp (build-context-06
    §2.3).
    """
    use_case = ListUsersUseCase(SqlAlchemyUserRepository(db), SqlAlchemySubscriptionRepository(db))
    result = await use_case.execute(
        UserFilters(search=search, role=role, has_phone=has_phone), page, page_size
    )
    return PaginatedResponse.build(
        items=[AdminUserResponse.from_entity(row) for row in result.items],
        page=page,
        page_size=page_size,
        total=result.total,
    )


@router.get("/{public_id}", response_model=AdminUserResponse)
async def get_user(
    public_id: str,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: GET /admin/users/{public_id} — detalhe de um usuário.
    """
    use_case = GetUserUseCase(SqlAlchemyUserRepository(db), SqlAlchemySubscriptionRepository(db))
    try:
        row = await use_case.execute(_parse_user_public_id(public_id))
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc
    return AdminUserResponse.from_entity(row)


@router.patch("/{public_id}/role", response_model=AdminUserResponse)
async def change_user_role(
    public_id: str,
    payload: ChangeUserRoleRequest,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: PATCH /admin/users/{public_id}/role — troca de papel
    (`user`/`admin`) de um usuário.
    """
    use_case = ChangeUserRoleUseCase(SqlAlchemyUserRepository(db), SqlAlchemySubscriptionRepository(db))
    try:
        row = await use_case.execute(
            ChangeUserRoleInput(user_id=_parse_user_public_id(public_id), role=payload.role)
        )
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc

    await db.commit()
    return AdminUserResponse.from_entity(row)


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    public_id: str,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: DELETE /admin/users/{public_id} — exclui permanentemente
    a conta de um usuário (RN-03, cascade via FK). Fora de qualquer
    build-context — pedido direto do usuário pra poder remover contas
    de teste/debug criadas em produção sem acesso direto ao banco.
    """
    use_case = DeleteUserUseCase(
        SqlAlchemyUserRepository(db), SqlAlchemyAdminActivityRepository(db)
    )
    try:
        await use_case.execute(
            DeleteUserInput(
                user_id=_parse_user_public_id(public_id),
                requesting_admin_id=current_admin.id,
            )
        )
    except CannotDeleteSelfError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Admin cannot delete their own account"
        ) from exc
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc

    await db.commit()


@router.patch("/{public_id}/test-access", response_model=AdminUserResponse)
async def set_test_access(
    public_id: str,
    payload: SetTestAccessRequest,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: PATCH /admin/users/{public_id}/test-access — concede
    (`enabled=true`) ou revoga (`enabled=false`) o acesso de teste
    Premium vitalício de um usuário, sem passar por Stripe. Fora de
    qualquer build-context — pedido direto do usuário pra poder testar
    o produto à vontade em contas escolhidas manualmente, sem gerar
    cobrança real.
    """
    use_case = SetAdminTestAccessUseCase(
        SqlAlchemySubscriptionRepository(db),
        SqlAlchemyUserRepository(db),
        SqlAlchemyAdminActivityRepository(db),
    )
    try:
        row = await use_case.execute(
            SetAdminTestAccessInput(
                user_id=_parse_user_public_id(public_id), enabled=payload.enabled
            )
        )
    except (UserNotFoundError, SubscriptionNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc

    await db.commit()
    return AdminUserResponse.from_entity(row)
