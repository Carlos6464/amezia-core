import random
import uuid
import zlib
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ai_usage.use_cases.check_ai_usage_limit import CheckAiUsageLimitUseCase
from src.application.ai_usage.use_cases.record_ai_usage import RecordAiUsageUseCase
from src.application.category.use_cases.check_category_duplicate import (
    CheckCategoryDuplicateUseCase,
)
from src.application.category.use_cases.create_category import (
    CreateCategoryInput,
    CreateCategoryUseCase,
)
from src.application.conversation.use_cases.create_conversation import CreateConversationUseCase
from src.application.conversation.use_cases.generate_ai_response import GenerateAiResponseUseCase
from src.application.conversation.use_cases.get_or_create_active_conversation import (
    GetOrCreateActiveConversationUseCase,
)
from src.application.conversation.use_cases.summarize_old_messages import (
    SummarizeOldMessagesUseCase,
)
from src.application.embedding.use_cases.index_category_embedding import (
    IndexCategoryEmbeddingUseCase,
)
from src.application.embedding.use_cases.index_conversation_message_embedding import (
    IndexConversationMessageEmbeddingUseCase,
)
from src.application.embedding.use_cases.search_relevant_context import (
    SearchRelevantContextUseCase,
)
from src.application.feedback.use_cases.submit_feedback import SubmitFeedbackUseCase
from src.application.reports.use_cases.get_financial_summary import GetFinancialSummaryUseCase
from src.application.transaction.use_cases.create_recurring_transaction import (
    CreateRecurringTransactionUseCase,
)
from src.application.transaction.use_cases.create_transaction import CreateTransactionUseCase
from src.application.transaction.use_cases.register_expense_via_bot import (
    RegisterExpenseViaBotUseCase,
)
from src.application.whatsapp_bot.use_cases.handle_chat_state import HandleChatStateUseCase
from src.application.whatsapp_bot.use_cases.handle_expense_state import HandleExpenseStateUseCase
from src.application.whatsapp_bot.use_cases.handle_feedback_state import HandleFeedbackStateUseCase
from src.application.whatsapp_bot.use_cases.handle_menu_state import HandleMenuStateUseCase
from src.application.whatsapp_bot.use_cases.handle_report_state import HandleReportStateUseCase
from src.application.whatsapp_bot.use_cases.process_incoming_whatsapp_message import (
    ProcessIncomingWhatsappMessageInput,
    ProcessIncomingWhatsappMessageUseCase,
)
from src.application.whatsapp_bot.use_cases.reset_to_menu import ResetToMenuUseCase
from src.domain.conversation.ports import ChatCompletionResult
from src.domain.conversation.value_objects import AiProvider
from src.domain.shared.value_objects import PublicId
from src.domain.transaction.repository import TransactionFilters
from src.domain.whatsapp_bot.ports import TranscriptionResult
from src.domain.whatsapp_bot.value_objects import BotMode
from src.infrastructure.database.models.evolution_instance import (
    EvolutionInstance as EvolutionInstanceModel,
)
from src.infrastructure.database.models.user import User as UserModel
from src.infrastructure.database.repositories.ai_usage_repository import (
    SqlAlchemyAiUsageRepository,
)
from src.infrastructure.database.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from src.infrastructure.database.repositories.conversation_repository import (
    SqlAlchemyConversationRepository,
)
from src.infrastructure.database.repositories.embedding_repository import (
    SqlAlchemyEmbeddingRepository,
)
from src.infrastructure.database.repositories.feedback_repository import (
    SqlAlchemyFeedbackRepository,
)
from src.infrastructure.database.repositories.recurrence_rule_repository import (
    SqlAlchemyRecurrenceRuleRepository,
)
from src.infrastructure.database.repositories.sqlalchemy_evolution_instance_repository import (
    SqlAlchemyEvolutionInstanceRepository,
)
from src.infrastructure.database.repositories.sqlalchemy_reports_repository import (
    SqlAlchemyReportsRepository,
)
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemyPlanLimitsRepository,
    SqlAlchemySubscriptionRepository,
)
from src.infrastructure.database.repositories.transaction_repository import (
    SqlAlchemyTransactionRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.repositories.whatsapp_bot_repository import (
    SqlAlchemyProcessedBotMessageRepository,
    SqlAlchemyWhatsappSessionRepository,
)
from src.infrastructure.security.jwt_service import JwtService
from src.infrastructure.security.phone_hasher import hash_phone
from src.infrastructure.whatsapp.messages import MessageCatalog

pytestmark = pytest.mark.asyncio


class _FakeChatCompletionPort:
    """Substituto de ChatCompletionPort — devolve `response` fixo, sem bater em Gemini/Grok."""

    def __init__(self, response: str = "resposta da IA") -> None:
        self.response = response

    async def complete(self, system_instruction: str, messages: list) -> ChatCompletionResult:
        return ChatCompletionResult(
            content=self.response,
            provider=AiProvider.GEMINI,
            model="gemini-2.5-flash",
            input_tokens=10,
            output_tokens=5,
        )


class _FakeEmbeddingGenerator:
    async def generate(self, text: str) -> list[float]:
        return [0.0] * 768


class _FakeSemanticEmbeddingGenerator:
    """
    Vetor determinístico por hash do texto normalizado — textos iguais (mesmo hash) geram o
    mesmo vetor (similaridade de cosseno 1.0), textos diferentes geram vetores de alta dimensão
    ~ortogonais entre si (similaridade ~0), sem bater na API real do Gemini. Usado nos testes de
    duplicata semântica de categoria (build-context-12), onde `_FakeEmbeddingGenerator` acima
    (vetor zero fixo) não serve — cosine_distance de dois vetores zero é indefinida.
    """

    async def generate(self, text: str) -> list[float]:
        seed = zlib.crc32(text.strip().lower().encode())
        rng = random.Random(seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(768)]


class _FakeAudioTranscriptionPort:
    def __init__(self, transcription: str = "gastei 50 no mercado") -> None:
        self.transcription = transcription

    async def transcribe(self, audio_base64: str, mime_type: str) -> TranscriptionResult:
        return TranscriptionResult(
            text=self.transcription, model="gemini-2.5-flash", input_tokens=8, output_tokens=4
        )


class _FakeWhatsappGateway:
    def __init__(self, *, raise_on_send: bool = False) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.raise_on_send = raise_on_send

    async def send_text(self, name: str, phone: str, text: str) -> None:
        if self.raise_on_send:
            raise RuntimeError("Evolution API unavailable (simulated)")
        self.sent.append((name, phone, text))


class _FakeMediaDecryptor:
    """Substituto de MediaDecryptorPort — não bate no CDN real do WhatsApp."""

    def __init__(self, audio_bytes: bytes | None = b"fake-audio-bytes") -> None:
        self.audio_bytes = audio_bytes
        self.calls: list[tuple[str, object]] = []

    async def download_and_decrypt_audio(self, url: str, media_key: object) -> bytes | None:
        self.calls.append((url, media_key))
        return self.audio_bytes


def _make_payload(
    message_id: str,
    remote_phone: str,
    *,
    text: str | None = None,
    from_me: bool = False,
    is_group: bool = False,
    audio: bool = False,
    audio_base64: str | None = None,
) -> dict[str, Any]:
    """Monta o payload bruto de um evento `messages.upsert` (formato Baileys)."""
    suffix = "@g.us" if is_group else "@s.whatsapp.net"
    message: dict[str, Any] = {}
    if audio:
        message["audioMessage"] = {
            "mimetype": "audio/ogg; codecs=opus",
            "url": "https://mmg.whatsapp.net/fake-media-path",
            "mediaKey": "ZmFrZS1tZWRpYS1rZXk=",
        }
        if audio_base64 is not None:
            message["audioMessage"]["base64"] = audio_base64
    elif text is not None:
        message["conversation"] = text

    return {
        "event": "messages.upsert",
        "instance": "test-instance",
        "data": {
            "key": {"remoteJid": f"{remote_phone}{suffix}", "fromMe": from_me, "id": message_id},
            "message": message,
            "messageTimestamp": 1754247600,
        },
    }


async def _make_linked_user(db_session: AsyncSession, phone: str) -> UserModel:
    user_id = uuid.uuid4()
    model = UserModel(
        id=user_id,
        name="Bot User",
        email=f"bot-user-{user_id.hex[:12]}@example.com",
        password_hash="not-a-real-hash",
        role="user",
        language="pt-BR",
        phone_hash=hash_phone(phone),
    )
    db_session.add(model)
    await db_session.flush()
    return model


async def _make_evolution_instance(db_session: AsyncSession) -> EvolutionInstanceModel:
    """
    `is_active` fica no default (`False`) de propósito — o orquestrador do
    bot resolve a instância direto por `instance_id`, nunca por
    `get_active()`, então nada aqui depende disso. Definir `True` colidiria
    com `ux_evolution_instances_single_active` sempre que já existir uma
    instância ativa de verdade no banco (dev compartilhado, sem banco de
    teste separado — mesma classe de problema já visto em
    `test_admin_evolution.py`, 2026-08-16).
    """
    model = EvolutionInstanceModel(
        public_id=str(PublicId.generate()),
        name=f"test-instance-{uuid.uuid4().hex[:8]}",
        webhook_url="https://api.amezia.app/api/v1/webhook/evolution",
        webhook_secret="test-webhook-secret",
        status="connected",
    )
    db_session.add(model)
    await db_session.flush()
    return model


def _build_use_case(
    db_session: AsyncSession,
    *,
    chat_completion_port: _FakeChatCompletionPort,
    audio_transcription_port: _FakeAudioTranscriptionPort,
    whatsapp_gateway: _FakeWhatsappGateway,
    media_decryptor: _FakeMediaDecryptor | None = None,
    embedding_generator: object | None = None,
) -> ProcessIncomingWhatsappMessageUseCase:
    """
    Monta o mesmo grafo de dependências de `infrastructure/queue/jobs/whatsapp_jobs.py`,
    trocando só as portas de IA/Evolution por fakes — repositórios reais contra `db_session`.
    `embedding_generator` é `_FakeEmbeddingGenerator` (vetor zero) por padrão — os testes de
    duplicata semântica de categoria (build-context-12) passam `_FakeSemanticEmbeddingGenerator`.
    """
    conversation_repository = SqlAlchemyConversationRepository(db_session)
    embedding_repository = SqlAlchemyEmbeddingRepository(db_session)
    embedding_generator = embedding_generator or _FakeEmbeddingGenerator()
    category_repository = SqlAlchemyCategoryRepository(db_session)
    transaction_repository = SqlAlchemyTransactionRepository(db_session)
    message_catalog = MessageCatalog()
    ai_usage_repository = SqlAlchemyAiUsageRepository(db_session)
    record_ai_usage_use_case = RecordAiUsageUseCase(ai_usage_repository)
    check_ai_usage_limit_use_case = CheckAiUsageLimitUseCase(
        SqlAlchemySubscriptionRepository(db_session),
        SqlAlchemyPlanLimitsRepository(db_session),
        ai_usage_repository,
    )

    create_transaction_use_case = CreateTransactionUseCase(
        transaction_repository,
        category_repository,
        CreateRecurringTransactionUseCase(
            transaction_repository, SqlAlchemyRecurrenceRuleRepository(db_session)
        ),
        _NoopJobEnqueuer(),
    )

    handle_report_state_use_case = HandleReportStateUseCase(
        get_financial_summary_use_case=GetFinancialSummaryUseCase(
            SqlAlchemyReportsRepository(db_session)
        ),
        message_catalog=message_catalog,
        jwt_service=JwtService(),
    )

    return ProcessIncomingWhatsappMessageUseCase(
        processed_bot_message_repository=SqlAlchemyProcessedBotMessageRepository(db_session),
        whatsapp_session_repository=SqlAlchemyWhatsappSessionRepository(db_session),
        user_repository=SqlAlchemyUserRepository(db_session),
        evolution_instance_repository=SqlAlchemyEvolutionInstanceRepository(db_session),
        whatsapp_gateway=whatsapp_gateway,
        phone_hasher=_PassthroughPhoneHasher(),
        message_catalog=message_catalog,
        reset_to_menu_use_case=ResetToMenuUseCase(message_catalog),
        handle_menu_state_use_case=HandleMenuStateUseCase(message_catalog, handle_report_state_use_case),
        handle_expense_state_use_case=HandleExpenseStateUseCase(
            register_expense_use_case=RegisterExpenseViaBotUseCase(
                category_repository, chat_completion_port, record_ai_usage_use_case
            ),
            create_transaction_use_case=create_transaction_use_case,
            create_category_use_case=CreateCategoryUseCase(category_repository, _NoopJobEnqueuer()),
            check_category_duplicate_use_case=CheckCategoryDuplicateUseCase(
                embedding_repository, embedding_generator, threshold=0.85
            ),
            category_repository=category_repository,
            audio_transcription_port=audio_transcription_port,
            media_decryptor=media_decryptor or _FakeMediaDecryptor(),
            message_catalog=message_catalog,
            record_ai_usage_use_case=record_ai_usage_use_case,
        ),
        handle_chat_state_use_case=HandleChatStateUseCase(
            conversation_repository=conversation_repository,
            get_or_create_active_conversation_use_case=GetOrCreateActiveConversationUseCase(
                conversation_repository, CreateConversationUseCase(conversation_repository), 24
            ),
            generate_ai_response_use_case=GenerateAiResponseUseCase(
                conversation_repository=conversation_repository,
                user_repository=SqlAlchemyUserRepository(db_session),
                transaction_repository=transaction_repository,
                chat_completion_port=chat_completion_port,
                search_relevant_context_use_case=SearchRelevantContextUseCase(
                    embedding_repository, embedding_generator, pool_size=300, threshold=0.72, top_k=4
                ),
                summarize_old_messages_use_case=SummarizeOldMessagesUseCase(
                    conversation_repository, chat_completion_port
                ),
                index_conversation_message_embedding_use_case=(
                    IndexConversationMessageEmbeddingUseCase(embedding_repository, embedding_generator)
                ),
                summary_threshold=20,
                check_ai_usage_limit_use_case=check_ai_usage_limit_use_case,
                record_ai_usage_use_case=record_ai_usage_use_case,
            ),
            message_catalog=message_catalog,
        ),
        handle_report_state_use_case=handle_report_state_use_case,
        handle_feedback_state_use_case=HandleFeedbackStateUseCase(
            submit_feedback_use_case=SubmitFeedbackUseCase(SqlAlchemyFeedbackRepository(db_session)),
            message_catalog=message_catalog,
        ),
        subscription_repository=SqlAlchemySubscriptionRepository(db_session),
        plan_limits_repository=SqlAlchemyPlanLimitsRepository(db_session),
    )


class _NoopJobEnqueuer:
    async def enqueue_job(self, function: str, *args: object) -> None:
        return None


class _PassthroughPhoneHasher:
    """`hash_phone()` real (a mesma função usada por `_make_linked_user`), sem indireção extra."""

    def hash(self, phone: str) -> str:
        return hash_phone(phone)


@pytest.fixture
def gateway() -> _FakeWhatsappGateway:
    return _FakeWhatsappGateway()


async def test_duplicate_message_does_not_send_a_second_reply_or_transaction(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """RN-04: reentrega do mesmo `whatsapp_message_id` é ignorada, sem efeito colateral."""
    phone = "5511999990001"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    use_case = _build_use_case(
        db_session,
        chat_completion_port=_FakeChatCompletionPort(),
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )
    payload = _make_payload("MSG-DUP-1", phone, text="1")

    await use_case.execute(ProcessIncomingWhatsappMessageInput(instance_id=instance.id, payload=payload))
    await use_case.execute(ProcessIncomingWhatsappMessageInput(instance_id=instance.id, payload=payload))

    assert len(gateway.sent) == 1

    session_repository = SqlAlchemyWhatsappSessionRepository(db_session)
    session = await session_repository.get_by_phone_hash(hash_phone(phone))
    assert session is not None
    assert session.user_id == user.id


async def test_unlinked_number_does_not_create_session(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """RN-06: número sem usuário vinculado responde a mensagem padrão e não cria sessão."""
    instance = await _make_evolution_instance(db_session)
    use_case = _build_use_case(
        db_session,
        chat_completion_port=_FakeChatCompletionPort(),
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )
    phone = "5511999990002"
    payload = _make_payload("MSG-UNLINKED-1", phone, text="oi")

    await use_case.execute(ProcessIncomingWhatsappMessageInput(instance_id=instance.id, payload=payload))

    assert len(gateway.sent) == 1
    assert "Amezia" in gateway.sent[0][2]
    session = await SqlAlchemyWhatsappSessionRepository(db_session).get_by_phone_hash(hash_phone(phone))
    assert session is None


@pytest.mark.parametrize(
    ("option", "expected_mode"),
    [("1", BotMode.EXPENSE), ("2", BotMode.CHAT), ("3", BotMode.REPORT), ("4", BotMode.FEEDBACK)],
)
async def test_menu_option_transitions_to_expected_mode(
    db_session: AsyncSession,
    gateway: _FakeWhatsappGateway,
    option: str,
    expected_mode: BotMode,
) -> None:
    """As 4 transições do Menu para os modos Registrar/Chat/Relatório/Feedback."""
    phone = f"55119999901{option}"
    await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    use_case = _build_use_case(
        db_session,
        chat_completion_port=_FakeChatCompletionPort(),
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )
    payload = _make_payload(f"MSG-MENU-{option}", phone, text=option)

    await use_case.execute(ProcessIncomingWhatsappMessageInput(instance_id=instance.id, payload=payload))

    session = await SqlAlchemyWhatsappSessionRepository(db_session).get_by_phone_hash(hash_phone(phone))
    assert session is not None
    assert session.current_state == expected_mode
    assert len(gateway.sent) == 1


async def test_report_mode_sends_text_with_magic_link(
    db_session: AsyncSession,
    gateway: _FakeWhatsappGateway,
) -> None:
    """
    Entrar no modo Relatório manda um texto + link mágico pro painel de
    relatórios (`report_view` token) em vez de responder perguntas em
    linguagem natural via IA (comportamento substituído em 2026-08-18,
    a pedido do usuário) — e qualquer mensagem seguinte, já dentro do
    modo, reenvia o mesmo tipo de resposta (não distingue "1ª vez" de
    "de novo"). O token embutido no link decodifica de volta pro
    usuário certo, com `type: "report_view"`.
    """
    phone = "5511999990030"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    use_case = _build_use_case(
        db_session,
        chat_completion_port=_FakeChatCompletionPort(),
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    entry_payload = _make_payload("MSG-REPORT-ENTRY", phone, text="3")
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(instance_id=instance.id, payload=entry_payload)
    )

    assert len(gateway.sent) == 1
    entry_text = gateway.sent[0][2]
    assert "/reports/shared?token=" in entry_text

    token = entry_text.split("token=")[1].split("\n")[0].strip()
    payload = JwtService().decode(token, "report_view")
    assert payload is not None
    assert payload["sub"] == str(user.id)

    follow_up_payload = _make_payload("MSG-REPORT-FOLLOWUP", phone, text="quanto gastei esse mês?")
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(instance_id=instance.id, payload=follow_up_payload)
    )

    assert len(gateway.sent) == 2
    assert "/reports/shared?token=" in gateway.sent[1][2]


async def test_feedback_message_saves_feedback_and_auto_returns_to_menu(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """Feedback é o único estado que não é sticky — salva e volta ao Menu na mesma mensagem."""
    phone = "5511999990030"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    use_case = _build_use_case(
        db_session,
        chat_completion_port=_FakeChatCompletionPort(),
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-FB-ENTER", phone, text="4")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id,
            payload=_make_payload("MSG-FB-SEND", phone, text="Adorei o bot, só isso mesmo"),
        )
    )

    session = await SqlAlchemyWhatsappSessionRepository(db_session).get_by_phone_hash(hash_phone(phone))
    assert session is not None
    assert session.current_state is None

    # Escopado por user_id (não list_paginated, que é global) — o banco de dev
    # não é isolado entre a aplicação e os testes (sem banco de teste separado,
    # ver techContext.md), então feedback de outros usuários pode já existir.
    feedback_repository = SqlAlchemyFeedbackRepository(db_session)
    items, total = await feedback_repository.list_by_user(user.id, 1, 10)
    assert total == 1
    assert items[0].message == "Adorei o bot, só isso mesmo"


async def test_menu_override_resets_session_from_any_state(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """"0"/"menu" volta ao Menu a partir de qualquer estado (checado antes do dispatch)."""
    phone = "5511999990040"
    await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    use_case = _build_use_case(
        db_session,
        chat_completion_port=_FakeChatCompletionPort(),
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-OVR-ENTER", phone, text="2")
        )
    )
    session = await SqlAlchemyWhatsappSessionRepository(db_session).get_by_phone_hash(hash_phone(phone))
    assert session is not None and session.current_state == BotMode.CHAT

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-OVR-RESET", phone, text="menu")
        )
    )
    session = await SqlAlchemyWhatsappSessionRepository(db_session).get_by_phone_hash(hash_phone(phone))
    assert session is not None and session.current_state is None
    assert "menu" in gateway.sent[-1][2].lower() or "Olá" in gateway.sent[-1][2]


async def test_audio_outside_expense_mode_is_rejected_without_changing_state(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """Áudio só é aceito no modo `expense` — nos demais, guard responde sem mudar o estado."""
    phone = "5511999990050"
    await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    use_case = _build_use_case(
        db_session,
        chat_completion_port=_FakeChatCompletionPort(),
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-AUD-ENTER", phone, text="3")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-AUD-1", phone, audio=True)
        )
    )

    session = await SqlAlchemyWhatsappSessionRepository(db_session).get_by_phone_hash(hash_phone(phone))
    assert session is not None
    assert session.current_state == BotMode.REPORT
    assert len(gateway.sent) == 2


async def test_expense_audio_without_inline_base64_is_decrypted_from_cdn(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """
    Caminho mais comum na prática (achado do projeto irmão, DIARIO.md
    2026-08-15): a Evolution não embute o base64 do áudio no payload do
    webhook — `HandleExpenseStateUseCase` baixa e decripta direto do CDN
    do WhatsApp via `MediaDecryptorPort`, sem nenhuma chamada à Evolution
    API, antes de transcrever e registrar a despesa.
    """
    phone = "5511999990060"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    categories = await SqlAlchemyCategoryRepository(db_session).list_visible_to(user.id)
    category_name = categories[0].name
    chat_port = _FakeChatCompletionPort(
        response=f'{{"amount": 50, "category": "{category_name}", '
        f'"description": "mercado", "date": null}}'
    )
    media_decryptor = _FakeMediaDecryptor(audio_bytes=b"fake-audio-bytes")
    use_case = _build_use_case(
        db_session,
        chat_completion_port=chat_port,
        audio_transcription_port=_FakeAudioTranscriptionPort("gastei 50 no mercado"),
        whatsapp_gateway=gateway,
        media_decryptor=media_decryptor,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-EXP-ENTER", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-EXP-AUDIO", phone, audio=True)
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-EXP-INSTALLMENT", phone, text="1")
        )
    )

    assert len(gateway.sent) == 3
    assert "50" in gateway.sent[-1][2]
    assert media_decryptor.calls == [("https://mmg.whatsapp.net/fake-media-path", "ZmFrZS1tZWRpYS1rZXk=")]

    _, total = await SqlAlchemyTransactionRepository(db_session).list(
        user.id, TransactionFilters(), page=1, page_size=10
    )
    assert total == 1


async def test_expense_audio_with_inline_base64_skips_cdn_download(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """Quando a Evolution embute o base64 inline, o caminho rápido não chama o decriptador de mídia."""
    phone = "5511999990065"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    categories = await SqlAlchemyCategoryRepository(db_session).list_visible_to(user.id)
    category_name = categories[0].name
    chat_port = _FakeChatCompletionPort(
        response=f'{{"amount": 30, "category": "{category_name}", '
        f'"description": "padaria", "date": null}}'
    )
    media_decryptor = _FakeMediaDecryptor()
    use_case = _build_use_case(
        db_session,
        chat_completion_port=chat_port,
        audio_transcription_port=_FakeAudioTranscriptionPort("gastei 30 na padaria"),
        whatsapp_gateway=gateway,
        media_decryptor=media_decryptor,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-EXP2-ENTER", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id,
            payload=_make_payload(
                "MSG-EXP2-AUDIO", phone, audio=True, audio_base64="aW5saW5lLWJhc2U2NA=="
            ),
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-EXP2-INSTALLMENT", phone, text="1")
        )
    )

    assert len(gateway.sent) == 3
    assert "30" in gateway.sent[-1][2]
    assert media_decryptor.calls == []

    _, total = await SqlAlchemyTransactionRepository(db_session).list(
        user.id, TransactionFilters(), page=1, page_size=10
    )
    assert total == 1


async def test_expired_session_is_reset_to_menu_before_dispatch(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """TTL de 30min: sessão inativa é tratada como Menu já na mensagem que a encontra expirada."""
    phone = "5511999990070"
    await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    use_case = _build_use_case(
        db_session,
        chat_completion_port=_FakeChatCompletionPort(),
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-TTL-ENTER", phone, text="2")
        )
    )
    session_repository = SqlAlchemyWhatsappSessionRepository(db_session)
    session = await session_repository.get_by_phone_hash(hash_phone(phone))
    assert session is not None and session.current_state == BotMode.CHAT
    session.last_interaction_at = datetime.now(UTC) - timedelta(minutes=31)
    await session_repository.update(session)

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-TTL-AFTER", phone, text="1")
        )
    )

    session = await session_repository.get_by_phone_hash(hash_phone(phone))
    assert session is not None
    assert session.current_state == BotMode.EXPENSE


async def test_from_me_and_group_messages_are_ignored(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """Eco do próprio bot (`fromMe`) e mensagens de grupo nunca geram resposta."""
    phone = "5511999990080"
    await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    use_case = _build_use_case(
        db_session,
        chat_completion_port=_FakeChatCompletionPort(),
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id,
            payload=_make_payload("MSG-ECHO", phone, text="oi", from_me=True),
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id,
            payload=_make_payload("MSG-GROUP", phone, text="oi", is_group=True),
        )
    )

    assert gateway.sent == []


async def test_whatsapp_send_failure_does_not_crash_the_job(db_session: AsyncSession) -> None:
    """
    Falha da Evolution API no envio final (`_finish`) não deve propagar
    como exceção não tratada — a mensagem já foi marcada como processada
    (RN-04), então não há retry que ajude; o job precisa terminar limpo
    mesmo sem conseguir entregar a resposta (2026-08-16).
    """
    phone = "5511999990090"
    await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    failing_gateway = _FakeWhatsappGateway(raise_on_send=True)
    use_case = _build_use_case(
        db_session,
        chat_completion_port=_FakeChatCompletionPort(),
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=failing_gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-SEND-FAIL", phone, text="1")
        )
    )

    assert failing_gateway.sent == []
    session = await SqlAlchemyWhatsappSessionRepository(db_session).get_by_phone_hash(hash_phone(phone))
    assert session is not None
    assert session.current_state == BotMode.EXPENSE


async def test_expense_with_no_category_match_lets_user_choose_existing_by_number(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """
    Categoria dinâmica (build-context-12 §3.1): quando a IA devolve
    `category: null`, o bot lista as categorias existentes numeradas em
    vez de cair em "Outros" — escolher um número resolve a categoria
    direto, sem checagem de duplicata (não é nome novo).
    """
    phone = "5511999990100"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    categories = await SqlAlchemyCategoryRepository(db_session).list_visible_to(user.id)
    chosen_category = categories[0]
    chat_port = _FakeChatCompletionPort(
        response='{"amount": 45, "category": null, "description": "gasolina", "date": null}'
    )
    use_case = _build_use_case(
        db_session,
        chat_completion_port=chat_port,
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-NOCAT-ENTER", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-NOCAT-EXPENSE", phone, text="gasolina no posto")
        )
    )
    assert chosen_category.name in gateway.sent[-1][2]

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-NOCAT-CHOICE", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-NOCAT-INSTALLMENT", phone, text="1")
        )
    )

    assert "45" in gateway.sent[-1][2]
    assert chosen_category.name in gateway.sent[-1][2]

    transactions, total = await SqlAlchemyTransactionRepository(db_session).list(
        user.id, TransactionFilters(), page=1, page_size=10
    )
    assert total == 1
    assert transactions[0].category_id == chosen_category.id


async def test_expense_new_category_name_creates_it_when_not_duplicate(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """
    Categoria dinâmica: digitar um nome que não existe ainda (sem
    duplicata semântica) cria a categoria privada de verdade — sem
    limite de quantidade (build-context-02/DIARIO 2026-09-09) — e segue
    pro registro normalmente.
    """
    phone = "5511999990105"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    chat_port = _FakeChatCompletionPort(
        response='{"amount": 20, "category": null, "description": "aluguel de patinete", "date": null}'
    )
    use_case = _build_use_case(
        db_session,
        chat_completion_port=chat_port,
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
        embedding_generator=_FakeSemanticEmbeddingGenerator(),
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-NEWCAT-ENTER", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-NEWCAT-EXPENSE", phone, text="patinete")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id,
            payload=_make_payload("MSG-NEWCAT-NAME", phone, text="Micromobilidade"),
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-NEWCAT-INSTALLMENT", phone, text="1")
        )
    )

    assert "Micromobilidade" in gateway.sent[-1][2]

    categories = await SqlAlchemyCategoryRepository(db_session).list_visible_to(user.id)
    created = [category for category in categories if category.name == "Micromobilidade"]
    assert len(created) == 1
    assert created[0].user_id == user.id


async def test_expense_category_dedup_confirm_reuses_existing_category(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """
    Checagem de duplicata semântica (build-context-12 §3.1 passo 3):
    digitar o mesmo nome de uma categoria já indexada (mesmo vetor, no
    fake) dispara a pergunta de confirmação — respondendo "sim", usa a
    categoria existente em vez de criar uma nova (nenhuma duplicata).
    """
    phone = "5511999990110"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    semantic_generator = _FakeSemanticEmbeddingGenerator()

    category_repository = SqlAlchemyCategoryRepository(db_session)
    existing = await CreateCategoryUseCase(category_repository, _NoopJobEnqueuer()).execute(
        CreateCategoryInput(user_id=user.id, name="Petshop", color="#123456", icon="tag")
    )
    # Simula o job `index_category_embedding` já ter rodado pra essa categoria (enfileirado como
    # no-op nos testes, ver `_NoopJobEnqueuer`).
    await IndexCategoryEmbeddingUseCase(
        SqlAlchemyEmbeddingRepository(db_session), semantic_generator
    ).execute(user.id, existing.id, existing.name)

    chat_port = _FakeChatCompletionPort(
        response='{"amount": 60, "category": null, "description": "uber", "date": null}'
    )
    use_case = _build_use_case(
        db_session,
        chat_completion_port=chat_port,
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
        embedding_generator=semantic_generator,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-DEDUP-ENTER", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-DEDUP-EXPENSE", phone, text="racao pro cachorro")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-DEDUP-NAME", phone, text="Petshop")
        )
    )
    assert "Petshop" in gateway.sent[-1][2]

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-DEDUP-CONFIRM", phone, text="sim")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-DEDUP-INSTALLMENT", phone, text="1")
        )
    )

    categories = await category_repository.list_visible_to(user.id)
    transporte_categories = [category for category in categories if category.name == "Petshop"]
    assert len(transporte_categories) == 1

    transactions, total = await SqlAlchemyTransactionRepository(db_session).list(
        user.id, TransactionFilters(), page=1, page_size=10
    )
    assert total == 1
    assert transactions[0].category_id == existing.id


async def test_expense_installment_choice_creates_grouped_transactions(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """Parcelamento via bot (build-context-12 §3.2) reaproveita `installment_group_id`."""
    phone = "5511999990115"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    categories = await SqlAlchemyCategoryRepository(db_session).list_visible_to(user.id)
    chat_port = _FakeChatCompletionPort(
        response=f'{{"amount": 300, "category": "{categories[0].name}", '
        f'"description": "notebook", "date": null}}'
    )
    use_case = _build_use_case(
        db_session,
        chat_completion_port=chat_port,
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-INST-ENTER", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-INST-EXPENSE", phone, text="notebook novo")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-INST-CHOICE", phone, text="2")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-INST-COUNT", phone, text="3")
        )
    )
    assert "Confirma" in gateway.sent[-1][2] or "Confirm" in gateway.sent[-1][2]
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-INST-DATE-CONFIRM", phone, text="sim")
        )
    )

    transactions, total = await SqlAlchemyTransactionRepository(db_session).list(
        user.id, TransactionFilters(), page=1, page_size=10
    )
    assert total == 3
    group_ids = {transaction.installment_group_id for transaction in transactions}
    assert len(group_ids) == 1
    assert None not in group_ids


async def test_expense_recurrence_choice_creates_recurring_transaction(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """Recorrência via bot (build-context-12 §3.2) — as 3 frequências que o domínio já suporta."""
    phone = "5511999990120"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    categories = await SqlAlchemyCategoryRepository(db_session).list_visible_to(user.id)
    chat_port = _FakeChatCompletionPort(
        response=f'{{"amount": 15, "category": "{categories[0].name}", '
        f'"description": "streaming", "date": null}}'
    )
    use_case = _build_use_case(
        db_session,
        chat_completion_port=chat_port,
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-REC-ENTER", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-REC-EXPENSE", phone, text="assinatura streaming")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-REC-CHOICE", phone, text="3")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-REC-FREQUENCY", phone, text="2")
        )
    )
    # Digita uma data diferente da inferida em vez de confirmar — cobre o caminho de correção
    # da data de início (build-context-12 §3.2, pedido do usuário em 2026-09-09).
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-REC-DATE", phone, text="10/03/2026")
        )
    )

    transactions, total = await SqlAlchemyTransactionRepository(db_session).list(
        user.id, TransactionFilters(), page=1, page_size=10
    )
    assert total == 1
    assert transactions[0].is_recurring_occurrence is True
    assert transactions[0].date == date(2026, 3, 10)


async def test_expense_start_date_invalid_text_is_rejected_without_losing_the_draft(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """Texto que não é `sim` nem `DD/MM`(`/YYYY`) pede a data de novo, sem perder o rascunho."""
    phone = "5511999990130"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    categories = await SqlAlchemyCategoryRepository(db_session).list_visible_to(user.id)
    chat_port = _FakeChatCompletionPort(
        response=f'{{"amount": 80, "category": "{categories[0].name}", '
        f'"description": "conserto", "date": null}}'
    )
    use_case = _build_use_case(
        db_session,
        chat_completion_port=chat_port,
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-BADDATE-ENTER", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-BADDATE-EXPENSE", phone, text="conserto do carro")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-BADDATE-CHOICE", phone, text="2")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-BADDATE-COUNT", phone, text="2")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-BADDATE-INVALID", phone, text="não sei")
        )
    )

    session = await SqlAlchemyWhatsappSessionRepository(db_session).get_by_phone_hash(hash_phone(phone))
    assert session is not None
    assert session.pending_action is not None
    assert session.pending_action["step"] == "awaiting_start_date_confirm"
    assert session.pending_action["draft"]["installment_total"] == 2

    _, total = await SqlAlchemyTransactionRepository(db_session).list(
        user.id, TransactionFilters(), page=1, page_size=10
    )
    assert total == 0


async def test_expense_auto_detected_installment_total_computes_per_installment_amount(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """
    "gastei 600 dividido em 10 vezes" (build-context-12, 2026-09-10): a IA já detecta
    parcelamento na mensagem original — pula o menu 1/2/3 e a pergunta de parcelas,
    e o valor por parcela é calculado no código (600 ÷ 10 = 60), nunca pela IA.
    """
    phone = "5511999990135"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    categories = await SqlAlchemyCategoryRepository(db_session).list_visible_to(user.id)
    chat_port = _FakeChatCompletionPort(
        response=f'{{"amount": 600, "category": "{categories[0].name}", "description": "notebook", '
        f'"date": null, "installment_total": 10, "recurrence_frequency": null, '
        f'"amount_refers_to": "total"}}'
    )
    use_case = _build_use_case(
        db_session,
        chat_completion_port=chat_port,
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-AUTOINST-ENTER", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id,
            payload=_make_payload("MSG-AUTOINST-EXPENSE", phone, text="gastei 600 dividido em 10 vezes no notebook"),
        )
    )
    # Pulou direto pra confirmação de data — nem menu 1/2/3, nem pergunta de quantidade de parcelas.
    assert "Confirma" in gateway.sent[-1][2] or "Confirm" in gateway.sent[-1][2]

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-AUTOINST-DATE", phone, text="sim")
        )
    )

    transactions, total = await SqlAlchemyTransactionRepository(db_session).list(
        user.id, TransactionFilters(), page=1, page_size=10
    )
    assert total == 10
    assert all(transaction.amount.amount_cents == 6000 for transaction in transactions)


async def test_expense_auto_detected_installment_per_installment_amount_used_as_is(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """"parcelado em 3x de 100" — o valor mencionado já é por parcela, não deve ser dividido."""
    phone = "5511999990140"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    categories = await SqlAlchemyCategoryRepository(db_session).list_visible_to(user.id)
    chat_port = _FakeChatCompletionPort(
        response=f'{{"amount": 100, "category": "{categories[0].name}", "description": "celular", '
        f'"date": null, "installment_total": 3, "recurrence_frequency": null, '
        f'"amount_refers_to": "per_installment"}}'
    )
    use_case = _build_use_case(
        db_session,
        chat_completion_port=chat_port,
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-PERINST-ENTER", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id,
            payload=_make_payload("MSG-PERINST-EXPENSE", phone, text="celular parcelado em 3x de 100 reais"),
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-PERINST-DATE", phone, text="sim")
        )
    )

    transactions, total = await SqlAlchemyTransactionRepository(db_session).list(
        user.id, TransactionFilters(), page=1, page_size=10
    )
    assert total == 3
    assert all(transaction.amount.amount_cents == 10000 for transaction in transactions)


async def test_expense_auto_detected_installment_ambiguous_amount_is_asked(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """
    Quando a IA não consegue decidir se o valor é total ou por parcela
    (`amount_refers_to: null`), o bot pergunta o valor da parcela em vez
    de arriscar a conta — pedido do usuário em 2026-09-10.
    """
    phone = "5511999990145"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    categories = await SqlAlchemyCategoryRepository(db_session).list_visible_to(user.id)
    chat_port = _FakeChatCompletionPort(
        response=f'{{"amount": 500, "category": "{categories[0].name}", "description": "sofa", '
        f'"date": null, "installment_total": 5, "recurrence_frequency": null, '
        f'"amount_refers_to": null}}'
    )
    use_case = _build_use_case(
        db_session,
        chat_completion_port=chat_port,
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-AMBINST-ENTER", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id,
            payload=_make_payload("MSG-AMBINST-EXPENSE", phone, text="sofa em 5 vezes, uns 500 reais"),
        )
    )
    assert "500" in gateway.sent[-1][2]
    assert "5" in gateway.sent[-1][2]

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-AMBINST-AMOUNT", phone, text="120")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-AMBINST-DATE", phone, text="sim")
        )
    )

    transactions, total = await SqlAlchemyTransactionRepository(db_session).list(
        user.id, TransactionFilters(), page=1, page_size=10
    )
    assert total == 5
    assert all(transaction.amount.amount_cents == 12000 for transaction in transactions)


async def test_expense_auto_detected_recurrence_skips_menu(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """"80 reais por mês" já detecta recorrência mensal — pula o menu 1/2/3."""
    phone = "5511999990150"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    categories = await SqlAlchemyCategoryRepository(db_session).list_visible_to(user.id)
    chat_port = _FakeChatCompletionPort(
        response=f'{{"amount": 80, "category": "{categories[0].name}", "description": "academia", '
        f'"date": null, "installment_total": null, "recurrence_frequency": "monthly", '
        f'"amount_refers_to": null}}'
    )
    use_case = _build_use_case(
        db_session,
        chat_completion_port=chat_port,
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-AUTOREC-ENTER", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id,
            payload=_make_payload("MSG-AUTOREC-EXPENSE", phone, text="academia, 80 reais por mes"),
        )
    )
    assert "Confirma" in gateway.sent[-1][2] or "Confirm" in gateway.sent[-1][2]

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-AUTOREC-DATE", phone, text="sim")
        )
    )

    transactions, total = await SqlAlchemyTransactionRepository(db_session).list(
        user.id, TransactionFilters(), page=1, page_size=10
    )
    assert total == 1
    assert transactions[0].is_recurring_occurrence is True
    assert transactions[0].amount.amount_cents == 8000


async def test_menu_override_cancels_pending_category_choice(
    db_session: AsyncSession, gateway: _FakeWhatsappGateway
) -> None:
    """"0"/"menu" cancela um rascunho de categoria em aberto (build-context-12 §2), sem criar nada."""
    phone = "5511999990125"
    user = await _make_linked_user(db_session, phone)
    instance = await _make_evolution_instance(db_session)
    chat_port = _FakeChatCompletionPort(
        response='{"amount": 10, "category": null, "description": "algo", "date": null}'
    )
    use_case = _build_use_case(
        db_session,
        chat_completion_port=chat_port,
        audio_transcription_port=_FakeAudioTranscriptionPort(),
        whatsapp_gateway=gateway,
    )

    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-CANCEL-ENTER", phone, text="1")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-CANCEL-EXPENSE", phone, text="algo")
        )
    )
    await use_case.execute(
        ProcessIncomingWhatsappMessageInput(
            instance_id=instance.id, payload=_make_payload("MSG-CANCEL-ZERO", phone, text="0")
        )
    )

    session = await SqlAlchemyWhatsappSessionRepository(db_session).get_by_phone_hash(hash_phone(phone))
    assert session is not None
    assert session.pending_action is None
    assert session.current_state is None

    _, total = await SqlAlchemyTransactionRepository(db_session).list(
        user.id, TransactionFilters(), page=1, page_size=10
    )
    assert total == 0
