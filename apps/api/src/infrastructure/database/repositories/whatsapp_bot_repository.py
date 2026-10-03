import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.whatsapp_bot.entities import WhatsappSession as WhatsappSessionEntity
from src.domain.whatsapp_bot.value_objects import BotMode
from src.infrastructure.database.models.whatsapp_bot_model import (
    ProcessedBotMessage as ProcessedBotMessageModel,
)
from src.infrastructure.database.models.whatsapp_bot_model import (
    WhatsappSession as WhatsappSessionModel,
)


class SqlAlchemyWhatsappSessionRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Implementação concreta de WhatsappSessionRepository via
    SQLAlchemy async — traduz entre a entidade de domínio WhatsappSession
    e o model ORM (build-context-07 §2.4).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_phone_hash(self, phone_hash: str) -> WhatsappSessionEntity | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Busca a sessão pelo hash do telefone — caminho rápido
        do orquestrador (build-context-07 §2.6, passo 3), sem precisar
        tocar em `users` quando a sessão já existe.
        """
        result = await self._session.execute(
            select(WhatsappSessionModel).where(WhatsappSessionModel.phone_hash == phone_hash)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def create(self, session: WhatsappSessionEntity) -> WhatsappSessionEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Persiste uma nova sessão — chamada só no fallback em
        que o número ainda não tinha sessão (1º contato do usuário com o
        bot).
        """
        model = WhatsappSessionModel(
            user_id=session.user_id,
            phone_hash=session.phone_hash,
            current_state=session.current_state.value if session.current_state else None,
            pending_action=session.pending_action,
            last_interaction_at=session.last_interaction_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def update(self, session: WhatsappSessionEntity) -> WhatsappSessionEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Atualiza `current_state`/`pending_action`/
        `last_interaction_at` ao final do processamento de cada mensagem
        (build-context-07 §2.6, passo 9; `pending_action` desde o
        build-context-12).
        """
        model = await self._session.get(WhatsappSessionModel, session.id)
        if model is None:
            raise ValueError(f"WhatsappSession {session.id} not found")
        model.current_state = session.current_state.value if session.current_state else None
        model.pending_action = session.pending_action
        model.last_interaction_at = session.last_interaction_at
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    def _to_entity(self, model: WhatsappSessionModel) -> WhatsappSessionEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Converte o model SQLAlchemy na entidade de domínio
        WhatsappSession — fronteira entre as duas camadas.
        """
        return WhatsappSessionEntity(
            id=model.id,
            user_id=model.user_id,
            phone_hash=model.phone_hash,
            current_state=BotMode(model.current_state) if model.current_state else None,
            pending_action=model.pending_action,
            last_interaction_at=model.last_interaction_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class SqlAlchemyProcessedBotMessageRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Implementação concreta de ProcessedBotMessageRepository —
    sustenta a idempotência de mensagens (RN-04, build-context-07 §2.4).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def try_mark_processed(self, instance_id: int, whatsapp_message_id: str) -> bool:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: `INSERT ... ON CONFLICT (whatsapp_instance_id,
        whatsapp_message_id) DO NOTHING RETURNING id` — atômico por
        construção do Postgres, sem race condition entre checar e
        inserir. Sem `RETURNING`, a mensagem já existia (duplicata).
        """
        statement = (
            insert(ProcessedBotMessageModel)
            .values(whatsapp_instance_id=instance_id, whatsapp_message_id=whatsapp_message_id)
            .on_conflict_do_nothing(
                index_elements=["whatsapp_instance_id", "whatsapp_message_id"]
            )
            .returning(ProcessedBotMessageModel.id)
        )
        result = await self._session.execute(statement)
        return result.first() is not None

    async def set_user_id(
        self, instance_id: int, whatsapp_message_id: str, user_id: uuid.UUID
    ) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Preenche `user_id` na linha inserida por
        `try_mark_processed` — chamado logo após o usuário ser resolvido
        a partir do telefone (build-context-09 §2.6).
        """
        await self._session.execute(
            update(ProcessedBotMessageModel)
            .where(
                ProcessedBotMessageModel.whatsapp_instance_id == instance_id,
                ProcessedBotMessageModel.whatsapp_message_id == whatsapp_message_id,
            )
            .values(user_id=user_id)
        )

    async def count_for_user_since(self, user_id: uuid.UUID, since: datetime) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Conta mensagens processadas do usuário desde `since`
        — usado pelo enforcement do limite mensal do Bot no Free
        (build-context-09 §2.6).
        """
        result = await self._session.execute(
            select(func.count())
            .select_from(ProcessedBotMessageModel)
            .where(
                ProcessedBotMessageModel.user_id == user_id,
                ProcessedBotMessageModel.processed_at >= since,
            )
        )
        return result.scalar_one()

    async def list_distinct_active_user_ids_since(self, since: datetime) -> set[uuid.UUID]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: Usuários distintos com pelo menos 1 mensagem
        processada pelo bot desde `since` — uma das 3 fontes de DAU/MAU
        do Admin (build-context-11 §2.2). `user_id IS NOT NULL` exclui
        mensagens de número não vinculado (RN-06).
        """
        result = await self._session.execute(
            select(ProcessedBotMessageModel.user_id.distinct()).where(
                ProcessedBotMessageModel.user_id.is_not(None),
                ProcessedBotMessageModel.processed_at >= since,
            )
        )
        return set(result.scalars().all())
