"""create subscription tables

Revision ID: c8f3a1b9d2e4
Revises: a7a25d50ae25
Create Date: 2026-09-10 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c8f3a1b9d2e4'
down_revision: str | Sequence[str] | None = 'a7a25d50ae25'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

subscription_plan_enum = postgresql.ENUM("free", "pro", "premium", name="subscription_plan")
subscription_billing_cycle_enum = postgresql.ENUM(
    "monthly", "annual", name="subscription_billing_cycle"
)
subscription_status_enum = postgresql.ENUM(
    "trialing", "active", "past_due", "canceled", "incomplete", name="subscription_status"
)

# Valores de partida do build-context-09 §2.2 — editáveis pelo admin depois
# (plan_limits não é constante hardcoded, é catálogo em banco).
PLAN_LIMITS_SEED = [
    {
        "plan": "free",
        "ai_conversations_per_month": 10,
        "ai_reports_per_month": 3,
        "whatsapp_bot_messages_per_month": 60,
        "csv_exports_per_month": 2,
        "priority_support_enabled": False,
    },
    {
        "plan": "pro",
        "ai_conversations_per_month": 50,
        "ai_reports_per_month": 10,
        "whatsapp_bot_messages_per_month": None,
        "csv_exports_per_month": None,
        "priority_support_enabled": False,
    },
    {
        "plan": "premium",
        "ai_conversations_per_month": None,
        "ai_reports_per_month": None,
        "whatsapp_bot_messages_per_month": None,
        "csv_exports_per_month": None,
        "priority_support_enabled": True,
    },
]

plan_limits_table = sa.table(
    "plan_limits",
    sa.column("plan", subscription_plan_enum),
    sa.column("ai_conversations_per_month", sa.Integer),
    sa.column("ai_reports_per_month", sa.Integer),
    sa.column("whatsapp_bot_messages_per_month", sa.Integer),
    sa.column("csv_exports_per_month", sa.Integer),
    sa.column("priority_support_enabled", sa.Boolean),
)

billing_settings_table = sa.table(
    "billing_settings",
    sa.column("id", sa.Integer),
    sa.column("trial_days", sa.Integer),
)


def upgrade() -> None:
    """Upgrade schema.

    `subscriptions` (build-context-09 §2.2/§2.3) — 1:1 com `users`, toda
    conta ganha uma linha, mesmo no Free (backfill ao final). `plan_limits`
    é catálogo (PK `plan`, sem FK), seed inline. `plan_prices` (revisado
    em 2026-09-10, a pedido do usuário) é o catálogo dinâmico de preços —
    cada linha espelha um Price real do Stripe, gerenciável pelo Admin em
    runtime (sem `STRIPE_PRICE_*` fixo no `.env`/redeploy). `billing_settings`
    é singleton (`id` fixo, 1 linha). `payment_events`/`csv_export_events`
    são auditoria/contagem, sem lógica de negócio no schema.
    """
    bind = op.get_bind()
    subscription_plan_enum.create(bind, checkfirst=True)
    subscription_billing_cycle_enum.create(bind, checkfirst=True)
    subscription_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "subscriptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "plan",
            postgresql.ENUM("free", "pro", "premium", name="subscription_plan", create_type=False),
            nullable=False,
            server_default="free",
        ),
        sa.Column(
            "billing_cycle",
            postgresql.ENUM(
                "monthly", "annual", name="subscription_billing_cycle", create_type=False
            ),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "trialing",
                "active",
                "past_due",
                "canceled",
                "incomplete",
                name="subscription_status",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("legacy_pro_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_subscriptions_stripe_customer_id", "subscriptions", ["stripe_customer_id"]
    )
    op.create_index(
        "ix_subscriptions_stripe_subscription_id", "subscriptions", ["stripe_subscription_id"]
    )

    op.create_table(
        "plan_limits",
        sa.Column(
            "plan",
            postgresql.ENUM("free", "pro", "premium", name="subscription_plan", create_type=False),
            primary_key=True,
        ),
        sa.Column("ai_conversations_per_month", sa.Integer(), nullable=True),
        sa.Column("ai_reports_per_month", sa.Integer(), nullable=True),
        sa.Column("whatsapp_bot_messages_per_month", sa.Integer(), nullable=True),
        sa.Column("csv_exports_per_month", sa.Integer(), nullable=True),
        sa.Column(
            "priority_support_enabled", sa.Boolean(), nullable=False, server_default="false"
        ),
        # Um Produto Stripe por plano pago (`free` nunca tem) — criado sob
        # demanda pelo Admin na 1ª vez que um preço é cadastrado pra esse
        # plano (`CreateOrUpdatePlanPriceUseCase`), reaproveitado por todo
        # Price futuro do mesmo plano (ver `plan_prices` abaixo).
        sa.Column("stripe_product_id", sa.String(length=255), nullable=True),
    )
    op.bulk_insert(plan_limits_table, PLAN_LIMITS_SEED)

    op.create_table(
        "plan_prices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "plan",
            postgresql.ENUM("free", "pro", "premium", name="subscription_plan", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "billing_cycle",
            postgresql.ENUM(
                "monthly", "annual", name="subscription_billing_cycle", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("stripe_price_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("unit_amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="brl"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    # No máximo 1 preço ATIVO por combinação (plano, ciclo) — um Price do
    # Stripe é imutável em valor (não existe "editar preço" na API deles);
    # "editar" aqui sempre é criar um Price novo + arquivar o antigo
    # (`active=false`), nunca dois ativos ao mesmo tempo pra não oferecer
    # dois valores simultâneos no checkout. Mesmo padrão de índice parcial
    # único já usado por `ux_evolution_instances_single_active`.
    op.create_index(
        "ux_plan_prices_active_combo",
        "plan_prices",
        ["plan", "billing_cycle"],
        unique=True,
        postgresql_where=sa.text("active = true"),
    )

    op.create_table(
        "billing_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="7"),
        sa.CheckConstraint("id = 1", name="ck_billing_settings_singleton"),
    )
    op.bulk_insert(billing_settings_table, [{"id": 1, "trial_days": 7}])

    op.create_table(
        "payment_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("stripe_event_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount_cents", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "csv_export_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # Backfill (build-context-09 §2.3) — toda linha de `users` já existente
    # ganha uma `subscriptions` row no plano Free, nenhum usuário fica sem
    # assinatura.
    op.execute(
        sa.text(
            "INSERT INTO subscriptions (id, user_id, plan, status, created_at, updated_at) "
            "SELECT gen_random_uuid(), id, 'free', 'active', now(), now() FROM users"
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("csv_export_events")
    op.drop_table("payment_events")
    op.drop_table("billing_settings")
    op.drop_index("ux_plan_prices_active_combo", table_name="plan_prices")
    op.drop_table("plan_prices")
    op.drop_table("plan_limits")
    op.drop_index("ix_subscriptions_stripe_subscription_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_stripe_customer_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    subscription_status_enum.drop(op.get_bind(), checkfirst=True)
    subscription_billing_cycle_enum.drop(op.get_bind(), checkfirst=True)
    subscription_plan_enum.drop(op.get_bind(), checkfirst=True)
