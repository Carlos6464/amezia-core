import uuid
from dataclasses import dataclass

from src.domain.reports.repository import ReportsRepository
from src.domain.reports.value_objects import PaymentMethodDistributionItem, PeriodRange


@dataclass
class GetPaymentMethodDistributionInput:
    user_id: uuid.UUID
    period: PeriodRange


class GetPaymentMethodDistributionUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Distribuição por tipo de pagamento do período, ordenada
    por total desc — alimenta a lista lateral com % do Dashboard/Reports
    (pedido direto do usuário, fora de qualquer build-context, mesmo
    padrão visual de `GetCategoryDistributionUseCase`).
    """

    def __init__(self, reports_repository: ReportsRepository) -> None:
        self._reports_repository = reports_repository

    async def execute(
        self, input_data: GetPaymentMethodDistributionInput
    ) -> list[PaymentMethodDistributionItem]:
        return await self._reports_repository.get_payment_method_distribution(
            input_data.user_id, input_data.period
        )
