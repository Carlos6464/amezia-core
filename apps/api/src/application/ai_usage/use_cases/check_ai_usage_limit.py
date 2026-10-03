import uuid
from dataclasses import dataclass

from src.application.ai_usage.cycle import resolve_cycle_start
from src.domain.ai_usage.entities import AiFeature
from src.domain.ai_usage.exceptions import AiUsageLimitExceededError
from src.domain.ai_usage.repository import AiUsageRepository
from src.domain.subscription.entities import Plan
from src.domain.subscription.repository import PlanLimitsRepository, SubscriptionRepository
from src.domain.subscription.services import PlanLimitService


@dataclass
class CheckAiUsageLimitInput:
    user_id: uuid.UUID
    feature: AiFeature


class CheckAiUsageLimitUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Chamado antes de qualquer chamada de IA sujeita a limite
    de plano (build-context-10 §2.5/T7) — hoje só `GenerateAiResponseUseCase`
    (chat web e modo Chat do bot) e `GenerateAiNarrativeUseCase`
    (narrativa de relatório). `bot_expense_parsing`/`bot_audio_transcription`
    nunca chamam este use case (§2.2 — só registrados, nunca bloqueiam).
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

    async def execute(self, input_data: CheckAiUsageLimitInput) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Levanta `AiUsageLimitExceededError` quando o usuário
        já atingiu o limite mensal do plano efetivo para a feature
        informada — nunca bloqueia quando o plano não tem limite
        cadastrado (`None` = ilimitado) ou quando `plan_limits` não foi
        encontrado (não deveria acontecer em produção — falha aberta em
        vez de derrubar o chat/narrativa por um problema de catálogo).
        """
        subscription = await self._subscription_repository.get_by_user_id(input_data.user_id)
        effective_plan = subscription.resolve_effective_plan() if subscription else Plan.FREE
        plan_limits = await self._plan_limits_repository.get_by_plan(effective_plan)
        if plan_limits is None:
            return

        limit = (
            self._plan_limit_service.ai_conversation_limit(plan_limits)
            if input_data.feature == AiFeature.AGENT_CHAT
            else self._plan_limit_service.ai_report_limit(plan_limits)
        )
        if limit is None:
            return

        cycle_start = resolve_cycle_start(subscription)
        count = await self._ai_usage_repository.count_this_cycle(
            input_data.user_id, input_data.feature, cycle_start
        )
        if count >= limit:
            raise AiUsageLimitExceededError(input_data.feature.value)
