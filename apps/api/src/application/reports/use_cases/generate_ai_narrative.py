import uuid
from dataclasses import dataclass
from decimal import Decimal

from src.application.ai_usage.use_cases.check_ai_usage_limit import (
    CheckAiUsageLimitInput,
    CheckAiUsageLimitUseCase,
)
from src.application.ai_usage.use_cases.record_ai_usage import (
    RecordAiUsageInput,
    RecordAiUsageUseCase,
)
from src.domain.ai_usage.entities import AiFeature
from src.domain.category.exceptions import CategoryNotFoundError
from src.domain.category.repository import CategoryRepository
from src.domain.conversation.ports import ChatCompletionPort, ChatMessage
from src.domain.conversation.value_objects import MessageRole
from src.domain.reports.repository import ReportsRepository
from src.domain.reports.value_objects import (
    CategoryDistributionItem,
    FinancialSummary,
    MonthlyEvolutionPoint,
    PeriodRange,
)
from src.domain.shared.value_objects import PublicId
from src.domain.user.value_objects import Language

_LANGUAGE_NAMES = {Language.PT_BR: "Brazilian Portuguese (pt-BR)", Language.EN: "English"}

_EMPTY_PERIOD_NARRATIVE = {
    Language.PT_BR: "Não há transações registradas neste período.",
    Language.EN: "There are no transactions recorded for this period.",
}

_PERSONA_INSTRUCTION = (
    "You are Amezia's financial report narrator, embedded in a personal finance app. Write a "
    "short narrative (2 to 4 short paragraphs) summarizing the user's finances for the period "
    "below, based only on the data provided — never invent, estimate or round a number that "
    "isn't here. Highlight the top spending categories, notable month-over-month trends and "
    "one practical recommendation when relevant. You may use **bold** for key figures/"
    "categories; avoid headings, bullet lists and any other markdown."
)

_GENERATE_MESSAGE = ChatMessage(role=MessageRole.USER, content="Write the narrative now.")


def _format_cents(cents: int) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Formata centavos como "1.234,56" — mesmo espírito de
    `generate_ai_response.py::_format_cents` (build-context-04).
    """
    return f"{(Decimal(cents) / 100):.2f}".replace(".", ",")


def _months_between(start_year: int, start_month: int, end_year: int, end_month: int) -> int:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Quantidade de meses cobertos por um `PeriodRange`
    (inclusive nas duas pontas) — usado para pedir a `ReportsRepository`
    exatamente a evolução mensal do intervalo selecionado pelo usuário,
    não um número fixo (diferente do line-chart do Dashboard, sempre 6).
    """
    return (end_year - start_year) * 12 + (end_month - start_month) + 1


def _build_system_instruction(
    language: Language,
    summary: FinancialSummary,
    evolution: list[MonthlyEvolutionPoint],
    distribution: list[CategoryDistributionItem],
) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Monta a instrução de sistema — persona + instrução de
    idioma (RN-10) + os 3 blocos de dados determinísticos buscados via
    `ReportsRepository` (resumo, evolução mensal, distribuição por
    categoria). Texto da instrução em inglês (convenção de código); só a
    narrativa gerada precisa respeitar `language`.
    """
    date_from, date_to = summary.period.date_range()
    lines = [
        f"Period: {date_from.isoformat()} to {date_to.isoformat()}",
        f"Total expenses: R$ {_format_cents(summary.total_expense)}",
        f"Transaction count: {summary.transaction_count}",
    ]
    if summary.top_category:
        top = summary.top_category
        lines.append(
            f"Top category: {top.category_name} (R$ {_format_cents(top.total)}, "
            f"{top.percentage:.0f}% of the period)"
        )
    if evolution:
        trend = "\n".join(
            f"- {point.period.year}-{point.period.month:02d}: R$ {_format_cents(point.total_expense)}"
            for point in evolution
        )
        lines.append(f"Month-by-month:\n{trend}")
    if distribution:
        breakdown = "\n".join(
            f"- {item.category_name}: R$ {_format_cents(item.total)} ({item.percentage:.0f}%)"
            for item in distribution
        )
        lines.append(f"Category distribution:\n{breakdown}")

    return (
        f"{_PERSONA_INSTRUCTION} Always answer in {_LANGUAGE_NAMES[language]}.\n\n"
        f"Financial data:\n" + "\n".join(lines)
    )


@dataclass
class GenerateAiNarrativeInput:
    user_id: uuid.UUID
    period: PeriodRange
    category_public_id: PublicId | None
    language: Language


class GenerateAiNarrativeUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Entrypoint do job ARQ `generate_ai_narrative_job` — busca
    `FinancialSummary` + `MonthlyEvolutionPoint[]` + `CategoryDistributionItem[]`
    via `ReportsRepository`, monta o prompt e chama o provider de IA
    (Gemini → fallback Grok, mesmo `ChatCompletionPort` do
    build-context-04) — build-context-05 §2.4/§2.7. Retorna a narrativa
    padrão fixa sem chamar o provider quando o período não tem nenhuma
    transação (evita custo e consumo de throttle desnecessário, e não
    checa/consome limite de IA por não haver chamada nenhuma). Checa o
    limite mensal de plano antes de chamar o provider
    (`CheckAiUsageLimitUseCase`, build-context-10 §2.5, feature
    `report_narrative`) e registra o uso depois (`RecordAiUsageUseCase`).
    Não captura `AllProvidersUnavailableError`/`AiUsageLimitExceededError`
    — propaga para o job decidir o evento a publicar.
    """

    def __init__(
        self,
        reports_repository: ReportsRepository,
        category_repository: CategoryRepository,
        chat_completion_port: ChatCompletionPort,
        check_ai_usage_limit_use_case: CheckAiUsageLimitUseCase,
        record_ai_usage_use_case: RecordAiUsageUseCase,
    ) -> None:
        self._reports_repository = reports_repository
        self._category_repository = category_repository
        self._chat_completion_port = chat_completion_port
        self._check_ai_usage_limit_use_case = check_ai_usage_limit_use_case
        self._record_ai_usage_use_case = record_ai_usage_use_case

    async def execute(self, input_data: GenerateAiNarrativeInput) -> str:
        # `ReportsRepository.get_financial_summary/get_monthly_evolution/
        # get_category_distribution` (build-context-05 §2.3) não aceitam
        # `category_id` — só `get_transactions_page`/`get_transactions_for_export`
        # fazem. A narrativa sempre reflete o período/tipo como um todo;
        # resolver a categoria aqui só valida que ela existe e pertence ao
        # usuário (RN-01) quando informada, sem filtrar os dados do prompt.
        await self._resolve_category_id(input_data.user_id, input_data.category_public_id)

        summary = await self._reports_repository.get_financial_summary(
            input_data.user_id, input_data.period
        )
        if summary.transaction_count == 0:
            return _EMPTY_PERIOD_NARRATIVE[input_data.language]

        months = _months_between(
            input_data.period.start.year,
            input_data.period.start.month or 1,
            input_data.period.end.year,
            input_data.period.end.month or 12,
        )
        evolution = await self._reports_repository.get_monthly_evolution(
            input_data.user_id, input_data.period.end, months
        )
        distribution = await self._reports_repository.get_category_distribution(
            input_data.user_id, input_data.period
        )

        system_instruction = _build_system_instruction(
            input_data.language, summary, evolution, distribution
        )
        await self._check_ai_usage_limit_use_case.execute(
            CheckAiUsageLimitInput(user_id=input_data.user_id, feature=AiFeature.REPORT_NARRATIVE)
        )
        result = await self._chat_completion_port.complete(system_instruction, [_GENERATE_MESSAGE])
        await self._record_ai_usage_use_case.execute(
            RecordAiUsageInput(
                user_id=input_data.user_id,
                feature=AiFeature.REPORT_NARRATIVE,
                provider=result.provider,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
        )
        return result.content

    async def _resolve_category_id(
        self, user_id: uuid.UUID, category_public_id: PublicId | None
    ) -> int | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-14
        Descrição: Mesmo padrão de
        `ListReportTransactionsUseCase._resolve_category_id` — usado
        aqui só para validar que a categoria informada existe e pertence
        ao usuário (RN-01), já que o resumo/evolução/distribuição da
        narrativa não são filtrados por categoria (ver nota em
        `execute`).
        """
        if category_public_id is None:
            return None
        category = await self._category_repository.get_by_public_id(category_public_id)
        if category is None or (not category.is_global and category.user_id != user_id):
            raise CategoryNotFoundError(str(category_public_id))
        return category.id
