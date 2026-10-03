import base64
import logging
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from src.application.ai_usage.use_cases.record_ai_usage import (
    RecordAiUsageInput,
    RecordAiUsageUseCase,
)
from src.application.category.use_cases.check_category_duplicate import (
    CheckCategoryDuplicateUseCase,
)
from src.application.category.use_cases.create_category import (
    CreateCategoryInput,
    CreateCategoryUseCase,
)
from src.application.transaction.use_cases.create_transaction import (
    MAX_INSTALLMENTS,
    CreateTransactionInput,
    CreateTransactionUseCase,
    InstallmentInput,
    RecurrenceInput,
)
from src.application.transaction.use_cases.register_expense_via_bot import (
    RegisterExpenseViaBotInput,
    RegisterExpenseViaBotUseCase,
)
from src.application.whatsapp_bot.dtos import IncomingMessage
from src.domain.ai_usage.entities import AiFeature, AiProvider
from src.domain.category.repository import CategoryRepository
from src.domain.shared.value_objects import PublicId
from src.domain.transaction.exceptions import ExpenseParsingFailedError, NoCategoryMatchError
from src.domain.transaction.value_objects import Money, RecurrenceFrequency, TransactionType
from src.domain.user.entities import User
from src.domain.user.value_objects import Language
from src.domain.whatsapp_bot.entities import WhatsappSession
from src.domain.whatsapp_bot.ports import (
    AudioTranscriptionPort,
    MediaDecryptorPort,
    MessageCatalogPort,
)
from src.domain.whatsapp_bot.value_objects import BotMode

logger = logging.getLogger(__name__)

_DEFAULT_CATEGORY_COLOR = "#6b7280"
_DEFAULT_CATEGORY_ICON = "tag"
_AFFIRMATIVE_KEYWORDS = {"sim", "s", "yes", "y"}
_RECURRENCE_FREQUENCY_OPTIONS = {
    "1": RecurrenceFrequency.WEEKLY,
    "2": RecurrenceFrequency.MONTHLY,
    "3": RecurrenceFrequency.YEARLY,
}


def _format_decimal(value: Decimal, language: Language) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Formata um valor decimal na convenção do idioma do
    usuário (vírgula em pt-BR, ponto em en) — extraído de `_format_amount`
    pra também formatar um total ainda não convertido em `Money` (ex.: a
    pergunta de valor de parcela, build-context-12).
    """
    formatted = f"{value:.2f}"
    return formatted if language == Language.EN else formatted.replace(".", ",")


def _format_amount(amount: Money, language: Language) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Formata o valor da despesa na convenção decimal do
    idioma do usuário (vírgula em pt-BR, ponto em en) para a mensagem
    de confirmação (RN-10).
    """
    return _format_decimal(amount.to_decimal(), language)


def _serialize_draft(amount: Decimal, description: str, expense_date: date) -> dict[str, Any]:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Serializa o rascunho de despesa em aberto para
    `WhatsappSession.pending_action` (JSONB — build-context-12 §2), que
    não guarda `Decimal`/`date` nativamente.
    """
    return {"amount": str(amount), "description": description, "date": expense_date.isoformat()}


def _deserialize_draft(draft: dict[str, Any]) -> tuple[Decimal, str, date]:
    """
    Autor: Carlos Adriano
    Data: 2026-09-09
    Descrição: Reconstrói `amount`/`description`/`date` do rascunho
    persistido em `pending_action` (build-context-12 §2).
    """
    return Decimal(draft["amount"]), draft["description"], date.fromisoformat(draft["date"])


class HandleExpenseStateUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-09-10
    Descrição: Handler do modo Registrar (build-context-07 §2.8, com
    fluxo multi-turno do build-context-12) — texto direto ou transcrição
    de áudio convergem para o mesmo pipeline de parsing
    (`RegisterExpenseViaBotUseCase`), que já tenta extrair parcelamento/
    recorrência da própria mensagem original (`_proceed_after_category`
    pula perguntas que ela já respondeu, só pergunta o que ficou
    ambíguo — ex.: valor por parcela quando não dá pra saber se o número
    mencionado é o total ou já o valor de cada parcela). Quando
    `session.pending_action` já tem uma pergunta em aberto (categoria
    não reconhecida, dedup de nome, parcelamento/recorrência, valor da
    parcela, data de início), a mensagem recebida é interpretada como
    resposta a ela, em vez de uma nova despesa — ver
    `_handle_pending_action`. Permanece no modo `expense` em qualquer
    caso, para o usuário poder tentar de novo/continuar respondendo sem
    precisar reabrir o menu.
    """

    def __init__(
        self,
        register_expense_use_case: RegisterExpenseViaBotUseCase,
        create_transaction_use_case: CreateTransactionUseCase,
        create_category_use_case: CreateCategoryUseCase,
        check_category_duplicate_use_case: CheckCategoryDuplicateUseCase,
        category_repository: CategoryRepository,
        audio_transcription_port: AudioTranscriptionPort,
        media_decryptor: MediaDecryptorPort,
        message_catalog: MessageCatalogPort,
        record_ai_usage_use_case: RecordAiUsageUseCase,
    ) -> None:
        self._register_expense_use_case = register_expense_use_case
        self._create_transaction_use_case = create_transaction_use_case
        self._create_category_use_case = create_category_use_case
        self._check_category_duplicate_use_case = check_category_duplicate_use_case
        self._category_repository = category_repository
        self._audio_transcription_port = audio_transcription_port
        self._media_decryptor = media_decryptor
        self._message_catalog = message_catalog
        self._record_ai_usage_use_case = record_ai_usage_use_case

    async def execute(self, user: User, session: WhatsappSession, message: IncomingMessage) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Ponto de entrada do modo Registrar. Delega pra
        `_handle_pending_action` quando existe uma pergunta em aberto
        (build-context-12); senão, trata a mensagem como uma despesa
        nova — resolve o texto (`_resolve_text`), parseia via IA
        (`RegisterExpenseViaBotUseCase`) e, com a categoria já resolvida,
        abre a pergunta de parcelamento/recorrência em vez de criar a
        transação na hora (§3.2 do build-context-12).
        """
        session.transition_to(BotMode.EXPENSE)

        if session.pending_action is not None:
            return await self._handle_pending_action(user, session, message)

        try:
            raw_text = await self._resolve_text(user, message)
        except Exception:
            logger.exception("Failed to download/transcribe WhatsApp audio (user_id=%s)", user.id)
            return self._message_catalog.get_message("expense.parse_failed", user.language)

        try:
            parsed = await self._register_expense_use_case.execute(
                RegisterExpenseViaBotInput(user_id=user.id, raw_text=raw_text)
            )
        except NoCategoryMatchError as exc:
            return await self._start_category_choice(
                session,
                user,
                exc.amount,
                exc.description,
                exc.expense_date,
                installment_total=exc.installment_total,
                recurrence_frequency=exc.recurrence_frequency,
                amount_is_total=exc.amount_is_total,
            )
        except ExpenseParsingFailedError:
            return self._message_catalog.get_message("expense.parse_failed", user.language)

        return self._proceed_after_category(
            session,
            user,
            parsed.amount,
            parsed.description,
            parsed.date,
            str(parsed.category.public_id),
            parsed.category.name,
            parsed.installment_total,
            parsed.recurrence_frequency,
            parsed.amount_is_total,
        )

    async def _resolve_text(self, user: User, message: IncomingMessage) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Devolve o texto a ser parseado — direto da mensagem
        (`kind="text"`) ou via transcrição (`kind="audio"`). Para áudio,
        usa `audio_base64` quando o webhook já veio com ele embutido; na
        prática isso raramente acontece (achado do projeto irmão,
        DIARIO.md 2026-08-15 — a Evolution nem sempre honra o embed de
        base64 mesmo configurada para isso), então o caminho comum é
        baixar e decriptar `audio_media_url`/`audio_media_key` direto do
        CDN do WhatsApp (`MediaDecryptorPort`), sem nenhuma chamada à
        Evolution API — o endpoint de mídia dela se mostrou não confiável
        entre versões. Registra o uso de IA (`RecordAiUsageUseCase`,
        build-context-10 §2.2, feature `bot_audio_transcription`) a cada
        transcrição bem-sucedida — nunca passa por `CheckAiUsageLimitUseCase`,
        essa feature não bloqueia por limite de plano.
        """
        if message.kind == "text":
            return message.text or ""

        audio_base64 = message.audio_base64
        if not audio_base64:
            if not message.audio_media_url or message.audio_media_key is None:
                raise RuntimeError("audio message without inline base64 or url/mediaKey")
            audio_bytes = await self._media_decryptor.download_and_decrypt_audio(
                message.audio_media_url, message.audio_media_key
            )
            if audio_bytes is None:
                raise RuntimeError("failed to download/decrypt WhatsApp audio from CDN")
            audio_base64 = base64.b64encode(audio_bytes).decode()

        transcription = await self._audio_transcription_port.transcribe(
            audio_base64, message.audio_mime_type
        )
        await self._record_ai_usage_use_case.execute(
            RecordAiUsageInput(
                user_id=user.id,
                feature=AiFeature.BOT_AUDIO_TRANSCRIPTION,
                provider=AiProvider.GEMINI,
                model=transcription.model,
                input_tokens=transcription.input_tokens,
                output_tokens=transcription.output_tokens,
            )
        )
        return transcription.text

    async def _handle_pending_action(
        self, user: User, session: WhatsappSession, message: IncomingMessage
    ) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Despacha pra o handler do `step` em aberto
        (build-context-12 §2). Áudio nunca é uma resposta válida pra
        essas perguntas (são sempre escolhas curtas por número/texto) —
        pede pra responder em texto em vez de tentar transcrever.
        """
        assert session.pending_action is not None
        if message.kind != "text":
            return self._message_catalog.get_message("expense.reply_with_text", user.language)

        text = (message.text or "").strip()
        step = session.pending_action.get("step")

        if step == "awaiting_category_choice":
            return await self._handle_category_choice(user, session, text)
        if step == "awaiting_category_dedup_confirm":
            return await self._handle_category_dedup_confirm(user, session, text)
        if step == "awaiting_installment_choice":
            return await self._handle_installment_choice(user, session, text)
        if step == "awaiting_installment_amount":
            return await self._handle_installment_amount(user, session, text)
        if step == "awaiting_installment_count":
            return await self._handle_installment_count(user, session, text)
        if step == "awaiting_recurrence_frequency":
            return await self._handle_recurrence_frequency(user, session, text)
        if step == "awaiting_start_date_confirm":
            return await self._handle_start_date_confirm(user, session, text)

        # step desconhecido (não deveria acontecer em produção) — descarta o rascunho em vez de travar o usuário.
        session.pending_action = None
        return self._message_catalog.get_message("expense.parse_failed", user.language)

    async def _start_category_choice(
        self,
        session: WhatsappSession,
        user: User,
        amount: Decimal,
        description: str,
        expense_date: date,
        installment_total: int | None = None,
        recurrence_frequency: RecurrenceFrequency | None = None,
        amount_is_total: bool | None = None,
    ) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Abre a pergunta de categoria (build-context-12 §3.1
        passo 1) — lista globais + privadas do usuário, numeradas.
        `installment_total`/`recurrence_frequency`/`amount_is_total`
        (2026-09-10) guardam parcelamento/recorrência já detectados na
        mensagem original, mesmo quando a categoria ainda não foi
        resolvida — `_proceed_after_category` os lê de volta do rascunho
        assim que a categoria for escolhida, pra não reperguntar o que
        o usuário já disse de cara.
        """
        categories = await self._category_repository.list_visible_to(user.id)
        options = [{"public_id": str(category.public_id), "name": category.name} for category in categories]
        draft = _serialize_draft(amount, description, expense_date)
        if installment_total is not None:
            draft["installment_total"] = installment_total
        if recurrence_frequency is not None:
            draft["recurrence_frequency"] = recurrence_frequency.value
        if amount_is_total is not None:
            draft["amount_is_total"] = amount_is_total
        session.pending_action = {"step": "awaiting_category_choice", "draft": draft, "options": options}
        listing = "\n".join(f"{index + 1}) {option['name']}" for index, option in enumerate(options))
        return self._message_catalog.get_message("expense.choose_category", user.language, options=listing)

    async def _handle_category_choice(self, user: User, session: WhatsappSession, text: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Interpreta a resposta à pergunta de categoria
        (build-context-12 §3.1 passos 2-3) — um número da lista resolve
        direto; qualquer outro texto é tratado como nome de categoria
        nova, checado por duplicata semântica antes de criar.
        """
        pending = session.pending_action
        assert pending is not None
        options: list[dict[str, str]] = pending["options"]
        draft = pending["draft"]
        amount, description, expense_date = _deserialize_draft(draft)
        installment_total, recurrence_frequency, amount_is_total = self._extract_pending_schedule(draft)

        chosen = self._parse_option_choice(text, options)
        if chosen is not None:
            session.pending_action = None
            return self._proceed_after_category(
                session, user, amount, description, expense_date, chosen["public_id"], chosen["name"],
                installment_total, recurrence_frequency, amount_is_total,
            )

        match = await self._check_category_duplicate_use_case.execute(user.id, text)
        if match is not None:
            similar_category = await self._category_repository.get_by_id(match.source_id)
            if similar_category is not None:
                dedup_draft = dict(draft)
                session.pending_action = {
                    "step": "awaiting_category_dedup_confirm",
                    "draft": dedup_draft,
                    "typed_name": text,
                    "similar_public_id": str(similar_category.public_id),
                    "similar_name": similar_category.name,
                }
                return self._message_catalog.get_message(
                    "expense.category_dedup_confirm", user.language, existing=similar_category.name
                )
            # Embedding órfão (categoria já excluída, job de remoção ainda não rodou) — segue como
            # se não tivesse achado nada parecido, cria a categoria nova normalmente abaixo.

        category = await self._create_category_use_case.execute(
            CreateCategoryInput(
                user_id=user.id, name=text, color=_DEFAULT_CATEGORY_COLOR, icon=_DEFAULT_CATEGORY_ICON
            )
        )
        session.pending_action = None
        return self._proceed_after_category(
            session, user, amount, description, expense_date, str(category.public_id), category.name,
            installment_total, recurrence_frequency, amount_is_total,
        )

    async def _handle_category_dedup_confirm(self, user: User, session: WhatsappSession, text: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Interpreta a confirmação de duplicata semântica
        (build-context-12 §3.1 passo 3) — resposta afirmativa usa a
        categoria já existente; qualquer outra reafirma que o usuário
        quer mesmo uma categoria nova, com o nome originalmente digitado.
        """
        pending = session.pending_action
        assert pending is not None
        draft = pending["draft"]
        amount, description, expense_date = _deserialize_draft(draft)
        installment_total, recurrence_frequency, amount_is_total = self._extract_pending_schedule(draft)

        if text.strip().lower() in _AFFIRMATIVE_KEYWORDS:
            session.pending_action = None
            return self._proceed_after_category(
                session, user, amount, description, expense_date,
                pending["similar_public_id"], pending["similar_name"],
                installment_total, recurrence_frequency, amount_is_total,
            )

        category = await self._create_category_use_case.execute(
            CreateCategoryInput(
                user_id=user.id,
                name=pending["typed_name"],
                color=_DEFAULT_CATEGORY_COLOR,
                icon=_DEFAULT_CATEGORY_ICON,
            )
        )
        session.pending_action = None
        return self._proceed_after_category(
            session, user, amount, description, expense_date, str(category.public_id), category.name,
            installment_total, recurrence_frequency, amount_is_total,
        )

    @staticmethod
    def _extract_pending_schedule(
        draft: dict[str, Any],
    ) -> tuple[int | None, RecurrenceFrequency | None, bool | None]:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Lê de volta `installment_total`/`recurrence_frequency`/
        `amount_is_total` que `_start_category_choice` guardou no
        rascunho antes de perguntar a categoria (build-context-12) —
        ponte entre "o que a mensagem original já disse" e o momento em
        que a categoria finalmente é resolvida.
        """
        installment_total = draft.get("installment_total")
        recurrence_raw = draft.get("recurrence_frequency")
        recurrence_frequency = RecurrenceFrequency(recurrence_raw) if recurrence_raw is not None else None
        amount_is_total = draft.get("amount_is_total")
        return installment_total, recurrence_frequency, amount_is_total

    def _proceed_after_category(
        self,
        session: WhatsappSession,
        user: User,
        amount: Decimal,
        description: str,
        expense_date: date,
        category_public_id: str,
        category_name: str,
        installment_total: int | None,
        recurrence_frequency: RecurrenceFrequency | None,
        amount_is_total: bool | None,
    ) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Decide o próximo passo já com a categoria resolvida
        (build-context-12 §3.2, revisado em 2026-09-10 — achado real do
        usuário: "gastei 600 dividido em 10 vezes" forçava reperguntar
        parcelamento que a mensagem original já respondia). Parcelamento
        detectado na mensagem original com valor ambíguo (total ou por
        parcela) pergunta o valor da parcela antes de tudo; detectado com
        valor claro, ou recorrência detectada, pula direto pra
        confirmação de data; nada detectado cai no menu de sempre
        (`_start_installment_choice`).
        """
        if installment_total is not None:
            if amount_is_total is None:
                return self._start_installment_amount_clarify(
                    session, user, amount, description, expense_date,
                    category_public_id, category_name, installment_total,
                )
            final_amount = (
                (amount / installment_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if amount_is_total
                else amount
            )
            draft = _serialize_draft(final_amount, description, expense_date)
            draft["category_public_id"] = category_public_id
            draft["category_name"] = category_name
            draft["installment_total"] = installment_total
            return self._start_date_confirm(session, user, draft)

        if recurrence_frequency is not None:
            draft = _serialize_draft(amount, description, expense_date)
            draft["category_public_id"] = category_public_id
            draft["category_name"] = category_name
            draft["recurrence_frequency"] = recurrence_frequency.value
            return self._start_date_confirm(session, user, draft)

        return self._start_installment_choice(
            session, user, amount, description, expense_date, category_public_id, category_name
        )

    def _start_installment_amount_clarify(
        self,
        session: WhatsappSession,
        user: User,
        amount: Decimal,
        description: str,
        expense_date: date,
        category_public_id: str,
        category_name: str,
        installment_total: int,
    ) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Pergunta o valor de cada parcela quando a mensagem
        original menciona parcelamento mas não deixa claro se o valor é
        o total a dividir ou já o valor por parcela — pedido explícito
        do usuário: "caso não consiga entender, perguntar o valor por
        parcela" em vez de arriscar uma divisão errada. O valor mostrado
        (`amount`) é o número bruto mencionado, só como referência.
        """
        draft = _serialize_draft(amount, description, expense_date)
        draft["category_public_id"] = category_public_id
        draft["category_name"] = category_name
        draft["installment_total"] = installment_total
        session.pending_action = {"step": "awaiting_installment_amount", "draft": draft}
        return self._message_catalog.get_message(
            "expense.installment_amount_prompt",
            user.language,
            total=_format_decimal(amount, user.language),
            count=installment_total,
        )

    async def _handle_installment_amount(self, user: User, session: WhatsappSession, text: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Interpreta o valor da parcela digitado
        (build-context-12 §3.2) — sobrescreve `amount` no rascunho com o
        valor informado (não o total mencionado antes) e segue pra
        confirmação de data.
        """
        pending = session.pending_action
        assert pending is not None
        draft = pending["draft"]

        typed_amount = self._parse_typed_amount(text)
        if typed_amount is None:
            return self._message_catalog.get_message("expense.installment_amount_invalid", user.language)

        draft["amount"] = str(typed_amount)
        return self._start_date_confirm(session, user, draft)

    @staticmethod
    def _parse_typed_amount(text: str) -> Decimal | None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Aceita um número com vírgula ou ponto decimal,
        opcionalmente prefixado por "R$" (ex.: "R$ 60", "60,00", "60.5")
        — `None` pra texto que não é um valor positivo válido.
        """
        cleaned = text.strip().upper().replace("R$", "").replace(" ", "").replace(",", ".")
        try:
            value = Decimal(cleaned)
        except InvalidOperation:
            return None
        return value if value > 0 else None

    def _start_installment_choice(
        self,
        session: WhatsappSession,
        user: User,
        amount: Decimal,
        description: str,
        expense_date: date,
        category_public_id: str,
        category_name: str,
    ) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Abre a pergunta de parcelamento/recorrência
        (build-context-12 §3.2) — quando a mensagem original não deixou
        parcelamento/recorrência claros (`_proceed_after_category`),
        pergunta manualmente via menu 1/2/3.
        """
        draft = _serialize_draft(amount, description, expense_date)
        draft["category_public_id"] = category_public_id
        draft["category_name"] = category_name
        session.pending_action = {"step": "awaiting_installment_choice", "draft": draft}
        return self._message_catalog.get_message("expense.installment_choice", user.language)

    async def _handle_installment_choice(self, user: User, session: WhatsappSession, text: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Interpreta a escolha de parcelamento/recorrência
        (build-context-12 §3.2) — opção 1 finaliza direto (avulsa),
        2 e 3 abrem uma sub-pergunta antes de finalizar.
        """
        pending = session.pending_action
        assert pending is not None
        draft = pending["draft"]

        if text == "1":
            return await self._finalize(user, session, draft, installment=None, recurrence=None)
        if text == "2":
            session.pending_action = {"step": "awaiting_installment_count", "draft": draft}
            return self._message_catalog.get_message(
                "expense.installment_count_prompt", user.language, max=MAX_INSTALLMENTS
            )
        if text == "3":
            session.pending_action = {"step": "awaiting_recurrence_frequency", "draft": draft}
            return self._message_catalog.get_message("expense.recurrence_frequency_prompt", user.language)

        return self._message_catalog.get_message("expense.installment_choice_invalid", user.language)

    async def _handle_installment_count(self, user: User, session: WhatsappSession, text: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Valida o número de parcelas (2 a `MAX_INSTALLMENTS`,
        mesmo teto de `CreateTransactionUseCase` — build-context-12 §3.2)
        e abre a confirmação de data de início (§3.2, item pedido pelo
        usuário em 2026-09-09) antes de finalizar.
        """
        pending = session.pending_action
        assert pending is not None
        draft = pending["draft"]

        if not text.isdigit() or not (2 <= int(text) <= MAX_INSTALLMENTS):
            return self._message_catalog.get_message(
                "expense.installment_count_invalid", user.language, max=MAX_INSTALLMENTS
            )

        draft["installment_total"] = int(text)
        return self._start_date_confirm(session, user, draft)

    async def _handle_recurrence_frequency(self, user: User, session: WhatsappSession, text: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Valida a frequência de recorrência escolhida
        (semanal/mensal/anual — as 3 que `RecurrenceFrequency` já
        suporta, build-context-12 §3.2) e abre a confirmação de data de
        início antes de finalizar. Recorrência via bot nunca tem
        `end_date` — mesmo padrão "sem fim conhecido" que o formulário
        web já permite deixar em branco.
        """
        pending = session.pending_action
        assert pending is not None
        draft = pending["draft"]

        frequency = _RECURRENCE_FREQUENCY_OPTIONS.get(text)
        if frequency is None:
            return self._message_catalog.get_message("expense.recurrence_frequency_invalid", user.language)

        draft["recurrence_frequency"] = frequency.value
        return self._start_date_confirm(session, user, draft)

    def _start_date_confirm(self, session: WhatsappSession, user: User, draft: dict[str, Any]) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Abre a confirmação de data de início — só pra
        parcelado/recorrente (build-context-12 §3.2), nunca pra avulsa,
        que finaliza direto (a data da 1ª parcela/ocorrência importa pro
        cronograma inteiro; numa despesa avulsa não há cronograma).
        Mostra a data já extraída da mensagem original (ou "hoje", se
        nada foi mencionado) e permite confirmar ou corrigir.
        """
        session.pending_action = {"step": "awaiting_start_date_confirm", "draft": draft}
        _, _, expense_date = _deserialize_draft(draft)
        return self._message_catalog.get_message(
            "expense.start_date_confirm", user.language, date=expense_date.strftime("%d/%m/%Y")
        )

    async def _handle_start_date_confirm(self, user: User, session: WhatsappSession, text: str) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Interpreta a resposta à confirmação de data
        (build-context-12 §3.2) — afirmativa mantém a data já no
        rascunho; um texto `DD/MM` ou `DD/MM/YYYY` a substitui. Só então
        reconstrói `InstallmentInput`/`RecurrenceInput` a partir do que
        foi salvo no rascunho pelos passos anteriores e finaliza.
        """
        pending = session.pending_action
        assert pending is not None
        draft = pending["draft"]

        if text.strip().lower() not in _AFFIRMATIVE_KEYWORDS:
            typed_date = self._parse_typed_date(text)
            if typed_date is None:
                return self._message_catalog.get_message("expense.start_date_invalid", user.language)
            draft["date"] = typed_date.isoformat()

        installment = (
            InstallmentInput(total=draft["installment_total"]) if "installment_total" in draft else None
        )
        recurrence = (
            RecurrenceInput(frequency=RecurrenceFrequency(draft["recurrence_frequency"]), end_date=None)
            if "recurrence_frequency" in draft
            else None
        )
        return await self._finalize(user, session, draft, installment=installment, recurrence=recurrence)

    @staticmethod
    def _parse_typed_date(text: str) -> date | None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Aceita `DD/MM` (assume o ano corrente) ou
        `DD/MM/YYYY` — formato único independente do idioma do usuário
        (o parser é o mesmo, só a mensagem que pede a data é traduzida).
        `None` para qualquer texto que não bate nesses formatos ou não é
        uma data real (ex.: "31/02").
        """
        parts = text.strip().split("/")
        try:
            if len(parts) == 2:
                day, month = int(parts[0]), int(parts[1])
                return date(datetime.now(UTC).year, month, day)
            if len(parts) == 3:
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                return date(year, month, day)
        except ValueError:
            return None
        return None

    async def _finalize(
        self,
        user: User,
        session: WhatsappSession,
        draft: dict[str, Any],
        installment: InstallmentInput | None,
        recurrence: RecurrenceInput | None,
    ) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Cria a transação de fato (build-context-12 §3.2) —
        único ponto que chama `CreateTransactionUseCase` neste fluxo,
        reaproveitando o mesmo caminho de domínio (avulsa/parcelada/
        recorrente) que o formulário web já usa. Limpa `pending_action`
        ao final, sucesso ou não — uma falha aqui não deveria travar o
        usuário num rascunho preso.
        """
        amount, description, expense_date = _deserialize_draft(draft)
        session.pending_action = None

        result = await self._create_transaction_use_case.execute(
            CreateTransactionInput(
                user_id=user.id,
                category_public_id=PublicId(draft["category_public_id"]),
                type=TransactionType.EXPENSE,
                amount=amount,
                description=description,
                date=expense_date,
                installment=installment,
                recurrence=recurrence,
            )
        )
        return self._message_catalog.get_message(
            "expense.confirmation",
            user.language,
            amount=_format_amount(result.transaction.amount, user.language),
            category=result.category.name,
            date=result.transaction.date.isoformat(),
        )

    @staticmethod
    def _parse_option_choice(text: str, options: list[dict[str, str]]) -> dict[str, str] | None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-09
        Descrição: Resolve um número digitado (1-based, como exibido na
        listagem) pra uma das opções — `None` quando o texto não é um
        número válido dentro do intervalo, sinal de que deve ser tratado
        como nome de categoria nova (build-context-12 §3.1 passo 2).
        """
        if not text.isdigit():
            return None
        index = int(text) - 1
        if 0 <= index < len(options):
            return options[index]
        return None
