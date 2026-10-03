from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base
from src.infrastructure.security.encrypted_string import EncryptedString

evolution_connection_status_enum = ENUM(
    "connecting", "connected", "disconnected", name="evolution_connection_status", create_type=False
)


class EvolutionInstance(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Model SQLAlchemy da tabela `evolution_instances` — gestão
    de instância(s) da Evolution API a nível de plataforma (sem
    `user_id`, build-context-06 §2.2). `phone_number`/`webhook_secret`
    persistidos já criptografados (AES/Fernet, RN-05), transparente via
    `EncryptedString`. O índice parcial único garante, também no banco,
    que só existe uma instância ativa por vez (MVP1) — segunda linha de
    defesa além da regra aplicada em UpdateEvolutionInstanceUseCase.
    """

    __tablename__ = "evolution_instances"
    __table_args__ = (
        Index("ux_evolution_instances_public_id", "public_id", unique=True),
        Index("ux_evolution_instances_name", "name", unique=True),
        Index(
            "ux_evolution_instances_single_active",
            "is_active",
            unique=True,
            postgresql_where="is_active",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(26), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    status: Mapped[str] = mapped_column(
        evolution_connection_status_enum, nullable=False, server_default="disconnected"
    )
    qr_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    qr_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    webhook_url: Mapped[str] = mapped_column(String(500), nullable=False)
    webhook_secret: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
