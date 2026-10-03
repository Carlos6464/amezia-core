import uuid
from dataclasses import dataclass

from src.domain.reports.repository import ReportsRepository
from src.domain.reports.value_objects import MonthlyPaidPendingPoint
from src.domain.transaction.value_objects import Period

DEFAULT_MONTHS = 6


@dataclass
class GetMonthlyPaidPendingInput:
    user_id: uuid.UUID
    reference_period: Period
    months: int = DEFAULT_MONTHS


class GetMonthlyPaidPendingUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-15
    Descrição: Série mensal pago x pendente — alimenta o gráfico de
    barra dupla do Dashboard/Reports (pedido direto do usuário, fora de
    qualquer build-context), sempre `months=6` por padrão, mesmo recorte
    de `GetMonthlyEvolutionUseCase`.
    """

    def __init__(self, reports_repository: ReportsRepository) -> None:
        self._reports_repository = reports_repository

    async def execute(self, input_data: GetMonthlyPaidPendingInput) -> list[MonthlyPaidPendingPoint]:
        return await self._reports_repository.get_monthly_paid_pending(
            input_data.user_id, input_data.reference_period, input_data.months
        )
