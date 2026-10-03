import uuid
from dataclasses import dataclass

from src.domain.reports.repository import ReportsRepository
from src.domain.reports.value_objects import CategoryDistributionItem, PeriodRange


@dataclass
class GetCategoryDistributionInput:
    user_id: uuid.UUID
    period: PeriodRange


class GetCategoryDistributionUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Distribuição por categoria do período, ordenada por total
    desc — alimenta o donut do Dashboard (top 3) e o ranking completo do
    Reports (build-context-05 §2.4).
    """

    def __init__(self, reports_repository: ReportsRepository) -> None:
        self._reports_repository = reports_repository

    async def execute(self, input_data: GetCategoryDistributionInput) -> list[CategoryDistributionItem]:
        return await self._reports_repository.get_category_distribution(
            input_data.user_id, input_data.period
        )
