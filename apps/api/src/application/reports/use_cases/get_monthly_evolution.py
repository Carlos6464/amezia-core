import uuid
from dataclasses import dataclass

from src.domain.reports.repository import ReportsRepository
from src.domain.reports.value_objects import MonthlyEvolutionPoint
from src.domain.transaction.value_objects import Period

DEFAULT_MONTHS = 6


@dataclass
class GetMonthlyEvolutionInput:
    user_id: uuid.UUID
    reference_period: Period
    months: int = DEFAULT_MONTHS


class GetMonthlyEvolutionUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Série mensal de despesas/receitas — alimenta o line-chart
    do Dashboard, sempre `months=6` no MVP1 (build-context-05 §2.4).
    """

    def __init__(self, reports_repository: ReportsRepository) -> None:
        self._reports_repository = reports_repository

    async def execute(self, input_data: GetMonthlyEvolutionInput) -> list[MonthlyEvolutionPoint]:
        return await self._reports_repository.get_monthly_evolution(
            input_data.user_id, input_data.reference_period, input_data.months
        )
