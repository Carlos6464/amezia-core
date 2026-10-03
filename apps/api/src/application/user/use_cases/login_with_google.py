import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.user.dtos import AuthResult
from src.domain.admin_activity.entities import AdminActivityEvent
from src.domain.admin_activity.repository import AdminActivityRepository
from src.domain.subscription.entities import Subscription
from src.domain.subscription.repository import SubscriptionRepository
from src.domain.user.entities import User
from src.domain.user.exceptions import InvalidCredentialsError
from src.domain.user.repository import UserRepository
from src.domain.user.value_objects import Email
from src.infrastructure.oauth.google_client import GoogleOAuthClient
from src.infrastructure.security.jwt_service import JwtService

logger = logging.getLogger(__name__)


@dataclass
class LoginWithGoogleInput:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Exatamente um dos dois campos deve vir preenchido —
    `id_token` (fluxo Google Identity Services, já descontinuado no
    frontend) ou `code` (fluxo de redirect OAuth2, `GET
    /auth/google/callback`). Mantidos os dois pra não quebrar o endpoint
    `POST /login/google` existente.
    """

    id_token: str | None = None
    code: str | None = None


class LoginWithGoogleUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Login/cadastro via Google OAuth2. Se já existe conta local
    com o mesmo email (sem OAuth), faz account linking (seta
    oauth_provider/oauth_id na conta existente) em vez de criar uma conta
    duplicada; se não existe nenhuma conta, cria uma nova sem senha.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        google_client: GoogleOAuthClient,
        jwt_service: JwtService,
        subscription_repository: SubscriptionRepository,
        admin_activity_repository: AdminActivityRepository,
    ) -> None:
        self._user_repository = user_repository
        self._google_client = google_client
        self._jwt_service = jwt_service
        self._subscription_repository = subscription_repository
        self._admin_activity_repository = admin_activity_repository

    async def execute(self, data: LoginWithGoogleInput) -> AuthResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-09
        Descrição: Resolve a identidade do usuário no Google — via
        `id_token` (verificação local, síncrona) ou `code` (troca
        server-side por access_token, fluxo de redirect) — depois resolve
        a conta em três passos (por oauth_id → por email/linking → criação
        nova) e emite os tokens de sessão.
        """
        if data.id_token is not None:
            payload = self._google_client.verify_id_token(data.id_token)
        elif data.code is not None:
            payload = await self._google_client.exchange_code(data.code)
        else:
            raise InvalidCredentialsError()

        if payload is None:
            raise InvalidCredentialsError()

        google_sub: str = payload["sub"]
        email: str = payload["email"]
        name: str = payload.get("name") or email

        is_new = False
        user = await self._user_repository.get_by_oauth_id("google", google_sub)
        if user is None:
            user = await self._user_repository.get_by_email(email)
            if user is not None:
                user.oauth_provider = "google"
                user.oauth_id = google_sub
            else:
                user = User(
                    name=name, email=Email(email), oauth_provider="google", oauth_id=google_sub
                )
                is_new = True

        user.last_login_at = datetime.now(UTC)
        persisted = (
            await self._user_repository.create(user)
            if is_new
            else await self._user_repository.update(user)
        )
        if is_new:
            # Conta criada agora mesmo via Google — mesma invariante do
            # cadastro local (build-context-09 §2.5 passo 1): toda conta
            # nasce com uma Subscription(plan=free).
            await self._subscription_repository.create(Subscription(user_id=persisted.id))
            await self._record_registration_activity(persisted)

        access_token = self._jwt_service.create_access_token(
            str(persisted.id), persisted.role, persisted.language.value
        )
        refresh_token = self._jwt_service.create_refresh_token(str(persisted.id))
        return AuthResult(user=persisted, access_token=access_token, refresh_token=refresh_token)

    async def _record_registration_activity(self, user: User) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Mesmo evento `user_registered` de `RegisterUserUseCase`
        (build-context-11 §2.3), pro cadastro novo via Google — best
        effort, nunca impede o login de completar.
        """
        try:
            await self._admin_activity_repository.create(
                AdminActivityEvent(
                    event_type="user_registered",
                    user_id=user.id,
                    message=f"{user.name} se cadastrou",
                )
            )
        except Exception:
            logger.warning("Failed to record admin activity for registration", exc_info=True)
