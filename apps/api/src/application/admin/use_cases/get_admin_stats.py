import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from src.application.subscription.metrics import compute_churn_rate, compute_mrr_cents
from src.domain.ai_usage.entities import AiFeature
from src.domain.ai_usage.repository import AiUsageRepository
from src.domain.conversation.repository import ConversationRepository
from src.domain.feedback.repository import FeedbackRepository
from src.domain.subscription.repository import (
    PlanDistribution,
    PlanPriceRepository,
    SubscriptionRepository,
)
from src.domain.transaction.repository import TransactionRepository
from src.domain.user.repository import UserRepository
from src.domain.whatsapp_bot.repository import ProcessedBotMessageRepository

STATS_MONTHS = 6
_DAU_WINDOW_HOURS = 24
_MAU_WINDOW_DAYS = 30


@dataclass
class MonthlyUserPoint:
    month: date
    count: int


@dataclass
class UsageByChannel:
    web: int
    whatsapp: int


@dataclass
class AdminStats:
    total_users: int
    users_with_phone: int
    total_feedbacks: int
    new_users_by_month: list[MonthlyUserPoint]
    active_users_daily: int
    active_users_monthly: int
    subscriptions_by_plan: PlanDistribution
    mrr_cents: int
    churn_rate: float
    usage_by_channel: UsageByChannel


class GetAdminStatsUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: KPIs globais da Visão Geral do Admin (build-context-06
    §2.3/§2.4, estendido pelo build-context-11 §2.1) — total de
    usuários, novos usuários por mês, usuários com WhatsApp vinculado,
    total de feedbacks, DAU/MAU, distribuição de assinaturas por plano,
    MRR, churn e uso por canal (web vs. bot).
    """

    def __init__(
        self,
        user_repository: UserRepository,
        feedback_repository: FeedbackRepository,
        transaction_repository: TransactionRepository,
        conversation_repository: ConversationRepository,
        processed_bot_message_repository: ProcessedBotMessageRepository,
        subscription_repository: SubscriptionRepository,
        plan_price_repository: PlanPriceRepository,
        ai_usage_repository: AiUsageRepository,
    ) -> None:
        self._user_repository = user_repository
        self._feedback_repository = feedback_repository
        self._transaction_repository = transaction_repository
        self._conversation_repository = conversation_repository
        self._processed_bot_message_repository = processed_bot_message_repository
        self._subscription_repository = subscription_repository
        self._plan_price_repository = plan_price_repository
        self._ai_usage_repository = ai_usage_repository

    async def execute(self) -> AdminStats:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Agrega os KPIs originais (build-context-06) e os
        novos do build-context-11 (§2.1) — chamadas sequenciais
        simples, monta a série mensal e os agregados novos já
        convertidos pra DTO de aplicação.
        """
        total_users = await self._user_repository.count_total()
        users_with_phone = await self._user_repository.count_with_phone()
        total_feedbacks = await self._feedback_repository.count_total()
        monthly = await self._user_repository.count_new_users_by_month(STATS_MONTHS)

        active_users_daily, active_users_monthly = await self._compute_active_users()
        subscriptions_by_plan = await self._subscription_repository.get_plan_distribution()
        mrr_cents = await compute_mrr_cents(self._subscription_repository, self._plan_price_repository)
        churn_rate = await compute_churn_rate(self._subscription_repository)
        usage_by_channel = await self._compute_usage_by_channel()

        return AdminStats(
            total_users=total_users,
            users_with_phone=users_with_phone,
            total_feedbacks=total_feedbacks,
            new_users_by_month=[MonthlyUserPoint(month=month, count=count) for month, count in monthly],
            active_users_daily=active_users_daily,
            active_users_monthly=active_users_monthly,
            subscriptions_by_plan=subscriptions_by_plan,
            mrr_cents=mrr_cents,
            churn_rate=churn_rate,
            usage_by_channel=usage_by_channel,
        )

    async def _compute_active_users(self) -> tuple[int, int]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: DAU/MAU (build-context-11 §2.2) — usuário ativo é
        quem teve pelo menos 1 ação relevante no período (transação
        criada, mensagem no Agente, mensagem processada pelo bot).
        União feita em Python (`set | set`) sobre os 3 conjuntos de
        `user_id`, não uma query SQL cruzando bounded contexts — cada
        repositório continua restrito à sua própria tabela.
        """
        now = datetime.now(UTC)
        daily_since = now - timedelta(hours=_DAU_WINDOW_HOURS)
        monthly_since = now - timedelta(days=_MAU_WINDOW_DAYS)

        daily_users = await self._union_active_user_ids(daily_since)
        monthly_users = await self._union_active_user_ids(monthly_since)
        return len(daily_users), len(monthly_users)

    async def _union_active_user_ids(self, since: datetime) -> set[uuid.UUID]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: União dos 3 conjuntos de `user_id` ativos desde
        `since` — chamado uma vez pra DAU (`since` = 24h atrás) e outra
        pra MAU (`since` = 30 dias atrás).
        """
        transaction_users = await self._transaction_repository.list_distinct_active_user_ids_since(
            since
        )
        conversation_users = (
            await self._conversation_repository.list_distinct_active_user_ids_since(since)
        )
        bot_users = (
            await self._processed_bot_message_repository.list_distinct_active_user_ids_since(since)
        )
        return transaction_users | conversation_users | bot_users

    async def _compute_usage_by_channel(self) -> UsageByChannel:
        """
        Autor: Carlos Adriano
        Data: 2026-09-11
        Descrição: "Web vs. bot" no mês corrente (build-context-11
        §2.1) — reaproveita `AiUsageRepository.aggregate_for_admin`
        (build-context-10), que já discrimina por `feature`:
        `agent_chat`/`report_narrative` (bucket web) vs.
        `bot_expense_parsing`/`bot_audio_transcription` (bucket bot).
        Fonte mais simples de implementar já disponível — não é uma
        métrica de "toda ação do produto", só de uso de IA.
        """
        month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        aggregate = await self._ai_usage_repository.aggregate_for_admin(month_start)
        web = sum(
            item.event_count
            for item in aggregate.by_feature
            if item.feature in (AiFeature.AGENT_CHAT, AiFeature.REPORT_NARRATIVE)
        )
        whatsapp = sum(
            item.event_count
            for item in aggregate.by_feature
            if item.feature in (AiFeature.BOT_EXPENSE_PARSING, AiFeature.BOT_AUDIO_TRANSCRIPTION)
        )
        return UsageByChannel(web=web, whatsapp=whatsapp)
