import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from src.domain.ai_usage.repository import (
    AiUsageRepository,
    FeatureUsageTotal,
    ProviderUsageTotal,
)
from src.domain.subscription.entities import Plan
from src.domain.subscription.repository import SubscriptionRepository
from src.domain.user.repository import UserRepository


@dataclass
class AdminTopConsumerRow:
    user_id: uuid.UUID
    name: str
    email: str
    plan: Plan
    ai_conversations: int
    ai_reports: int
    estimated_cost_micros: int


@dataclass
class GetAdminAiUsageOverviewOutput:
    since: datetime
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost_micros: int
    by_feature: list[FeatureUsageTotal]
    by_provider: list[ProviderUsageTotal]
    top_consumers: list[AdminTopConsumerRow]


class GetAdminAiUsageOverviewUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: `GET /admin/ai-usage/overview` (build-context-10 §2.6/T8)
    — agregado do mês corrente (tokens/custo estimado total, por
    provider, por feature) + tabela "por usuário" (top consumidores,
    plano, conversas/relatórios usados). `AiUsageRepository.aggregate_for_admin`
    não sabe nome/e-mail/plano (não é dado de `ai_usage_events`) — este
    use case resolve isso à parte, um `get_by_id`/`get_by_user_id` por
    consumidor do topo (no máximo 10, `_TOP_CONSUMERS_LIMIT`), em vez de
    um join cross-bounded-context dentro do repositório.
    """

    def __init__(
        self,
        ai_usage_repository: AiUsageRepository,
        user_repository: UserRepository,
        subscription_repository: SubscriptionRepository,
    ) -> None:
        self._ai_usage_repository = ai_usage_repository
        self._user_repository = user_repository
        self._subscription_repository = subscription_repository

    async def execute(self) -> GetAdminAiUsageOverviewOutput:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: "Mês corrente" = mês calendário atual (dia 1, 00:00
        UTC) — recorte simples e previsível pro painel do admin,
        diferente do ciclo por assinatura usado pro limite individual
        (`resolve_cycle_start`), que não faria sentido pra um agregado
        de todos os usuários ao mesmo tempo.
        """
        since = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        aggregate = await self._ai_usage_repository.aggregate_for_admin(since)

        top_consumers: list[AdminTopConsumerRow] = []
        for consumer in aggregate.top_consumers:
            user = await self._user_repository.get_by_id(consumer.user_id)
            if user is None:
                continue
            subscription = await self._subscription_repository.get_by_user_id(consumer.user_id)
            plan = subscription.resolve_effective_plan() if subscription else Plan.FREE
            top_consumers.append(
                AdminTopConsumerRow(
                    user_id=consumer.user_id,
                    name=user.name,
                    email=str(user.email),
                    plan=plan,
                    ai_conversations=consumer.ai_conversations,
                    ai_reports=consumer.ai_reports,
                    estimated_cost_micros=consumer.estimated_cost_micros,
                )
            )

        return GetAdminAiUsageOverviewOutput(
            since=since,
            total_input_tokens=aggregate.total_input_tokens,
            total_output_tokens=aggregate.total_output_tokens,
            total_estimated_cost_micros=aggregate.total_estimated_cost_micros,
            by_feature=aggregate.by_feature,
            by_provider=aggregate.by_provider,
            top_consumers=top_consumers,
        )
