import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base


class Category(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Model SQLAlchemy da tabela `categories` — globais
    (`user_id` NULL) e privadas (`user_id` preenchido, limite de 3 por
    usuário validado na application layer). `is_system` marca as 7
    categorias de seed (build-context-02 §2.3), nunca editáveis/excluíveis
    (RN-02). `ON DELETE CASCADE` em `user_id` implementa o cascade de
    exclusão de conta para categorias privadas (RN-03, ver Observações do
    build-context).
    """

    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("NOT is_system OR user_id IS NULL", name="ck_categories_system_no_owner"),
        Index("ix_categories_public_id", "public_id", unique=True),
        Index("ix_categories_user_id", "user_id"),
        Index(
            "ix_categories_user_name",
            "user_id",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(26), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    icon: Mapped[str] = mapped_column(String(30), nullable=False, server_default="tag")
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
