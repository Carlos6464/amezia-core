import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base

feedback_channel_enum = ENUM("web", "whatsapp", name="feedback_channel", create_type=False)
feedback_type_enum = ENUM(
    "praise", "suggestion", "bug", "other", name="feedback_type", create_type=False
)


class Feedback(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Model SQLAlchemy da tabela `feedback` (build-context-08
    §2.3) — mensagem livre, canal, tipo, NPS opcional e assunto opcional.
    `message`/`subject` em texto plano (RN-05 não lista esses campos
    entre os criptografados por AES). `ON DELETE CASCADE` em `user_id`
    implementa o cascade de exclusão de conta (RN-03).
    """

    __tablename__ = "feedback"
    __table_args__ = (
        Index("ix_feedback_user_id", "user_id"),
        Index("ix_feedback_created_at", "created_at"),
        CheckConstraint(
            "nps_score IS NULL OR nps_score BETWEEN 0 AND 10", name="ck_feedback_nps_score_range"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(feedback_channel_enum, nullable=False)
    type: Mapped[str] = mapped_column(feedback_type_enum, nullable=False, server_default="other")
    nps_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    subject: Mapped[str | None] = mapped_column(String(150), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
