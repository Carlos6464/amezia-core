from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.admin.use_cases.login_admin import AdminLoginInput, AdminLoginUseCase
from src.domain.user.exceptions import InvalidCredentialsError
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.session import get_db
from src.infrastructure.security.jwt_service import JwtService
from src.infrastructure.security.password_hasher import PasswordHasher
from src.presentation.api.v1.admin.schemas import AdminLoginRequest
from src.presentation.api.v1.auth.cookies import set_refresh_cookie
from src.presentation.api.v1.auth.schemas import AuthTokensResponse, UserResponse

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


@router.post("/login", response_model=AuthTokensResponse)
async def admin_login(
    payload: AdminLoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> AuthTokensResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: POST /admin/auth/login — porta de entrada própria e
    isolada do painel administrativo (decisão de produto de 2026-08-15:
    painel cliente e painel admin são telas separadas, sem link cruzado
    entre os dois). Mesma sessão JWT única do resto do sistema (RN-08) —
    reaproveita o mesmo cookie de refresh (`set_refresh_cookie`), só a
    checagem de `role=admin` (AdminLoginUseCase) é exclusiva desta rota.
    Uma conta sem `role=admin` recebe a mesma resposta de "credenciais
    inválidas" de uma senha errada — nunca revela que a conta existe.
    """
    use_case = AdminLoginUseCase(
        user_repository=SqlAlchemyUserRepository(db),
        password_hasher=PasswordHasher(),
        jwt_service=JwtService(),
    )
    try:
        result = await use_case.execute(
            AdminLoginInput(email=payload.email, password=payload.password)
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password") from exc

    await db.commit()
    set_refresh_cookie(response, result.refresh_token)
    return AuthTokensResponse(
        user=UserResponse.from_entity(result.user), access_token=result.access_token
    )
