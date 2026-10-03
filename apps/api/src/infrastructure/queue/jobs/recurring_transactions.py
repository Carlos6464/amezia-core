from datetime import UTC, datetime

from src.application.transaction.use_cases.generate_due_recurrences import (
    GenerateDueRecurrencesUseCase,
)
from src.infrastructure.database.repositories.recurrence_rule_repository import (
    SqlAlchemyRecurrenceRuleRepository,
)
from src.infrastructure.database.repositories.transaction_repository import (
    SqlAlchemyTransactionRepository,
)
from src.infrastructure.database.session import async_session_factory


async def generate_recurring_transactions(ctx: dict) -> int:
    """
    Autor: Carlos Adriano
    Data: 2026-08-09
    Descrição: Job ARQ cron diário (registrado em
    `infrastructure/queue/worker.py::WorkerSettings.cron_jobs`) —
    materializa a próxima ocorrência de cada RecurrenceRule ativa cujo
    `next_occurrence_date` já chegou (build-context-03 §2.7). Roda fora
    do ciclo de requisição HTTP, então abre sua própria `AsyncSession` e
    comita ao final — diferente dos routers, aqui não há um `Depends(get_db)`
    fechando a sessão para nós. Usa `datetime.now(UTC).date()` em vez de
    `date.today()` (timezone-naive, lê o relógio local do host) — o
    projeto todo já opera em UTC (RN implícita dos timestamps `TIMESTAMPTZ`).
    """
    async with async_session_factory() as session:
        use_case = GenerateDueRecurrencesUseCase(
            transaction_repository=SqlAlchemyTransactionRepository(session),
            recurrence_rule_repository=SqlAlchemyRecurrenceRuleRepository(session),
        )
        generated = await use_case.execute(datetime.now(UTC).date())
        await session.commit()
        return generated
