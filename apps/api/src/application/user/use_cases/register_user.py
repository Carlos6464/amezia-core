import logging
from dataclasses import dataclass

from src.application.user.dtos import AuthResult
from src.domain.admin_activity.entities import AdminActivityEvent
from src.domain.admin_activity.repository import AdminActivityRepository
from src.domain.subscription.entities import Subscription
from src.domain.subscription.repository import SubscriptionRepository
from src.domain.user.entities import User
from src.domain.user.exceptions import EmailAlreadyExistsError
from src.domain.user.repository import UserRepository
from src.domain.user.value_objects import Email
from src.infrastructure.security.jwt_service import JwtService
from src.infrastructure.security.password_hasher import PasswordHasher

logger = logging.getLogger(__name__)


@dataclass
class RegisterUserInput:
    name: str
    email: str
    password: str


class RegisterUserUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Cria uma conta local (nome, email, senha) e já autentica o
    usuário, emitindo access e refresh token. Rejeita o cadastro se o email
    já existe, independente do método de autenticação da conta existente —
    o usuário deve usar login ou reset de senha nesse caso.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        jwt_service: JwtService,
        subscription_repository: SubscriptionRepository,
        admin_activity_repository: AdminActivityRepository,
    ) -> None:
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._jwt_service = jwt_service
        self._subscription_repository = subscription_repository
        self._admin_activity_repository = admin_activity_repository

    async def execute(self, data: RegisterUserInput) -> AuthResult:
        """
        Autor: Carlos Adriano
        Data: 2026-08-08
        Descrição: Valida duplicidade de email, cria a conta com senha
        hasheada e já devolve os tokens de sessão (registro = login
        automático). Toda conta nasce com uma `Subscription(plan=free)`
        (build-context-09 §2.5 passo 1) — nunca pulamos a criação dessa
        linha, mesmo quando o cadastro segue direto pra um checkout de
        plano pago.
        """
        if await self._user_repository.exists_by_email(data.email):
            raise EmailAlreadyExistsError(data.email)

        user = User(
            name=data.name,
            email=Email(data.email),
            password_hash=self._password_hasher.hash(data.password),
        )
        created = await self._user_repository.create(user)
        await self._subscription_repository.create(Subscription(user_id=created.id))
        await self._record_registration_activity(created)

        access_token = self._jwt_service.create_access_token(
            str(created.id), created.role, created.language.value
        )
        refresh_token = self._jwt_service.create_refresh_token(str(created.id))
        return AuthResult(user=created, access_token=access_token, refresh_token=refresh_token)

    async def _record_registration_activity(self, user: User) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Grava o evento no feed "Atividade recente" do Admin
        (build-context-11 §2.3) — best-effort: uma falha aqui nunca
        deve impedir o cadastro de completar, só loga um warning.
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
