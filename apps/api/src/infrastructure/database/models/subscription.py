import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base

subscription_plan_enum = ENUM("free", "pro", "premium", name="subscription_plan", create_type=False)
subscription_billing_cycle_enum = ENUM(
    "monthly", "annual", name="subscription_billing_cycle", create_type=False
)
subscription_status_enum = ENUM(
    "trialing",
    "active",
    "past_due",
    "canceled",
    "incomplete",
    name="subscription_status",
    create_type=False,
)


class Subscription(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Model SQLAlchemy da tabela `subscriptions`
    (build-context-09 §2.2/§2.3) — 1:1 com `users`. `status` espelha o
    Stripe, nunca calculado aqui.
    """

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    plan: Mapped[str] = mapped_column(subscription_plan_enum, nullable=False, server_default="free")
    billing_cycle: Mapped[str | None] = mapped_column(subscription_billing_cycle_enum, nullable=True)
    status: Mapped[str] = mapped_column(
        subscription_status_enum, nullable=False, server_default="active"
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    legacy_pro_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    admin_test_access_granted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PlanLimits(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Model SQLAlchemy da tabela `plan_limits`
    (build-context-09 §2.2) — catálogo (PK `plan`, sem FK), editável
    pelo admin.
    """

    __tablename__ = "plan_limits"

    plan: Mapped[str] = mapped_column(subscription_plan_enum, primary_key=True)
    ai_conversations_per_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_reports_per_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    whatsapp_bot_messages_per_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    csv_exports_per_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority_support_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    stripe_product_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PlanPrice(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Model SQLAlchemy da tabela `plan_prices` (revisado em
    2026-09-10) — catálogo dinâmico de preços, cada linha espelha um
    Price real do Stripe. No máximo uma linha `active=True` por
    `(plan, billing_cycle)` (índice parcial único na migration,
    `ux_plan_prices_active_combo`).
    """

    __tablename__ = "plan_prices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan: Mapped[str] = mapped_column(subscription_plan_enum, nullable=False)
    billing_cycle: Mapped[str] = mapped_column(subscription_billing_cycle_enum, nullable=False)
    stripe_price_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    unit_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="brl")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BillingSettings(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Model SQLAlchemy da tabela `billing_settings`
    (build-context-09 §2.2) — singleton, `id` sempre 1.
    """

    __tablename__ = "billing_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="7")


class PaymentEvent(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Model SQLAlchemy da tabela `payment_events`
    (build-context-09 §2.3) — auditoria de webhook processado,
    `stripe_event_id` único sustenta a idempotência.
    """

    __tablename__ = "payment_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stripe_event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    amount_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CsvExportEvent(Base):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Model SQLAlchemy da tabela `csv_export_events`
    (build-context-09 §2.3/§2.6) — só o fato de que uma exportação
    aconteceu, sem guardar o arquivo/conteúdo.
    """

    __tablename__ = "csv_export_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
