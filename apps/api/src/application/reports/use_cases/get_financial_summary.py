import uuid
from dataclasses import dataclass

from src.domain.reports.repository import ReportsRepository
from src.domain.reports.value_objects import FinancialSummary, PeriodRange


@dataclass
class GetFinancialSummaryInput:
    user_id: uuid.UUID
    period: PeriodRange


class GetFinancialSummaryUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Resumo financeiro do período — totais, maior categoria e
    maior transação (build-context-05 §2.4). RN-01: `user_id` só é
    aceito neste dataclass de entrada, nunca lido de outro lugar —
    o router sempre o preenche a partir do usuário autenticado (JWT).
    """

    def __init__(self, reports_repository: ReportsRepository) -> None:
        self._reports_repository = reports_repository

    async def execute(self, input_data: GetFinancialSummaryInput) -> FinancialSummary:
        return await self._reports_repository.get_financial_summary(
            input_data.user_id, input_data.period
        )
