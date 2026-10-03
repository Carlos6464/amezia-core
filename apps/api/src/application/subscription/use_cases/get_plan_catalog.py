from dataclasses import dataclass

from src.domain.subscription.entities import BillingCycle, Plan, PlanLimits, PlanPrice
from src.domain.subscription.exceptions import PlanLimitsNotFoundError
from src.domain.subscription.repository import PlanLimitsRepository, PlanPriceRepository

_ALL_PLANS = [Plan.FREE, Plan.PRO, Plan.PREMIUM]
_PAID_PLANS = {Plan.PRO, Plan.PREMIUM}


@dataclass
class PlanCatalogEntry:
    plan: Plan
    limits: PlanLimits
    monthly_price: PlanPrice | None
    annual_price: PlanPrice | None


class GetPlanCatalogUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Catálogo público de planos (build-context-09, reformulado
    2026-09-10) — usado pelas telas `register-plan-page`/
    `settings-plans-page` pra exibir preço e limites reais, sem hardcode
    no frontend. Deliberadamente sem autenticação (`register-plan-page`
    é exibida antes do cadastro existir) — só expõe dado de catálogo
    (preço, limite), nunca dado de conta.
    """

    def __init__(
        self, plan_limits_repository: PlanLimitsRepository, plan_price_repository: PlanPriceRepository
    ) -> None:
        self._plan_limits_repository = plan_limits_repository
        self._plan_price_repository = plan_price_repository

    async def execute(self) -> list[PlanCatalogEntry]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Free nunca tem preço (`monthly_price`/`annual_price`
        sempre `None`) — só os limites. Pro/Premium buscam o preço
        ativo de cada ciclo; `None` quando o Admin ainda não cadastrou
        aquele ciclo (ex.: anual, antes de existir na conta Stripe).
        """
        entries = []
        for plan in _ALL_PLANS:
            limits = await self._plan_limits_repository.get_by_plan(plan)
            if limits is None:
                raise PlanLimitsNotFoundError(plan.value)

            monthly_price = None
            annual_price = None
            if plan in _PAID_PLANS:
                monthly_price = await self._plan_price_repository.get_active(
                    plan, BillingCycle.MONTHLY
                )
                annual_price = await self._plan_price_repository.get_active(plan, BillingCycle.ANNUAL)

            entries.append(
                PlanCatalogEntry(
                    plan=plan, limits=limits, monthly_price=monthly_price, annual_price=annual_price
                )
            )
        return entries
