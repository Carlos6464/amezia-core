import datetime as dt
from typing import Literal

from pydantic import BaseModel

from src.application.ai_usage.use_cases.get_my_ai_usage import GetMyAiUsageOutput
from src.domain.ai_usage.repository import MonthlyUsagePoint

PlanLiteral = Literal["free", "pro", "premium"]


class MonthlyUsagePointResponse(BaseModel):
    month: dt.date
    ai_conversations: int
    ai_reports: int

    @classmethod
    def from_entity(cls, point: MonthlyUsagePoint) -> "MonthlyUsagePointResponse":
        return cls(
            month=point.month, ai_conversations=point.ai_conversations, ai_reports=point.ai_reports
        )


class GetMyAiUsageResponse(BaseModel):
    plan: PlanLiteral
    cycle_start: dt.datetime
    ai_conversations_used: int
    ai_conversations_limit: int | None
    ai_reports_used: int
    ai_reports_limit: int | None
    history: list[MonthlyUsagePointResponse]

    @classmethod
    def from_dto(cls, output: GetMyAiUsageOutput) -> "GetMyAiUsageResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Converte `GetMyAiUsageOutput` (application layer) no
        schema de resposta HTTP de `GET /ai-usage/me` — alimenta as
        barras de uso e a tabela de histórico de `settings-usage-page`.
        """
        return cls(
            plan=output.plan.value,
            cycle_start=output.cycle_start,
            ai_conversations_used=output.ai_conversations_used,
            ai_conversations_limit=output.ai_conversations_limit,
            ai_reports_used=output.ai_reports_used,
            ai_reports_limit=output.ai_reports_limit,
            history=[MonthlyUsagePointResponse.from_entity(point) for point in output.history],
        )
