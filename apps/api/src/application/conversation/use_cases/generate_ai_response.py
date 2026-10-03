import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from src.application.ai_usage.use_cases.check_ai_usage_limit import (
    CheckAiUsageLimitInput,
    CheckAiUsageLimitUseCase,
)
from src.application.ai_usage.use_cases.record_ai_usage import (
    RecordAiUsageInput,
    RecordAiUsageUseCase,
)
from src.application.conversation.use_cases.summarize_old_messages import (
    SummarizeOldMessagesUseCase,
)
from src.application.embedding.use_cases.index_conversation_message_embedding import (
    IndexConversationMessageEmbeddingUseCase,
)
from src.application.embedding.use_cases.search_relevant_context import (
    SearchRelevantContextUseCase,
)
from src.domain.ai_usage.entities import AiFeature
from src.domain.conversation.entities import ConversationMessage
from src.domain.conversation.ports import ChatCompletionPort, ChatMessage
from src.domain.conversation.repository import ConversationRepository
from src.domain.conversation.value_objects import MessageRole
from src.domain.embedding.repository import EmbeddingMatch
from src.domain.transaction.repository import TransactionFilters, TransactionRepository
from src.domain.transaction.value_objects import Period, TransactionType, add_months
from src.domain.user.repository import UserRepository
from src.domain.user.value_objects import Language

TITLE_MAX_LENGTH = 48
FINANCIAL_SNAPSHOT_TREND_MONTHS = 3

_LANGUAGE_NAMES = {Language.PT_BR: "Brazilian Portuguese (pt-BR)", Language.EN: "English"}

_PERSONA_INSTRUCTION = (
    "You are Amezia's financial assistant, embedded in a personal finance app. Be "
    "clear, concise and friendly. The financial snapshot below is computed directly "
    "from the user's real data (not a guess) — treat it as ground truth for totals, "
    "budget status and month-over-month comparisons. The RAG context block, when "
    "present, has specific transaction/message excerpts for more detailed questions "
    "(e.g. a particular purchase). Never guess, estimate or invent a number that "
    "isn't in the snapshot or context below — if you don't have the data to answer "
    "precisely, say so plainly instead of making one up. The chat UI renders a small "
    "subset of markdown (**bold**, *italics*, `code`, bullet/numbered lists, "
    "paragraphs) — feel free to use those sparingly to improve readability, but "
    "avoid headings and nested formatting the renderer doesn't support."
)


def _format_cents(cents: int) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-12
    Descrição: Formata centavos como "1234,56" (vírgula decimal) — mesmo
    padrão já usado no texto-fonte dos embeddings de transação
    (`build_transaction_content`), pra manter o formato de moeda
    consistente em todo o contexto mostrado ao provider.
    """
    return f"{(Decimal(cents) / 100):.2f}".replace(".", ",")


async def _build_financial_snapshot(
    transaction_repository: TransactionRepository,
    user_id: uuid.UUID,
    monthly_budget_cents: int | None,
    today: date,
) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-12
    Descrição: Bloco determinístico (sem RAG, sem chance de alucinação)
    com o total gasto em cada um dos últimos `FINANCIAL_SNAPSHOT_TREND_MONTHS`
    meses (incluindo o atual, parcial), o status do teto mensal e o
    total por categoria no mês atual — via `TransactionRepository.sum_amount`/
    `sum_by_category` (já existentes, usados por Transações/Relatórios/
    Categorias), não por busca vetorial. Corrige o caso encontrado em
    produção (2026-08-12): perguntas de agregação ("quanto gastei esse
    mês", "em qual categoria eu mais gastei") têm baixa similaridade
    semântica com o texto de uma transação individual ("Compra de R$ X
    em Y"), então o RAG sozinho quase nunca trazia contexto suficiente —
    o modelo ou inventava um número (total mensal, primeiro caso
    corrigido) ou dizia não ter o dado (categoria, este caso). Perguntas
    de agregação (total, teto, comparação de meses, ranking de
    categoria) sempre têm dado real aqui, independente do threshold de
    similaridade do RAG.
    """
    month_totals: list[tuple[date, int]] = []
    for offset in range(FINANCIAL_SNAPSHOT_TREND_MONTHS):
        month_date = add_months(today, -offset)
        filters = TransactionFilters(
            type=TransactionType.EXPENSE, period=Period(year=month_date.year, month=month_date.month)
        )
        total_cents = await transaction_repository.sum_amount(user_id, filters)
        month_totals.append((month_date, total_cents))

    current_month_date, current_month_cents = month_totals[0]
    lines = [
        (
            f"Total spent so far in {current_month_date.strftime('%B %Y')}: "
            f"R$ {_format_cents(current_month_cents)}"
        )
    ]

    if monthly_budget_cents:
        used_percentage = round(current_month_cents / monthly_budget_cents * 100)
        lines.append(
            f"Monthly budget: R$ {_format_cents(monthly_budget_cents)} "
            f"({used_percentage}% used so far)"
        )
    else:
        lines.append("Monthly budget: not configured by the user")

    trend = "\n".join(
        f"- {month_date.strftime('%B %Y')}: R$ {_format_cents(total_cents)}"
        for month_date, total_cents in month_totals
    )
    lines.append(f"Spending by month (most recent first):\n{trend}")

    category_filters = TransactionFilters(
        type=TransactionType.EXPENSE, period=Period(year=today.year, month=today.month)
    )
    category_totals = await transaction_repository.sum_by_category(user_id, category_filters)
    if category_totals:
        category_breakdown = "\n".join(
            f"- {name}: R$ {_format_cents(total_cents)}" for name, total_cents in category_totals
        )
        lines.append(
            f"Spending by category in {current_month_date.strftime('%B %Y')} "
            f"(highest first):\n{category_breakdown}"
        )
    else:
        lines.append(f"Spending by category in {current_month_date.strftime('%B %Y')}: none yet")

    return "\n".join(lines)


def _build_system_instruction(
    language: Language,
    summary: str | None,
    financial_snapshot: str,
    rag_matches: list[EmbeddingMatch],
) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-12
    Descrição: Monta a instrução de sistema — persona + instrução de
    idioma (RN-10, sempre no idioma do perfil, não no idioma do texto do
    histórico/contexto) + resumo comprimido (se houver) + o snapshot
    financeiro determinístico (sempre presente, ver
    `_build_financial_snapshot`) + bloco de contexto RAG (até
    `RAG_TOP_K` trechos, rotulados por `source_type`, build-context-04
    §2.3/§2.4). O texto da instrução em si fica em inglês (convenção de
    código/orquestração interna) — só a resposta gerada precisa
    respeitar `language`.
    """
    parts = [
        (
            f"{_PERSONA_INSTRUCTION} Always answer in {_LANGUAGE_NAMES[language]}, "
            "regardless of the language used in the summary/context below."
        ),
        f"User's financial snapshot:\n{financial_snapshot}",
    ]
    if summary:
        parts.append(f"Conversation summary so far:\n{summary}")
    if rag_matches:
        context = "\n".join(
            f"- [{match.source_type.value}] {match.content}" for match in rag_matches
        )
        parts.append(f"Relevant context from the user's financial history:\n{context}")
    return "\n\n".join(parts)


def _generate_title(first_message: str) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Heurística MVP1 de título automático — deriva da 1ª
    mensagem do usuário, normalizada (espaços colapsados) e truncada a
    `TITLE_MAX_LENGTH` caracteres, sem chamada extra ao provider só para
    nomear a conversa (build-context-04 §2.4, passo 6).
    """
    normalized = " ".join(first_message.split())
    if len(normalized) <= TITLE_MAX_LENGTH:
        return normalized
    return normalized[: TITLE_MAX_LENGTH - 1].rstrip() + "…"


@dataclass
class GenerateAiResponseInput:
    conversation_id: int
    message_id: int


class GenerateAiResponseUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-12
    Descrição: Entrypoint do job ARQ `generate_ai_response` (roda no
    container `worker`, nunca no `api`) — orquestra o fluxo completo
    (build-context-04 §2.3/§2.4, ajustado em 2026-08-12): carrega a
    conversa e as mensagens ainda não resumidas, comprime as antigas se
    passar do threshold, monta o snapshot financeiro determinístico
    (`_build_financial_snapshot` — total do mês/teto/tendência,
    calculado direto via `TransactionRepository`, nunca por busca
    vetorial), busca contexto RAG complementar, checa o limite mensal de
    plano (`CheckAiUsageLimitUseCase`, build-context-10 §2.5, feature
    `agent_chat`), chama o provider (via `ChatCompletionPort`, que
    resolve o fallback Gemini→Grok), persiste a resposta, gera o título
    automático na 1ª resposta, indexa os embeddings da pergunta e da
    resposta, e registra o uso de IA (`RecordAiUsageUseCase`). Não
    captura `AllProvidersUnavailableError`/`AiUsageLimitExceededError` —
    propaga pra quem chama (job ARQ do chat web, ou `HandleChatStateUseCase`
    do bot) decidir o evento/mensagem a devolver.
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        user_repository: UserRepository,
        transaction_repository: TransactionRepository,
        chat_completion_port: ChatCompletionPort,
        search_relevant_context_use_case: SearchRelevantContextUseCase,
        summarize_old_messages_use_case: SummarizeOldMessagesUseCase,
        index_conversation_message_embedding_use_case: IndexConversationMessageEmbeddingUseCase,
        summary_threshold: int,
        check_ai_usage_limit_use_case: CheckAiUsageLimitUseCase,
        record_ai_usage_use_case: RecordAiUsageUseCase,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._user_repository = user_repository
        self._transaction_repository = transaction_repository
        self._chat_completion_port = chat_completion_port
        self._search_relevant_context_use_case = search_relevant_context_use_case
        self._summarize_old_messages_use_case = summarize_old_messages_use_case
        self._index_conversation_message_embedding_use_case = (
            index_conversation_message_embedding_use_case
        )
        self._summary_threshold = summary_threshold
        self._check_ai_usage_limit_use_case = check_ai_usage_limit_use_case
        self._record_ai_usage_use_case = record_ai_usage_use_case

    async def execute(self, input_data: GenerateAiResponseInput) -> ConversationMessage | None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Devolve `None` (no-op silencioso) se a conversa ou a
        mensagem do usuário não existirem mais no momento em que o job
        roda — cenário raro (ex.: conta excluída entre o enfileiramento e
        a execução), mas não deve derrubar o worker.
        """
        conversation = await self._conversation_repository.get_by_id(input_data.conversation_id)
        if conversation is None:
            return None

        user_message = await self._conversation_repository.get_message_by_id(
            input_data.message_id
        )
        if user_message is None:
            return None

        user = await self._user_repository.get_by_id(conversation.user_id)
        if user is None:
            return None

        unsummarized = await self._conversation_repository.list_messages_after(
            conversation.id, conversation.summarized_until_message_id
        )
        if len(unsummarized) > self._summary_threshold:
            conversation = await self._summarize_old_messages_use_case.execute(
                conversation, unsummarized
            )
            unsummarized = await self._conversation_repository.list_messages_after(
                conversation.id, conversation.summarized_until_message_id
            )

        rag_matches = await self._search_relevant_context_use_case.execute(
            conversation.user_id, user_message.content
        )
        financial_snapshot = await _build_financial_snapshot(
            self._transaction_repository,
            conversation.user_id,
            user.monthly_budget_cents,
            datetime.now(UTC).date(),
        )

        system_instruction = _build_system_instruction(
            user.language, conversation.summary, financial_snapshot, rag_matches
        )
        chat_messages = [
            ChatMessage(role=message.role, content=message.content) for message in unsummarized
        ]

        await self._check_ai_usage_limit_use_case.execute(
            CheckAiUsageLimitInput(user_id=conversation.user_id, feature=AiFeature.AGENT_CHAT)
        )
        result = await self._chat_completion_port.complete(system_instruction, chat_messages)
        await self._record_ai_usage_use_case.execute(
            RecordAiUsageInput(
                user_id=conversation.user_id,
                feature=AiFeature.AGENT_CHAT,
                provider=result.provider,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
        )

        assistant_message = await self._conversation_repository.add_message(
            ConversationMessage(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=result.content,
                provider_used=result.provider,
            )
        )

        if conversation.title is None:
            conversation.title = _generate_title(user_message.content)
        conversation.last_message_at = assistant_message.created_at
        await self._conversation_repository.update(conversation)

        await self._index_conversation_message_embedding_use_case.execute(
            conversation.user_id, user_message
        )
        await self._index_conversation_message_embedding_use_case.execute(
            conversation.user_id, assistant_message
        )

        return assistant_message
