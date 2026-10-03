import uuid
from datetime import UTC, date, datetime

from src.application.ai_usage.use_cases.check_ai_usage_limit import CheckAiUsageLimitUseCase
from src.application.ai_usage.use_cases.record_ai_usage import RecordAiUsageUseCase
from src.application.reports.use_cases.generate_ai_narrative import (
    GenerateAiNarrativeInput,
    GenerateAiNarrativeUseCase,
)
from src.domain.ai_usage.exceptions import AiUsageLimitExceededError
from src.domain.conversation.exceptions import AllProvidersUnavailableError
from src.domain.reports.value_objects import PeriodRange
from src.domain.shared.value_objects import PublicId
from src.domain.transaction.value_objects import Period
from src.infrastructure.ai.chat_completion_gateway import ChatCompletionGateway
from src.infrastructure.database.repositories.ai_usage_repository import (
    SqlAlchemyAiUsageRepository,
)
from src.infrastructure.database.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from src.infrastructure.database.repositories.sqlalchemy_reports_repository import (
    SqlAlchemyReportsRepository,
)
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemyPlanLimitsRepository,
    SqlAlchemySubscriptionRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.session import async_session_factory
from src.infrastructure.queue.ws_publisher import publish_to_user


async def generate_ai_narrative_job(
    ctx: dict,
    user_id: str,
    date_from: str,
    date_to: str,
    category_id: str | None,
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Job ARQ (registrado em `infrastructure/queue/worker.py::
    WorkerSettings.functions`) — enfileirado por `POST /reports/narrative`
    depois do throttle passar (build-context-05 §2.7). Mesmo padrão do
    job `generate_ai_response` (build-context-04): roda fora do ciclo de
    requisição HTTP, abre sua própria `AsyncSession`, resolve o usuário
    (e seu `language`, RN-10) antes de chamar o use case — sai em
    silêncio (sem publicar nada) se a conta foi excluída entre o
    enfileiramento e a execução, mesmo tratamento do job irmão. Em caso
    de falha dos dois providers, publica `report.narrative.failed` em vez
    de `report.narrative.ready`.
    """
    async with async_session_factory() as session:
        user_repository = SqlAlchemyUserRepository(session)
        user = await user_repository.get_by_id(uuid.UUID(user_id))
        if user is None:
            return

        period = PeriodRange(
            start=Period(
                year=date.fromisoformat(date_from).year, month=date.fromisoformat(date_from).month
            ),
            end=Period(
                year=date.fromisoformat(date_to).year, month=date.fromisoformat(date_to).month
            ),
        )
        use_case = GenerateAiNarrativeUseCase(
            reports_repository=SqlAlchemyReportsRepository(session),
            category_repository=SqlAlchemyCategoryRepository(session),
            chat_completion_port=ChatCompletionGateway(),
            check_ai_usage_limit_use_case=CheckAiUsageLimitUseCase(
                SqlAlchemySubscriptionRepository(session),
                SqlAlchemyPlanLimitsRepository(session),
                SqlAlchemyAiUsageRepository(session),
            ),
            record_ai_usage_use_case=RecordAiUsageUseCase(SqlAlchemyAiUsageRepository(session)),
        )

        try:
            narrative = await use_case.execute(
                GenerateAiNarrativeInput(
                    user_id=user.id,
                    period=period,
                    category_public_id=PublicId(category_id) if category_id else None,
                    language=user.language,
                )
            )
        except AllProvidersUnavailableError:
            await publish_to_user(
                user.id,
                {"event": "report.narrative.failed", "payload": {"reason": "ai_provider_unavailable"}},
            )
            return
        except AiUsageLimitExceededError:
            await publish_to_user(
                user.id,
                {"event": "report.narrative.failed", "payload": {"reason": "ai_usage_limit_exceeded"}},
            )
            return

        # Desde o build-context-10, `use_case.execute` grava um `AiUsageEvent` em
        # caso de sucesso (`RecordAiUsageUseCase`) — este job não tinha nenhuma
        # escrita própria antes disso, então nunca precisou commitar; agora precisa.
        await session.commit()
        await publish_to_user(
            user.id,
            {
                "event": "report.narrative.ready",
                "payload": {
                    "narrative": narrative,
                    "period": {"date_from": date_from, "date_to": date_to},
                    "language": user.language.value,
                    "generated_at": datetime.now(UTC).isoformat(),
                },
            },
        )
