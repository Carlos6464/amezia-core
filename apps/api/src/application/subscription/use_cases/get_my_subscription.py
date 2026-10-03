import uuid
from dataclasses import dataclass

from src.domain.subscription.entities import PlanLimits, Subscription
from src.domain.subscription.exceptions import PlanLimitsNotFoundError, SubscriptionNotFoundError
from src.domain.subscription.repository import PlanLimitsRepository, SubscriptionRepository


@dataclass
class GetMySubscriptionOutput:
    subscription: Subscription
    plan_limits: PlanLimits


class GetMySubscriptionUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: `GET /subscriptions/me` (build-context-09 §2.1/T10) —
    estado atual da assinatura do usuário autenticado (RN-01, nunca
    aceita `user_id` externo) + os `PlanLimits` resolvidos pelo plano
    **efetivo** (`Subscription.resolve_effective_plan`, que já trata
    `legacy_pro_until` vencido como Free automaticamente, §2.7).
    """

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        plan_limits_repository: PlanLimitsRepository,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._plan_limits_repository = plan_limits_repository

    async def execute(self, user_id: uuid.UUID) -> GetMySubscriptionOutput:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Resolve a Subscription do usuário e os PlanLimits do
        plano efetivo — nunca do plano bruto armazenado, pra
        `legacy_pro_until` vencido já refletir Free sem exigir job.
        """
        subscription = await self._subscription_repository.get_by_user_id(user_id)
        if subscription is None:
            raise SubscriptionNotFoundError(str(user_id))

        effective_plan = subscription.resolve_effective_plan()
        plan_limits = await self._plan_limits_repository.get_by_plan(effective_plan)
        if plan_limits is None:
            raise PlanLimitsNotFoundError(effective_plan.value)

        return GetMySubscriptionOutput(subscription=subscription, plan_limits=plan_limits)
