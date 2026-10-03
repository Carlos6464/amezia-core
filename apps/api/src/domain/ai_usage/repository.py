import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from src.domain.ai_usage.entities import AiFeature, AiProvider, AiUsageEvent


@dataclass
class MonthlyUsagePoint:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Um ponto do histórico mensal de uso de IA de um usuário
    (build-context-10 §2.6, tabela `usage-history-table`) — só as 2
    features sujeitas a limite de plano, mesmo recorte de
    `CheckAiUsageLimitUseCase`.
    """

    month: date
    ai_conversations: int
    ai_reports: int


@dataclass
class FeatureUsageTotal:
    feature: AiFeature
    event_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost_micros: int


@dataclass
class ProviderUsageTotal:
    provider: AiProvider
    event_count: int
    estimated_cost_micros: int


@dataclass
class TopConsumer:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Uma linha da tabela "por usuário" do overview do admin —
    só o que vem de `ai_usage_events`; nome/e-mail/plano são resolvidos
    à parte por `GetAdminAiUsageOverviewUseCase` (via `UserRepository`/
    `SubscriptionRepository`), pra este repositório não depender de
    tabelas de outro bounded context.
    """

    user_id: uuid.UUID
    ai_conversations: int
    ai_reports: int
    estimated_cost_micros: int


@dataclass
class AdminAiUsageAggregate:
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost_micros: int
    by_feature: list[FeatureUsageTotal]
    by_provider: list[ProviderUsageTotal]
    top_consumers: list[TopConsumer]


class AiUsageRepository(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Interface de persistência/agregação de `ai_usage_events`
    (build-context-10 §2.1) — implementada em
    infrastructure/database/repositories/ai_usage_repository.py.
    """

    async def record(self, event: AiUsageEvent) -> AiUsageEvent: ...

    async def count_this_cycle(
        self, user_id: uuid.UUID, feature: AiFeature, cycle_start: datetime
    ) -> int:
        """
        Quantos eventos de `feature` o usuário já gerou desde
        `cycle_start` — usado tanto por `CheckAiUsageLimitUseCase`
        (bloqueio) quanto por `GetMyAiUsageUseCase` (barra de uso).
        """
        ...

    async def get_monthly_history(
        self, user_id: uuid.UUID, months: int
    ) -> list[MonthlyUsagePoint]:
        """Últimos `months` meses (mês calendário, mais recente por último) — alimenta o histórico da tela de uso."""
        ...

    async def aggregate_for_admin(self, since: datetime) -> AdminAiUsageAggregate:
        """Agregado de todos os eventos desde `since` (início do mês corrente) — alimenta o overview do admin."""
        ...
