import logging
import uuid
from dataclasses import dataclass

from src.domain.admin_activity.entities import AdminActivityEvent
from src.domain.admin_activity.repository import AdminActivityRepository
from src.domain.user.exceptions import CannotDeleteSelfError, UserNotFoundError
from src.domain.user.repository import UserRepository

logger = logging.getLogger(__name__)


@dataclass
class DeleteUserInput:
    user_id: uuid.UUID
    requesting_admin_id: uuid.UUID


class DeleteUserUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Exclusão de qualquer conta pelo Admin (ex.: contas de
    teste/debug criadas em produção) — mesma operação de
    `DeleteAccountUseCase` (RN-03: `DELETE FROM users` cascade via FK
    `ON DELETE CASCADE`, já cobrindo transactions/conversations/
    embeddings/whatsapp_sessions/feedback), mas disparada pelo Admin
    sobre a conta de terceiros, não pelo próprio usuário sobre a sua.
    Fora de qualquer build-context — pedido direto do usuário pra
    limpar contas de teste esquecidas em produção.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        admin_activity_repository: AdminActivityRepository,
    ) -> None:
        self._user_repository = user_repository
        self._admin_activity_repository = admin_activity_repository

    async def execute(self, data: DeleteUserInput) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-15
        Descrição: 404 via `UserNotFoundError` se a conta não existir;
        bloqueia o admin de excluir a própria conta via
        `CannotDeleteSelfError` (evita perder acesso admin sem querer).
        """
        if data.user_id == data.requesting_admin_id:
            raise CannotDeleteSelfError(str(data.user_id))

        user = await self._user_repository.get_by_id(data.user_id)
        if user is None:
            raise UserNotFoundError(str(data.user_id))

        await self._user_repository.delete(data.user_id)
        await self._record_activity(user_id=user.id, user_name=user.name, email=str(user.email))

    async def _record_activity(self, user_id: uuid.UUID, user_name: str, email: str) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-15
        Descrição: Feed "Atividade recente" do Admin — best-effort,
        nunca impede a exclusão de completar (mesmo padrão de
        `SetAdminTestAccessUseCase._record_activity`). `user_id` fica
        `None` porque a conta já não existe mais no momento em que este
        evento é lido (FK de `admin_activity` pra `users` seria quebrada
        pelo cascade da própria exclusão).
        """
        try:
            await self._admin_activity_repository.create(
                AdminActivityEvent(
                    event_type="admin_deleted_user",
                    user_id=None,
                    message=f"Admin excluiu a conta de {user_name} ({email})",
                )
            )
        except Exception:
            logger.warning("Failed to record admin activity for user deletion", exc_info=True)
