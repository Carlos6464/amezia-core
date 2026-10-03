from urllib.parse import urlencode

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.user.use_cases.change_password import (
    ChangePasswordInput,
    ChangePasswordUseCase,
)
from src.application.user.use_cases.delete_account import DeleteAccountUseCase
from src.application.user.use_cases.get_current_user import GetCurrentUserUseCase
from src.application.user.use_cases.login import LoginInput, LoginUseCase
from src.application.user.use_cases.login_with_google import (
    LoginWithGoogleInput,
    LoginWithGoogleUseCase,
)
from src.application.user.use_cases.logout import LogoutUseCase
from src.application.user.use_cases.refresh_token import RefreshTokenInput, RefreshTokenUseCase
from src.application.user.use_cases.register_user import RegisterUserInput, RegisterUserUseCase
from src.application.user.use_cases.request_password_reset import (
    RequestPasswordResetInput,
    RequestPasswordResetUseCase,
)
from src.application.user.use_cases.reset_password import ResetPasswordInput, ResetPasswordUseCase
from src.application.user.use_cases.set_password import SetPasswordInput, SetPasswordUseCase
from src.application.user.use_cases.update_onboarding import (
    UpdateOnboardingInput,
    UpdateOnboardingUseCase,
)
from src.application.user.use_cases.update_profile import UpdateProfileInput, UpdateProfileUseCase
from src.domain.user.entities import User
from src.domain.user.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidOrExpiredTokenError,
    PasswordAlreadySetError,
    PasswordNotSetError,
    UserNotFoundError,
)
from src.infrastructure.config import get_settings
from src.infrastructure.database.repositories.admin_activity_repository import (
    SqlAlchemyAdminActivityRepository,
)
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemySubscriptionRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.session import get_db
from src.infrastructure.email.resend_client import ResendEmailClient
from src.infrastructure.oauth.google_client import GoogleOAuthClient
from src.infrastructure.queue.pool import get_arq_pool
from src.infrastructure.security.jwt_service import JwtService
from src.infrastructure.security.password_hasher import PasswordHasher
from src.infrastructure.security.phone_hasher import PhoneHasher
from src.presentation.api.v1.auth.cookies import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
    set_refresh_cookie,
)
from src.presentation.api.v1.auth.schemas import (
    AuthTokensResponse,
    ChangePasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    RefreshResponse,
    RegisterRequest,
    RequestPasswordResetRequest,
    ResetPasswordRequest,
    SetPasswordRequest,
    UpdateOnboardingRequest,
    UpdateProfileRequest,
    UserResponse,
)
from src.presentation.api.v1.dependencies.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

_GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"


@router.post("/register", response_model=AuthTokensResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> AuthTokensResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: POST /auth/register — cria conta local e já autentica
    (grava o cookie de refresh e devolve o access token).
    """
    use_case = RegisterUserUseCase(
        user_repository=SqlAlchemyUserRepository(db),
        password_hasher=PasswordHasher(),
        jwt_service=JwtService(),
        subscription_repository=SqlAlchemySubscriptionRepository(db),
        admin_activity_repository=SqlAlchemyAdminActivityRepository(db),
    )
    try:
        result = await use_case.execute(
            RegisterUserInput(name=payload.name, email=payload.email, password=payload.password)
        )
    except EmailAlreadyExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from exc

    await db.commit()
    set_refresh_cookie(response, result.refresh_token)
    return AuthTokensResponse(
        user=UserResponse.from_entity(result.user), access_token=result.access_token
    )


@router.post("/login", response_model=AuthTokensResponse)
async def login(
    payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> AuthTokensResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: POST /auth/login — autentica por email/senha.
    """
    use_case = LoginUseCase(
        user_repository=SqlAlchemyUserRepository(db),
        password_hasher=PasswordHasher(),
        jwt_service=JwtService(),
    )
    try:
        result = await use_case.execute(LoginInput(email=payload.email, password=payload.password))
    except InvalidCredentialsError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password") from exc

    await db.commit()
    set_refresh_cookie(response, result.refresh_token)
    return AuthTokensResponse(
        user=UserResponse.from_entity(result.user), access_token=result.access_token
    )


@router.post("/login/google", response_model=AuthTokensResponse)
async def login_with_google(
    payload: GoogleLoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> AuthTokensResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: POST /auth/login/google — autentica via id_token do Google
    Identity Services (login, account linking ou cadastro novo).
    """
    use_case = LoginWithGoogleUseCase(
        user_repository=SqlAlchemyUserRepository(db),
        google_client=GoogleOAuthClient(),
        jwt_service=JwtService(),
        subscription_repository=SqlAlchemySubscriptionRepository(db),
        admin_activity_repository=SqlAlchemyAdminActivityRepository(db),
    )
    try:
        result = await use_case.execute(LoginWithGoogleInput(id_token=payload.id_token))
    except InvalidCredentialsError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Google token") from exc

    await db.commit()
    set_refresh_cookie(response, result.refresh_token)
    return AuthTokensResponse(
        user=UserResponse.from_entity(result.user), access_token=result.access_token
    )


@router.get("/google")
async def google_authorize() -> RedirectResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: GET /auth/google — redireciona o browser pra tela de
    consentimento real do Google (fluxo OAuth2 authorization code
    server-side). O botão do frontend é um `<a href="/api/v1/auth/google">`
    puro, 100% estilizável — nenhum widget/iframe do Google é embutido na
    página do app, então não há branding/tamanho fixo pra brigar.
    """
    settings = get_settings()
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    return RedirectResponse(
        url=f"{_GOOGLE_AUTHORIZE_URL}?{urlencode(params)}", status_code=status.HTTP_302_FOUND
    )


@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: GET /auth/google/callback — recebe o `code` (ou `error`,
    se o usuário negou o consentimento) que o Google devolve depois do
    redirect de `google_authorize`, troca por sessão via
    `LoginWithGoogleUseCase` e devolve o browser pra
    `{FRONTEND_URL}/google-callback`, com o access token na query string
    (consumido em memória pelo frontend, nunca em localStorage — RN-08) e
    o refresh token no mesmo cookie HttpOnly dos outros fluxos. Em
    qualquer falha, redireciona com `?error=google_auth_failed` em vez de
    devolver um JSON de erro que o usuário nunca veria (é um redirect de
    topo de página, não uma chamada AJAX).
    """
    settings = get_settings()
    code = request.query_params.get("code")
    error = request.query_params.get("error")

    if error or not code:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/google-callback?{urlencode({'error': 'google_auth_failed'})}"
        )

    use_case = LoginWithGoogleUseCase(
        user_repository=SqlAlchemyUserRepository(db),
        google_client=GoogleOAuthClient(),
        jwt_service=JwtService(),
        subscription_repository=SqlAlchemySubscriptionRepository(db),
        admin_activity_repository=SqlAlchemyAdminActivityRepository(db),
    )
    try:
        result = await use_case.execute(LoginWithGoogleInput(code=code))
    except InvalidCredentialsError:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/google-callback?{urlencode({'error': 'google_auth_failed'})}"
        )

    await db.commit()
    redirect = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/google-callback?{urlencode({'token': result.access_token})}"
    )
    set_refresh_cookie(redirect, result.refresh_token)
    return redirect


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(request: Request, db: AsyncSession = Depends(get_db)) -> RefreshResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: POST /auth/refresh — lê o refresh token do cookie HttpOnly
    (nunca do corpo da requisição) e emite um novo access token.
    """
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing refresh token")

    use_case = RefreshTokenUseCase(
        user_repository=SqlAlchemyUserRepository(db), jwt_service=JwtService()
    )
    try:
        access_token = await use_case.execute(RefreshTokenInput(refresh_token=refresh_token))
    except InvalidOrExpiredTokenError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token"
        ) from exc

    return RefreshResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, _current_user: User = Depends(get_current_user)) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: POST /auth/logout — exige autenticação só para garantir que
    quem chama tinha uma sessão; a ação em si é só limpar o cookie de
    refresh (sem blacklist de token, RN-08).
    """
    await LogoutUseCase().execute()
    clear_refresh_cookie(response)


@router.post("/password-reset/request", status_code=status.HTTP_200_OK)
async def request_password_reset(
    payload: RequestPasswordResetRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: POST /auth/password-reset/request — sempre responde 200,
    exista ou não a conta (anti-enumeração de email).
    """
    use_case = RequestPasswordResetUseCase(
        user_repository=SqlAlchemyUserRepository(db),
        jwt_service=JwtService(),
        email_client=ResendEmailClient(),
    )
    await use_case.execute(RequestPasswordResetInput(email=payload.email))
    return {"detail": "If the email exists, a reset link has been sent"}


@router.post("/password-reset/confirm", status_code=status.HTTP_200_OK)
async def reset_password(
    payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: POST /auth/password-reset/confirm — valida o token do
    email e define a nova senha.
    """
    use_case = ResetPasswordUseCase(
        user_repository=SqlAlchemyUserRepository(db),
        jwt_service=JwtService(),
        password_hasher=PasswordHasher(),
    )
    try:
        await use_case.execute(
            ResetPasswordInput(token=payload.token, new_password=payload.new_password)
        )
    except InvalidOrExpiredTokenError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token") from exc

    await db.commit()
    return {"detail": "Password updated"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: GET /auth/me — retorna o perfil do próprio usuário
    (user_id sempre do JWT, nunca de parâmetro — RN-01).
    """
    use_case = GetCurrentUserUseCase(user_repository=SqlAlchemyUserRepository(db))
    try:
        user = await use_case.execute(current_user.id)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc
    return UserResponse.from_entity(user)


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> UserResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: PATCH /auth/me — atualização parcial de name/phone/language
    do próprio perfil.
    """
    use_case = UpdateProfileUseCase(
        user_repository=SqlAlchemyUserRepository(db), phone_hasher=PhoneHasher(), job_enqueuer=arq_pool
    )
    try:
        user = await use_case.execute(
            UpdateProfileInput(
                user_id=current_user.id,
                name=payload.name,
                phone=payload.phone,
                language=payload.language,
            )
        )
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc

    await db.commit()
    return UserResponse.from_entity(user)


@router.patch("/me/onboarding", response_model=UserResponse)
async def update_onboarding(
    payload: UpdateOnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: PATCH /auth/me/onboarding — marca (`true`, ao concluir o
    tour/checklist) ou desmarca (`false`, "reiniciar tour" em
    Configurações) o onboarding guiado. Separado de `PATCH /auth/me`
    porque é estado de produto, não dado de perfil editável em formulário.
    """
    use_case = UpdateOnboardingUseCase(user_repository=SqlAlchemyUserRepository(db))
    try:
        user = await use_case.execute(
            UpdateOnboardingInput(
                user_id=current_user.id, onboarding_completed=payload.onboarding_completed
            )
        )
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc

    await db.commit()
    return UserResponse.from_entity(user)


@router.post("/me/password", response_model=UserResponse)
async def set_password(
    payload: SetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: POST /auth/me/password — define a senha local pela
    primeira vez, para contas só-OAuth (sem `password_hash` ainda).
    Diferente de `PATCH /me/password` (troca, exige senha atual), esta
    rota corrige a lacuna real da tela de perfil, que antes não tinha
    como uma conta vinculada ao Google ganhar uma senha local.
    """
    use_case = SetPasswordUseCase(
        user_repository=SqlAlchemyUserRepository(db), password_hasher=PasswordHasher()
    )
    try:
        updated = await use_case.execute(
            SetPasswordInput(user_id=current_user.id, new_password=payload.new_password)
        )
    except PasswordAlreadySetError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Password already set — use change password instead"
        ) from exc

    await db.commit()
    return UserResponse.from_entity(updated)


@router.patch("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: PATCH /auth/me/password — troca de senha do usuário
    autenticado, exigindo a senha atual.
    """
    use_case = ChangePasswordUseCase(
        user_repository=SqlAlchemyUserRepository(db), password_hasher=PasswordHasher()
    )
    try:
        await use_case.execute(
            ChangePasswordInput(
                user_id=current_user.id,
                current_password=payload.current_password,
                new_password=payload.new_password,
            )
        )
    except PasswordNotSetError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Account has no local password (OAuth-only)"
        ) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect") from exc

    await db.commit()
    return {"detail": "Password updated"}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: DELETE /auth/me — exclui a própria conta e limpa o cookie
    de refresh (a sessão não faz mais sentido depois disso).
    """
    use_case = DeleteAccountUseCase(user_repository=SqlAlchemyUserRepository(db))
    await use_case.execute(current_user.id)
    await db.commit()
    clear_refresh_cookie(response)
