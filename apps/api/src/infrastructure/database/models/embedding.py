import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base

embedding_source_type_enum = ENUM(
    "transaction",
    "conversation_message",
    "category",
    name="embedding_source_type",
    create_type=False,
)

# Fixo, não lido de Settings: mudar a dimensão exige nova migration + reprocessamento em
# lote (build-context-04 §2.2) — nunca deve divergir silenciosamente da coluna real do banco.
EMBEDDING_DIMENSION = 768


class Embedding(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Model SQLAlchemy da tabela `embeddings` — vetor RAG
    (`vector(768)`, extensão pgvector) de um trecho de texto do usuário,
    e também (desde o build-context-12) do nome de uma categoria, para
    checagem de duplicata semântica. `source_id` não é FK física
    (polimórfico: aponta para `transactions`, `conversation_messages` ou
    `categories` conforme `source_type`). `UNIQUE (source_type,
    source_id)` habilita upsert idempotente. `user_id` é nullable só
    para `source_type="category"` de uma categoria global (sem dono) —
    os outros dois `source_type` sempre preenchem.
    """

    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="ux_embeddings_source"),
        Index("ix_embeddings_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(embedding_source_type_enum, nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
