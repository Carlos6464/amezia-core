"""
Autor: Carlos Adriano
Data: 2026-09-10
Descrição: Script de dados único — importa os 2 preços mensais
(Pro/Premium) já criados manualmente no dashboard do Stripe (antes do
catálogo dinâmico `plan_prices` existir) para dentro do banco do Amezia,
em vez de descartá-los e recriar do zero via `CreateOrUpdatePlanPriceUseCase`.
Busca cada Price real na API do Stripe (`stripe.Price.retrieve_async`)
pra confirmar valor/moeda/produto reais, em vez de assumir o que está no
`.env` — populando `plan_limits.stripe_product_id` (reaproveita o
Produto que o Stripe já associou ao Price) e uma linha `active=True` em
`plan_prices`. Idempotente: não insere de novo se já existir uma linha
pra aquele `stripe_price_id`. Roda uma vez, manualmente:

    docker compose run --rm -v "$(pwd)/apps/api:/app" -v /app/.venv api \\
        sh -c "uv sync --locked && PYTHONPATH=/app .venv/bin/python scripts/backfill_existing_stripe_prices.py"
"""

import asyncio
import logging

import stripe
from sqlalchemy import select

from src.domain.subscription.entities import BillingCycle, Plan
from src.infrastructure.config import get_settings
from src.infrastructure.database.models.subscription import PlanLimits as PlanLimitsModel
from src.infrastructure.database.models.subscription import PlanPrice as PlanPriceModel
from src.infrastructure.database.session import async_session_factory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# (plano, ciclo, price_id do .env) — os 2 únicos preços que existem hoje,
# criados manualmente antes deste catálogo dinâmico existir.
_EXISTING_PRICES = [
    (Plan.PRO, BillingCycle.MONTHLY, "STRIPE_PRICE_PRO_MONTHLY"),
    (Plan.PREMIUM, BillingCycle.MONTHLY, "STRIPE_PRICE_PREMIUM_MONTHLY"),
]


async def main() -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Para cada preço conhecido, busca o objeto real no Stripe
    (fonte de verdade de valor/moeda/produto), grava/reaproveita o
    Produto em `plan_limits` e insere a linha em `plan_prices` se ainda
    não existir.
    """
    settings = get_settings()
    async with async_session_factory() as session:
        for plan, billing_cycle, env_var_name in _EXISTING_PRICES:
            price_id = getattr(settings, env_var_name)
            if not price_id:
                logger.info("Skipping %s (%s) — no price id in .env", plan.value, env_var_name)
                continue

            existing = await session.execute(
                select(PlanPriceModel).where(PlanPriceModel.stripe_price_id == price_id)
            )
            if existing.scalar_one_or_none() is not None:
                logger.info("Skipping %s — already imported", price_id)
                continue

            stripe_price = await stripe.Price.retrieve_async(price_id, api_key=settings.STRIPE_SECRET_KEY)
            product_id = stripe_price["product"]

            plan_limits = await session.execute(
                select(PlanLimitsModel).where(PlanLimitsModel.plan == plan.value)
            )
            plan_limits_model = plan_limits.scalar_one()
            if plan_limits_model.stripe_product_id is None:
                plan_limits_model.stripe_product_id = product_id

            session.add(
                PlanPriceModel(
                    plan=plan.value,
                    billing_cycle=billing_cycle.value,
                    stripe_price_id=price_id,
                    unit_amount_cents=stripe_price["unit_amount"],
                    currency=stripe_price["currency"],
                    active=True,
                )
            )
            logger.info(
                "Imported %s %s: price=%s product=%s amount=%s %s",
                plan.value,
                billing_cycle.value,
                price_id,
                product_id,
                stripe_price["unit_amount"],
                stripe_price["currency"],
            )

        await session.commit()

    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
