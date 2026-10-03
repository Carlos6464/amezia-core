import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base

ai_usage_feature_enum = ENUM(
    "agent_chat",
    "report_narrative",
    "bot_expense_parsing",
    "bot_audio_transcription",
    name="ai_usage_feature",
    create_type=False,
)
ai_usage_provider_enum = ENUM("gemini", "grok", name="ai_usage_provider", create_type=False)


class AiUsageEvent(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Model SQLAlchemy da tabela `ai_usage_events`
    (build-context-10 §2.2/§2.3) — log unificado de toda chamada de IA
    do produto, gravado por `RecordAiUsageUseCase`. `estimated_cost_micros`
    é calculado uma única vez no momento do registro (`pricing.py`),
    nunca recalculado depois — em micros de BRL (1 BRL = 1_000_000
    micros), não centavos, pra não perder precisão de chamadas
    individuais baratas (ver docstring de `AiUsageEvent` no domínio).
    """

    __tablename__ = "ai_usage_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    feature: Mapped[str] = mapped_column(ai_usage_feature_enum, nullable=False)
    provider: Mapped[str] = mapped_column(ai_usage_provider_enum, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
