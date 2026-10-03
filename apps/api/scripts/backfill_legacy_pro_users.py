"""
Autor: Carlos Adriano
Data: 2026-09-10
Descrição: Script de dados único (build-context-09 §2.7/T14) — roda uma
vez, manualmente, na data de lançamento do módulo de Planos. Todo usuário
que já existia antes desse momento (ou seja: toda `subscriptions` row
que ainda nunca passou por um checkout real, `stripe_subscription_id IS
NULL`) ganha um cohort "Pro legado": `plan=pro` irrestrito sem passar
pelo Stripe, `legacy_pro_until = agora + 30 dias` (valor confirmado com o
usuário em 2026-09-10). `GetMySubscriptionUseCase`/`PlanLimitService`
resolvem `legacy_pro_until` vencido como Free automaticamente
(`Subscription.resolve_effective_plan`), sem exigir job assíncrono
dedicado. Idempotente na condição (`stripe_subscription_id IS NULL`),
mas **não** seguro rodar duas vezes em datas diferentes — cada execução
reseta `legacy_pro_until` pra "agora + 30 dias" de novo. Rodar uma única
vez:

    docker compose run --rm -v "$(pwd)/apps/api:/app" -v /app/.venv api \\
        sh -c "uv sync --locked && PYTHONPATH=/app .venv/bin/python scripts/backfill_legacy_pro_users.py"
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from src.infrastructure.database.models.subscription import Subscription as SubscriptionModel
from src.infrastructure.database.session import async_session_factory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LEGACY_PRO_TRIAL_DAYS = 30


async def main() -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: `UPDATE` em lote — sem N+1, todo o cohort legado em uma
    única query.
    """
    legacy_pro_until = datetime.now(UTC) + timedelta(days=LEGACY_PRO_TRIAL_DAYS)

    async with async_session_factory() as session:
        result = await session.execute(
            update(SubscriptionModel)
            .where(SubscriptionModel.stripe_subscription_id.is_(None))
            .values(plan="pro", legacy_pro_until=legacy_pro_until)
        )
        await session.commit()

    logger.info(
        "Legacy Pro cohort: %d subscriptions updated, legacy_pro_until=%s",
        result.rowcount,
        legacy_pro_until.isoformat(),
    )


if __name__ == "__main__":
    asyncio.run(main())
