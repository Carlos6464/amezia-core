import uuid
from dataclasses import dataclass
from datetime import datetime

from src.application.ai_usage.cycle import resolve_cycle_start
from src.domain.ai_usage.entities import AiFeature
from src.domain.ai_usage.repository import AiUsageRepository, MonthlyUsagePoint
from src.domain.subscription.entities import Plan
from src.domain.subscription.exceptions import PlanLimitsNotFoundError, SubscriptionNotFoundError
from src.domain.subscription.repository import PlanLimitsRepository, SubscriptionRepository
from src.domain.subscription.services import PlanLimitService

HISTORY_MONTHS = 6


@dataclass
class GetMyAiUsageOutput:
    plan: Plan
    cycle_start: datetime
    ai_conversations_used: int
    ai_conversations_limit: int | None
    ai_reports_used: int
    ai_reports_limit: int | None
    history: list[MonthlyUsagePoint]


class GetMyAiUsageUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: `GET /ai-usage/me` (build-context-10 §2.6/T8) — uso do
    ciclo atual (conversas/relatórios usados vs. limite do plano
    efetivo) + histórico dos últimos `HISTORY_MONTHS` meses, pra
    `settings-usage-page`.
    """

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        plan_limits_repository: PlanLimitsRepository,
        ai_usage_repository: AiUsageRepository,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._plan_limits_repository = plan_limits_repository
        self._ai_usage_repository = ai_usage_repository
        self._plan_limit_service = PlanLimitService()

    async def execute(self, user_id: uuid.UUID) -> GetMyAiUsageOutput:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Resolve o plano efetivo (RN-01, sempre do usuário do
        JWT) e cruza a contagem real do ciclo (`AiUsageRepository`) com
        o limite do plano (`PlanLimitService`) pras 2 barras de uso —
        mesmo `resolve_cycle_start` que `CheckAiUsageLimitUseCase` usa,
        pra nunca divergir o que é "o ciclo atual" entre bloqueio e
        exibição.
        """
        subscription = await self._subscription_repository.get_by_user_id(user_id)
        if subscription is None:
            raise SubscriptionNotFoundError(str(user_id))

        effective_plan = subscription.resolve_effective_plan()
        plan_limits = await self._plan_limits_repository.get_by_plan(effective_plan)
        if plan_limits is None:
            raise PlanLimitsNotFoundError(effective_plan.value)

        cycle_start = resolve_cycle_start(subscription)
        ai_conversations_used = await self._ai_usage_repository.count_this_cycle(
            user_id, AiFeature.AGENT_CHAT, cycle_start
        )
        ai_reports_used = await self._ai_usage_repository.count_this_cycle(
            user_id, AiFeature.REPORT_NARRATIVE, cycle_start
        )
        history = await self._ai_usage_repository.get_monthly_history(user_id, HISTORY_MONTHS)

        return GetMyAiUsageOutput(
            plan=effective_plan,
            cycle_start=cycle_start,
            ai_conversations_used=ai_conversations_used,
            ai_conversations_limit=self._plan_limit_service.ai_conversation_limit(plan_limits),
            ai_reports_used=ai_reports_used,
            ai_reports_limit=self._plan_limit_service.ai_report_limit(plan_limits),
            history=history,
        )
