from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.reports.exceptions import ReportsThrottleExceededError
from src.domain.subscription.exceptions import CsvExportLimitExceededError
from src.domain.subscription.services import PlanLimitService
from src.domain.user.entities import User
from src.infrastructure.cache.redis_client import get_redis_client
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemyCsvExportEventRepository,
    SqlAlchemyPlanLimitsRepository,
    SqlAlchemySubscriptionRepository,
)
from src.infrastructure.database.session import get_db
from src.presentation.api.v1.dependencies.auth import (
    get_current_user,
    get_current_user_or_report_viewer,
)

NARRATIVE_THROTTLE_LIMIT = 10
NARRATIVE_THROTTLE_WINDOW_SECONDS = 60


def _check_throttle(count: int, ttl_seconds: int) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Regra pura de limite — separada da leitura/escrita no
    Redis (`enforce_ai_narrative_throttle`) para deixar explícito o que
    conta como "excedido", levantando a exceção de domínio
    `ReportsThrottleExceededError` (build-context-05 §2.7).
    """
    if count > NARRATIVE_THROTTLE_LIMIT:
        retry_after = ttl_seconds if ttl_seconds > 0 else NARRATIVE_THROTTLE_WINDOW_SECONDS
        raise ReportsThrottleExceededError(retry_after)


async def enforce_ai_narrative_throttle(
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis_client),
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Dependency FastAPI de `POST /reports/narrative` — limite
    de 10 requisições/minuto por usuário (build-context-05 §2.7),
    contador Redis por usuário (`reports:narrative:throttle:{user_id}`,
    `INCR` + `EXPIRE 60` só na primeira requisição da janela). Checagem
    acontece antes de enfileirar o job, na requisição HTTP síncrona —
    feedback imediato ao usuário via `429` + header `Retry-After`.
    """
    key = f"reports:narrative:throttle:{current_user.id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, NARRATIVE_THROTTLE_WINDOW_SECONDS)

    ttl = await redis.ttl(key)
    try:
        _check_throttle(count, ttl)
    except ReportsThrottleExceededError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many narrative requests",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc


async def enforce_csv_export_limit(
    current_user: User = Depends(get_current_user_or_report_viewer),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Dependency FastAPI de `GET /reports/export/csv`
    (build-context-09 §2.6) — limite mensal de exportações CSV do
    plano efetivo do usuário, contra `csv_export_events` (mês
    calendário atual). `None` (Pro/Premium) é ilimitado, nunca conta.
    A contagem da exportação em si (`csv_export_events.create`)
    acontece no router, só depois do CSV ser gerado com sucesso — esta
    dependency só bloqueia, nunca grava.
    """
    subscription = await SqlAlchemySubscriptionRepository(db).get_by_user_id(current_user.id)
    if subscription is None:
        return

    plan_limits = await SqlAlchemyPlanLimitsRepository(db).get_by_plan(
        subscription.resolve_effective_plan()
    )
    if plan_limits is None:
        return

    limit = PlanLimitService().csv_export_limit(plan_limits)
    if limit is None:
        return

    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    count = await SqlAlchemyCsvExportEventRepository(db).count_since(current_user.id, month_start)
    try:
        if count >= limit:
            raise CsvExportLimitExceededError(str(current_user.id))
    except CsvExportLimitExceededError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Monthly CSV export limit reached for your plan — upgrade to export more",
        ) from exc
