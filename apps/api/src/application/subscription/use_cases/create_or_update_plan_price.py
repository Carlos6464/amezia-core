from dataclasses import dataclass

from src.domain.subscription.entities import BillingCycle, Plan, PlanPrice
from src.domain.subscription.exceptions import PlanLimitsNotFoundError
from src.domain.subscription.ports import PaymentGatewayPort
from src.domain.subscription.repository import PlanLimitsRepository, PlanPriceRepository

_PAID_PLANS = {Plan.PRO, Plan.PREMIUM}

_PRODUCT_NAMES = {
    Plan.PRO: "Amezia Pro",
    Plan.PREMIUM: "Amezia Premium",
}

_STRIPE_INTERVALS = {
    BillingCycle.MONTHLY: "month",
    BillingCycle.ANNUAL: "year",
}


@dataclass
class CreateOrUpdatePlanPriceInput:
    plan: Plan
    billing_cycle: BillingCycle
    unit_amount_cents: int
    currency: str = "brl"


class CreateOrUpdatePlanPriceUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Cadastro/edição de preço pelo Admin (revisado em
    2026-09-10, a pedido do usuário — antes eram 4 `STRIPE_PRICE_*`
    fixos no `.env`, exigindo criar os preços manualmente no dashboard
    do Stripe e fazer redeploy pra mudar um valor). Como um Price do
    Stripe é imutável em valor, "editar" sempre é: criar um Price novo,
    arquivar o anterior (se existir) e trocar qual linha de
    `plan_prices` está `active=True` — nunca uma atualização in-place
    do valor de um Price já existente.
    """

    def __init__(
        self,
        plan_limits_repository: PlanLimitsRepository,
        plan_price_repository: PlanPriceRepository,
        payment_gateway: PaymentGatewayPort,
    ) -> None:
        self._plan_limits_repository = plan_limits_repository
        self._plan_price_repository = plan_price_repository
        self._payment_gateway = payment_gateway

    async def execute(self, input_data: CreateOrUpdatePlanPriceInput) -> PlanPrice:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Garante o Produto Stripe do plano (cria só na 1ª
        vez), cria o Price novo, arquiva o Price vigente da mesma
        combinação (plano, ciclo) — no Stripe e em `plan_prices` — e
        ativa o novo.
        """
        if input_data.plan not in _PAID_PLANS:
            raise ValueError(f"Cannot create a price for plan={input_data.plan.value}")

        product_id = await self._resolve_product_id(input_data.plan)

        stripe_price_id = await self._payment_gateway.create_price(
            product_id=product_id,
            unit_amount_cents=input_data.unit_amount_cents,
            currency=input_data.currency,
            interval=_STRIPE_INTERVALS[input_data.billing_cycle],
        )

        previous = await self._plan_price_repository.get_active(
            input_data.plan, input_data.billing_cycle
        )
        if previous is not None:
            await self._payment_gateway.archive_price(previous.stripe_price_id)
            await self._plan_price_repository.deactivate(input_data.plan, input_data.billing_cycle)

        return await self._plan_price_repository.create(
            PlanPrice(
                plan=input_data.plan,
                billing_cycle=input_data.billing_cycle,
                stripe_price_id=stripe_price_id,
                unit_amount_cents=input_data.unit_amount_cents,
                currency=input_data.currency,
            )
        )

    async def _resolve_product_id(self, plan: Plan) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Reaproveita `plan_limits.stripe_product_id` se já
        existir; cria o Produto no Stripe só na 1ª chamada pra esse
        plano.
        """
        plan_limits = await self._plan_limits_repository.get_by_plan(plan)
        if plan_limits is None:
            raise PlanLimitsNotFoundError(plan.value)
        if plan_limits.stripe_product_id is not None:
            return plan_limits.stripe_product_id

        product_id = await self._payment_gateway.create_product(_PRODUCT_NAMES[plan])
        await self._plan_limits_repository.set_stripe_product_id(plan, product_id)
        return product_id
