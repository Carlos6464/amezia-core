import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base

whatsapp_bot_mode_enum = ENUM(
    "expense", "chat", "report", "feedback", name="whatsapp_bot_mode", create_type=False
)


class WhatsappSession(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Model SQLAlchemy da tabela `whatsapp_sessions`
    (build-context-07 §2.4) — uma linha por usuário. `current_state`
    NULL representa o estado Menu. `ON DELETE CASCADE` em `user_id`
    implementa o cascade de exclusão de conta (RN-03). `pending_action`
    (build-context-12 §2) guarda o rascunho de uma pergunta em aberto do
    modo Registrar — `NULL` na maior parte do tempo.
    """

    __tablename__ = "whatsapp_sessions"
    __table_args__ = (
        Index("ux_whatsapp_sessions_user_id", "user_id", unique=True),
        Index("ux_whatsapp_sessions_phone_hash", "phone_hash", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_state: Mapped[str | None] = mapped_column(whatsapp_bot_mode_enum, nullable=True)
    pending_action: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    last_interaction_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProcessedBotMessage(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Model SQLAlchemy da tabela `processed_bot_messages`
    (build-context-07 §2.4) — deduplicação de mensagens do Bot WhatsApp
    (RN-04). O UNIQUE composto (`whatsapp_instance_id`,
    `whatsapp_message_id`) é a base do `INSERT ... ON CONFLICT DO
    NOTHING` atômico em `SqlAlchemyProcessedBotMessageRepository`.
    `user_id` (build-context-09 §2.6) foi adicionado depois, preenchido
    num 2º passo (`set_user_id`) já que o usuário só é resolvido a
    partir do telefone depois da idempotência já ter rodado — sustenta
    a contagem de `PlanLimits.whatsapp_bot_messages_per_month`.
    """

    __tablename__ = "processed_bot_messages"
    __table_args__ = (
        UniqueConstraint(
            "whatsapp_instance_id",
            "whatsapp_message_id",
            name="ux_processed_bot_messages_instance_message",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    whatsapp_instance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("evolution_instances.id", ondelete="CASCADE"), nullable=False
    )
    whatsapp_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
