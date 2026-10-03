from src.domain.subscription.entities import Plan, PlanPrice
from src.domain.subscription.repository import PlanPriceRepository

_PAID_PLANS = [Plan.PRO, Plan.PREMIUM]


class ListPlanPricesUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Lista o catálogo de preços dos planos pagos pro Admin
    (ativos e arquivados) — alimenta a tela de gestão de planos,
    mostrando o histórico de valores já praticados por combinação
    (plano, ciclo).
    """

    def __init__(self, plan_price_repository: PlanPriceRepository) -> None:
        self._plan_price_repository = plan_price_repository

    async def execute(self) -> dict[Plan, list[PlanPrice]]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Uma consulta por plano pago — volume baixo (poucas
        linhas por plano), não justifica uma query única mais
        complexa.
        """
        return {plan: await self._plan_price_repository.list_for_plan(plan) for plan in _PAID_PLANS}
