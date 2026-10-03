import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base
from src.infrastructure.security.encrypted_string import EncryptedString

user_role_enum = ENUM("user", "admin", name="user_role", create_type=False)
user_language_enum = ENUM("pt-BR", "en", name="user_language", create_type=False)


class User(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Model SQLAlchemy da tabela `users` — primeira tabela de
    domínio do projeto (build-context-01). `phone` é armazenado já
    criptografado (AES/Fernet, RN-05); a cifra/decifra acontece na camada
    de infraestrutura (repository), nunca aqui.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "password_hash IS NOT NULL OR oauth_provider IS NOT NULL",
            name="ck_users_has_auth_method",
        ),
        Index(
            "ux_users_oauth_provider_id",
            "oauth_provider",
            "oauth_id",
            unique=True,
            postgresql_where="oauth_provider IS NOT NULL",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    role: Mapped[str] = mapped_column(user_role_enum, nullable=False, server_default="user")
    language: Mapped[str] = mapped_column(user_language_enum, nullable=False, server_default="pt-BR")
    oauth_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    oauth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    monthly_budget_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    dashboard_layout: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
