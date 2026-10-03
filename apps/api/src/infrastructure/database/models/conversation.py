import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base
from src.infrastructure.security.encrypted_string import EncryptedString

conversation_channel_enum = ENUM("web", "whatsapp", name="conversation_channel", create_type=False)
message_role_enum = ENUM("user", "assistant", name="message_role", create_type=False)
ai_provider_enum = ENUM("gemini", "grok", name="ai_provider", create_type=False)


class Conversation(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Model SQLAlchemy da tabela `conversations` — `title`/
    `summary` persistidos já criptografados (AES/Fernet, RN-05),
    transparente via `EncryptedString`. `summarized_until_message_id`
    referencia `conversation_messages.id` (FK criada na mesma migration,
    depois da tabela existir — referência circular entre as duas tabelas).
    """

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ux_conversations_public_id", "public_id", unique=True),
        Index("ix_conversations_user_last_message", "user_id", "last_message_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(26), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    summary: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    summarized_until_message_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(conversation_channel_enum, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ConversationMessage(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Model SQLAlchemy da tabela `conversation_messages` —
    `content` não é criptografado (não está na lista RN-05 de campos
    sensíveis, diferente de `title`/`summary`). `provider_used` só
    preenchido em mensagens `role=assistant`.
    """

    __tablename__ = "conversation_messages"
    __table_args__ = (
        Index("ux_conversation_messages_public_id", "public_id", unique=True),
        Index("ix_conversation_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(26), nullable=False)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(message_role_enum, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    provider_used: Mapped[str | None] = mapped_column(ai_provider_enum, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
