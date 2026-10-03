import uuid
from datetime import UTC, datetime
from datetime import date as date_type

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ai_usage.entities import AiFeature, AiProvider
from src.domain.ai_usage.entities import AiUsageEvent as AiUsageEventEntity
from src.domain.ai_usage.repository import (
    AdminAiUsageAggregate,
    FeatureUsageTotal,
    MonthlyUsagePoint,
    ProviderUsageTotal,
    TopConsumer,
)
from src.infrastructure.database.models.ai_usage import AiUsageEvent as AiUsageEventModel

_TOP_CONSUMERS_LIMIT = 10


def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Mesmo helper de `SqlAlchemyUserRepository._shift_month`
    (build-context-06) — desloca (ano, mês) em `offset` meses,
    normalizando o ano quando o mês sai do intervalo 1-12.
    """
    total = (year * 12 + month - 1) + offset
    new_year, new_month = divmod(total, 12)
    return new_year, new_month + 1


class SqlAlchemyAiUsageRepository:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Implementação concreta de `AiUsageRepository`
    (build-context-10 §2.1) via SQLAlchemy async.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, event: AiUsageEventEntity) -> AiUsageEventEntity:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Persiste um evento de uso de IA já concluído —
        chamado por `RecordAiUsageUseCase` ao fim de qualquer chamada
        de IA do produto.
        """
        model = AiUsageEventModel(
            id=event.id,
            user_id=event.user_id,
            feature=event.feature.value,
            provider=event.provider.value,
            model=event.model,
            input_tokens=event.input_tokens,
            output_tokens=event.output_tokens,
            estimated_cost_micros=event.estimated_cost_micros,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return AiUsageEventEntity(
            id=model.id,
            user_id=model.user_id,
            feature=AiFeature(model.feature),
            provider=AiProvider(model.provider),
            model=model.model,
            input_tokens=model.input_tokens,
            output_tokens=model.output_tokens,
            estimated_cost_micros=model.estimated_cost_micros,
            created_at=model.created_at,
        )

    async def count_this_cycle(
        self, user_id: uuid.UUID, feature: AiFeature, cycle_start: datetime
    ) -> int:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Conta eventos de `feature` do usuário desde
        `cycle_start` — usado por `CheckAiUsageLimitUseCase` (bloqueio)
        e `GetMyAiUsageUseCase` (barra de uso do ciclo atual).
        """
        result = await self._session.execute(
            select(func.count())
            .select_from(AiUsageEventModel)
            .where(
                AiUsageEventModel.user_id == user_id,
                AiUsageEventModel.feature == feature.value,
                AiUsageEventModel.created_at >= cycle_start,
            )
        )
        return result.scalar_one()

    async def get_monthly_history(
        self, user_id: uuid.UUID, months: int
    ) -> list[MonthlyUsagePoint]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Série mensal (mês calendário, `months` meses até o
        atual inclusive, ordem crescente) de conversas/relatórios de IA
        do usuário — alimenta `usage-history-table`. Mesmo padrão de
        `SqlAlchemyUserRepository.count_new_users_by_month`, agregando
        as 2 features numa query por mês via `CASE WHEN`.
        """
        today = datetime.now(UTC).date()
        points: list[MonthlyUsagePoint] = []
        for offset in range(months - 1, -1, -1):
            year, month = _shift_month(today.year, today.month, -offset)
            next_year, next_month = _shift_month(year, month, 1)
            range_start = datetime(year, month, 1, tzinfo=UTC)
            range_end = datetime(next_year, next_month, 1, tzinfo=UTC)

            result = await self._session.execute(
                select(
                    func.sum(
                        case((AiUsageEventModel.feature == AiFeature.AGENT_CHAT.value, 1), else_=0)
                    ),
                    func.sum(
                        case(
                            (AiUsageEventModel.feature == AiFeature.REPORT_NARRATIVE.value, 1),
                            else_=0,
                        )
                    ),
                ).where(
                    AiUsageEventModel.user_id == user_id,
                    AiUsageEventModel.created_at >= range_start,
                    AiUsageEventModel.created_at < range_end,
                )
            )
            ai_conversations, ai_reports = result.one()
            points.append(
                MonthlyUsagePoint(
                    month=date_type(year, month, 1),
                    ai_conversations=ai_conversations or 0,
                    ai_reports=ai_reports or 0,
                )
            )
        return points

    async def aggregate_for_admin(self, since: datetime) -> AdminAiUsageAggregate:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Agregado de todos os eventos desde `since` (início do
        mês corrente) — totais de tokens/custo, quebra por feature, por
        provider, e os `_TOP_CONSUMERS_LIMIT` usuários que mais geraram
        custo estimado no período (`GetAdminAiUsageOverviewUseCase`
        resolve nome/e-mail/plano à parte via `UserRepository`/
        `SubscriptionRepository`, este repositório não faz join fora de
        `ai_usage_events`).
        """
        totals_result = await self._session.execute(
            select(
                func.coalesce(func.sum(AiUsageEventModel.input_tokens), 0),
                func.coalesce(func.sum(AiUsageEventModel.output_tokens), 0),
                func.coalesce(func.sum(AiUsageEventModel.estimated_cost_micros), 0),
            ).where(AiUsageEventModel.created_at >= since)
        )
        total_input_tokens, total_output_tokens, total_estimated_cost_micros = totals_result.one()

        by_feature_result = await self._session.execute(
            select(
                AiUsageEventModel.feature,
                func.count(),
                func.coalesce(func.sum(AiUsageEventModel.input_tokens), 0),
                func.coalesce(func.sum(AiUsageEventModel.output_tokens), 0),
                func.coalesce(func.sum(AiUsageEventModel.estimated_cost_micros), 0),
            )
            .where(AiUsageEventModel.created_at >= since)
            .group_by(AiUsageEventModel.feature)
        )
        by_feature = [
            FeatureUsageTotal(
                feature=AiFeature(row.feature),
                event_count=row[1],
                input_tokens=row[2],
                output_tokens=row[3],
                estimated_cost_micros=row[4],
            )
            for row in by_feature_result.all()
        ]

        by_provider_result = await self._session.execute(
            select(
                AiUsageEventModel.provider,
                func.count(),
                func.coalesce(func.sum(AiUsageEventModel.estimated_cost_micros), 0),
            )
            .where(AiUsageEventModel.created_at >= since)
            .group_by(AiUsageEventModel.provider)
        )
        by_provider = [
            ProviderUsageTotal(provider=AiProvider(row.provider), event_count=row[1], estimated_cost_micros=row[2])
            for row in by_provider_result.all()
        ]

        top_consumers_result = await self._session.execute(
            select(
                AiUsageEventModel.user_id,
                func.sum(
                    case((AiUsageEventModel.feature == AiFeature.AGENT_CHAT.value, 1), else_=0)
                ),
                func.sum(
                    case((AiUsageEventModel.feature == AiFeature.REPORT_NARRATIVE.value, 1), else_=0)
                ),
                func.coalesce(func.sum(AiUsageEventModel.estimated_cost_micros), 0),
            )
            .where(AiUsageEventModel.created_at >= since)
            .group_by(AiUsageEventModel.user_id)
            .order_by(func.coalesce(func.sum(AiUsageEventModel.estimated_cost_micros), 0).desc())
            .limit(_TOP_CONSUMERS_LIMIT)
        )
        top_consumers = [
            TopConsumer(
                user_id=row[0], ai_conversations=row[1] or 0, ai_reports=row[2] or 0, estimated_cost_micros=row[3]
            )
            for row in top_consumers_result.all()
        ]

        return AdminAiUsageAggregate(
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_estimated_cost_micros=total_estimated_cost_micros,
            by_feature=by_feature,
            by_provider=by_provider,
            top_consumers=top_consumers,
        )
