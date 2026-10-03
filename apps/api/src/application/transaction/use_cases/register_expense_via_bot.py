import json
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from src.application.ai_usage.use_cases.record_ai_usage import (
    RecordAiUsageInput,
    RecordAiUsageUseCase,
)
from src.domain.ai_usage.entities import AiFeature
from src.domain.category.entities import Category
from src.domain.category.repository import CategoryRepository
from src.domain.conversation.ports import ChatCompletionPort, ChatMessage
from src.domain.conversation.value_objects import MessageRole
from src.domain.transaction.exceptions import ExpenseParsingFailedError, NoCategoryMatchError
from src.domain.transaction.value_objects import RecurrenceFrequency

_FALLBACK_CATEGORY_NAME = "Outros"
_MIN_INSTALLMENTS = 2
_MAX_INSTALLMENTS_FROM_TEXT = 60  # mesmo teto de CreateTransactionUseCase.MAX_INSTALLMENTS

_SYSTEM_INSTRUCTION_TEMPLATE = """You extract structured expense data from a free-text message \
(written by a user of a personal finance app, in Portuguese or English, sent via text or \
transcribed from a voice message). Today's date is {today}.

Respond with a single-line strict JSON object, no markdown fences, no extra text, with exactly \
these keys:
- "amount": the expense value as a positive number (no currency symbol, dot as decimal separator)
- "category": the single best matching name from this exact list (copy verbatim): {categories}. \
If none of these categories is a reasonable match for this expense, set "category" to null instead \
of forcing a poor match.
- "description": a short description of the expense (in the same language as the user's message)
- "date": the expense date as "YYYY-MM-DD", resolving relative expressions ("today", "yesterday", \
"hoje", "ontem") against today's date above; use today's date if no date is mentioned
- "installment_total": if the message explicitly says this expense is being split into \
installments (e.g. "em 10 vezes", "parcelado em 3x", "dividido em 5 vezes", "in 6 installments"), \
the total number of installments as an integer; otherwise null. Never infer this from the amount \
alone — only from explicit installment language.
- "recurrence_frequency": if the message explicitly says this expense repeats periodically (e.g. \
"todo mês", "mensalmente", "toda semana", "todo ano", "recurring monthly"), one of "weekly", \
"monthly", "yearly" (always in English, exactly one of these three); otherwise null. A message \
can have "installment_total" OR "recurrence_frequency" set, never both — pick whichever the \
message actually describes.
- "amount_refers_to": only relevant when "installment_total" is set. "total" if "amount" is the \
whole sum being divided across the installments (e.g. "gastei 600 dividido em 10 vezes", "total \
de 900 em 3x" — the per-installment value is amount ÷ installment_total, do NOT compute this \
division yourself, just report "total"); "per_installment" if "amount" is explicitly the value of \
EACH installment (e.g. "parcelado em 3x de 100", "3 parcelas de 50 cada"). If the message is \
genuinely ambiguous about which one it is, set this to null instead of guessing — the application \
will ask the user to clarify. When "installment_total" is null, always set this to null too.

If you cannot find a plausible amount in the message, set "amount" to null.
"""


def _strip_accents(value: str) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Normaliza um texto removendo acentos e caixa, para o
    match de categoria não depender de acentuação exata devolvida pela
    IA ("Alimentacao" vs "Alimentação").
    """
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).strip().lower()


def _build_system_instruction(categories: list[Category], today: date) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Preenche o template de extração com a data de referência
    (para resolver "hoje"/"ontem") e a lista literal de categorias
    visíveis ao usuário, para a IA escolher um nome que já existe em vez
    de inventar um novo. "Outros" fica de fora da lista oferecida à IA
    (build-context-12) — sendo um "pega-tudo" por definição, a IA sempre
    a considerava "razoável" e nunca devolvia `category: null`, o que
    fazia o fluxo de categoria dinâmica nunca disparar de verdade
    (achado real, reportado pelo usuário testando o bot). "Outros"
    continua existindo como opção de sistema — só não é mais um destino
    automático da IA, aparece de volta como escolha explícita do usuário
    na lista numerada de `HandleExpenseStateUseCase._start_category_choice`.
    """
    offered = [category for category in categories if category.name != _FALLBACK_CATEGORY_NAME]
    category_names = ", ".join(f'"{category.name}"' for category in offered)
    return _SYSTEM_INSTRUCTION_TEMPLATE.format(today=today.isoformat(), categories=category_names)


def _parse_extraction(content: str) -> dict[str, object]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Parseia defensivamente a resposta da IA — sem infra de
    saída estruturada (JSON mode/function-calling) no projeto, a
    instrução de sistema pede JSON estrito e este parser tolera cercas
    de código (```json ... ```) que o provider às vezes inclui mesmo
    quando instruído a não incluir.
    """
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ExpenseParsingFailedError("AI response is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ExpenseParsingFailedError("AI response is not a JSON object")
    return data


def _resolve_category(category_name: object, categories: list[Category]) -> Category:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Casa o nome de categoria extraído pela IA contra as
    categorias visíveis ao usuário (globais + privadas, build-context-02)
    por igualdade normalizada (sem acento/caixa). Sem match, cai para a
    categoria de sistema "Outros" — sempre existe (seed, build-context-02
    §2.3), evita falhar o registro só por causa de uma categoria fora do
    esperado.
    """
    normalized_target = _strip_accents(category_name) if isinstance(category_name, str) else ""
    for category in categories:
        if _strip_accents(category.name) == normalized_target:
            return category

    for category in categories:
        if _strip_accents(category.name) == _strip_accents(_FALLBACK_CATEGORY_NAME):
            return category

    raise ExpenseParsingFailedError("no matching category and no fallback category available")


def _resolve_installment_and_recurrence(
    parsed: dict[str, object],
) -> tuple[int | None, RecurrenceFrequency | None]:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Extrai parcelamento/recorrência já mencionados na
    mensagem original (build-context-12, achado real: "gastei 600
    dividido em 10 vezes" forçava reperguntar o que o usuário já tinha
    dito) — validação defensiva igual ao resto do parsing: fora da faixa
    ou tipo errado vira `None` em vez de propagar lixo pro domínio.
    Nunca os dois ao mesmo tempo — `recurrence_frequency` tem prioridade
    se a IA, por algum motivo, mandar os dois preenchidos (mesma regra
    de prioridade de `CreateTransactionUseCase.execute`).
    """
    recurrence_raw = parsed.get("recurrence_frequency")
    if isinstance(recurrence_raw, str):
        try:
            return None, RecurrenceFrequency(recurrence_raw)
        except ValueError:
            pass

    installment_raw = parsed.get("installment_total")
    if isinstance(installment_raw, int) and _MIN_INSTALLMENTS <= installment_raw <= _MAX_INSTALLMENTS_FROM_TEXT:
        return installment_raw, None

    return None, None


def _resolve_amount_is_total(parsed: dict[str, object]) -> bool | None:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Só tem sentido quando `installment_total` também foi
    extraído — desambigua se o valor mencionado é o **total** a dividir
    (`"gastei 600 dividido em 10 vezes"` → 60/parcela) ou já o valor **de
    cada parcela** (`"parcelado em 3x de 100"` → 100/parcela). `None`
    (ambíguo, IA não conseguiu decidir) faz `HandleExpenseStateUseCase`
    perguntar o valor da parcela em vez de arriscar uma conta errada —
    pedido explícito do usuário: "caso não consiga entender, perguntar o
    valor por parcela". A divisão em si nunca é feita pela IA (aritmética
    de IA não é confiável o bastante pra dinheiro) — só o código calcula.
    """
    value = parsed.get("amount_refers_to")
    if value == "total":
        return True
    if value == "per_installment":
        return False
    return None


def _resolve_date(date_raw: object, today: date) -> date:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Converte o campo `date` extraído pela IA (esperado
    "YYYY-MM-DD") para `date` — qualquer valor ausente ou malformado
    cai para `today`, em vez de falhar o registro só por causa da data.
    """
    if not isinstance(date_raw, str):
        return today
    try:
        return date.fromisoformat(date_raw)
    except ValueError:
        return today


@dataclass
class RegisterExpenseViaBotInput:
    user_id: uuid.UUID
    raw_text: str


@dataclass
class ParsedExpense:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Resultado da extração via IA já com a categoria resolvida
    — build-context-12 §3.1. Não é uma transação ainda: a criação de
    fato só acontece depois que `HandleExpenseStateUseCase` também
    souber se é avulsa/parcelada/recorrente (§3.2), então este DTO só
    carrega o que já foi entendido, sem persistir nada.
    """

    amount: Decimal
    description: str
    date: date
    category: Category
    installment_total: int | None = None
    recurrence_frequency: RecurrenceFrequency | None = None
    amount_is_total: bool | None = None


class RegisterExpenseViaBotUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Extensão do módulo Transações para o Bot WhatsApp
    (build-context-07 §2.9) — extrai `amount`/categoria/data/descrição
    de um texto livre via IA (`ChatCompletionPort`, mesmo fallback
    Gemini→Grok do chat) e resolve a categoria contra as categorias do
    usuário. Só lida com texto: a transcrição de áudio acontece antes,
    em `HandleExpenseStateUseCase` (build-context-07 §2.9). Desde o
    build-context-12, não cria mais a transação diretamente (`execute`
    devolve um `ParsedExpense`) — `HandleExpenseStateUseCase` decide
    quando finalizar, depois de também perguntar parcelamento/recorrência.
    Registra o uso de IA (`RecordAiUsageUseCase`, build-context-10 §2.2,
    feature `bot_expense_parsing`) a cada chamada bem-sucedida — não
    passa por `CheckAiUsageLimitUseCase`, essa feature nunca bloqueia
    por limite de plano (só o Bot como um todo tem limite, contado à
    parte via `processed_bot_messages`, build-context-09 §2.6).
    """

    def __init__(
        self,
        category_repository: CategoryRepository,
        chat_completion_port: ChatCompletionPort,
        record_ai_usage_use_case: RecordAiUsageUseCase,
    ) -> None:
        self._category_repository = category_repository
        self._chat_completion_port = chat_completion_port
        self._record_ai_usage_use_case = record_ai_usage_use_case

    async def execute(self, input_data: RegisterExpenseViaBotInput) -> ParsedExpense:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Levanta `ExpenseParsingFailedError` quando a IA não
        devolve um JSON válido ou o `amount` extraído é ausente/inválido
        — `HandleExpenseStateUseCase` traduz isso na mensagem
        `expense.parse_failed`, sem persistir nada. Levanta
        `NoCategoryMatchError` (build-context-12 §3.1) quando a IA extrai
        valor/descrição/data mas devolve `category: null` — sinal
        deliberado de "nenhuma categoria da lista serve", diferente de um
        nome de categoria que só não bateu por acidente (esse caso
        continua caindo em "Outros" via `_resolve_category`). Também
        extrai `installment_total`/`recurrence_frequency` já mencionados
        na mensagem original, e `amount_is_total` pra desambiguar se o
        valor extraído é o total a dividir ou o valor de cada parcela —
        `HandleExpenseStateUseCase` usa esses três campos pra pular
        perguntas que a mensagem original já respondeu.
        """
        categories = await self._category_repository.list_visible_to(input_data.user_id)
        today = datetime.now(UTC).date()

        system_instruction = _build_system_instruction(categories, today)
        result = await self._chat_completion_port.complete(
            system_instruction,
            [ChatMessage(role=MessageRole.USER, content=input_data.raw_text)],
        )
        await self._record_ai_usage_use_case.execute(
            RecordAiUsageInput(
                user_id=input_data.user_id,
                feature=AiFeature.BOT_EXPENSE_PARSING,
                provider=result.provider,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
        )
        parsed = _parse_extraction(result.content)

        amount_raw = parsed.get("amount")
        if not isinstance(amount_raw, int | float) or amount_raw <= 0:
            raise ExpenseParsingFailedError("missing or invalid amount")

        description_raw = parsed.get("description")
        description = description_raw if isinstance(description_raw, str) and description_raw else input_data.raw_text
        expense_date = _resolve_date(parsed.get("date"), today)
        installment_total, recurrence_frequency = _resolve_installment_and_recurrence(parsed)
        amount_is_total = _resolve_amount_is_total(parsed) if installment_total is not None else None

        category_name = parsed.get("category")
        if category_name is None:
            raise NoCategoryMatchError(
                Decimal(str(amount_raw)),
                description,
                expense_date,
                installment_total=installment_total,
                recurrence_frequency=recurrence_frequency,
                amount_is_total=amount_is_total,
            )

        category = _resolve_category(category_name, categories)

        return ParsedExpense(
            amount=Decimal(str(amount_raw)),
            description=description,
            date=expense_date,
            category=category,
            installment_total=installment_total,
            recurrence_frequency=recurrence_frequency,
            amount_is_total=amount_is_total,
        )
