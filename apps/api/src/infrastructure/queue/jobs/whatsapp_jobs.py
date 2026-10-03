import logging
import re
import uuid
from typing import Any

from src.application.ai_usage.use_cases.check_ai_usage_limit import CheckAiUsageLimitUseCase
from src.application.ai_usage.use_cases.record_ai_usage import RecordAiUsageUseCase
from src.application.category.use_cases.check_category_duplicate import (
    CheckCategoryDuplicateUseCase,
)
from src.application.category.use_cases.create_category import CreateCategoryUseCase
from src.application.conversation.use_cases.create_conversation import CreateConversationUseCase
from src.application.conversation.use_cases.generate_ai_response import GenerateAiResponseUseCase
from src.application.conversation.use_cases.get_or_create_active_conversation import (
    GetOrCreateActiveConversationUseCase,
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
from src.infrastructure.ai.chat_completion_gateway import ChatCompletionGateway
from src.infrastructure.ai.gemini_client import GeminiAudioTranscriber, GeminiEmbeddingClient
from src.infrastructure.config import get_settings
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
from src.infrastructure.database.session import async_session_factory
from src.infrastructure.security.jwt_service import JwtService
from src.infrastructure.security.phone_hasher import PhoneHasher
from src.infrastructure.whatsapp.evolution_client import EvolutionApiClient
from src.infrastructure.whatsapp.media_decryptor import WhatsappMediaDecryptor
from src.infrastructure.whatsapp.messages import MessageCatalog

logger = logging.getLogger(__name__)

_NON_DIGITS = re.compile(r"\D+")


async def process_incoming_whatsapp_message(ctx: dict, instance_id: int, payload: dict[str, Any]) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Job ARQ (registrado em
    `infrastructure/queue/worker.py::WorkerSettings.functions`) — o
    pipeline completo do Bot WhatsApp (build-context-07 §2.6), chamado
    diretamente pelo stub `dispatch_message_to_bot`
    (infrastructure/queue/jobs/evolution_webhook_jobs.py, evento
    `MESSAGES_UPSERT` do webhook Evolution, build-context-06). Abre sua
    própria `AsyncSession` e comita ao final — mesmo padrão de
    `generate_ai_response`. Todos os erros de handler já são capturados
    dentro de `ProcessIncomingWhatsappMessageUseCase` (RN-04: o job nunca
    falha/reprocessa).
    """
    settings = get_settings()
    async with async_session_factory() as session:
        conversation_repository = SqlAlchemyConversationRepository(session)
        embedding_repository = SqlAlchemyEmbeddingRepository(session)
        embedding_generator = GeminiEmbeddingClient()
        chat_completion_gateway = ChatCompletionGateway()
        category_repository = SqlAlchemyCategoryRepository(session)
        transaction_repository = SqlAlchemyTransactionRepository(session)
        message_catalog = MessageCatalog()
        ai_usage_repository = SqlAlchemyAiUsageRepository(session)
        record_ai_usage_use_case = RecordAiUsageUseCase(ai_usage_repository)
        check_ai_usage_limit_use_case = CheckAiUsageLimitUseCase(
            SqlAlchemySubscriptionRepository(session),
            SqlAlchemyPlanLimitsRepository(session),
            ai_usage_repository,
        )

        create_transaction_use_case = CreateTransactionUseCase(
            transaction_repository,
            category_repository,
            CreateRecurringTransactionUseCase(
                transaction_repository, SqlAlchemyRecurrenceRuleRepository(session)
            ),
            ctx["redis"],
        )

        handle_report_state_use_case = HandleReportStateUseCase(
            get_financial_summary_use_case=GetFinancialSummaryUseCase(
                SqlAlchemyReportsRepository(session)
            ),
            message_catalog=message_catalog,
            jwt_service=JwtService(),
        )

        use_case = ProcessIncomingWhatsappMessageUseCase(
            processed_bot_message_repository=SqlAlchemyProcessedBotMessageRepository(session),
            whatsapp_session_repository=SqlAlchemyWhatsappSessionRepository(session),
            user_repository=SqlAlchemyUserRepository(session),
            evolution_instance_repository=SqlAlchemyEvolutionInstanceRepository(session),
            whatsapp_gateway=EvolutionApiClient(),
            phone_hasher=PhoneHasher(),
            message_catalog=message_catalog,
            reset_to_menu_use_case=ResetToMenuUseCase(message_catalog),
            handle_menu_state_use_case=HandleMenuStateUseCase(
                message_catalog, handle_report_state_use_case
            ),
            handle_expense_state_use_case=HandleExpenseStateUseCase(
                register_expense_use_case=RegisterExpenseViaBotUseCase(
                    category_repository, chat_completion_gateway, record_ai_usage_use_case
                ),
                create_transaction_use_case=create_transaction_use_case,
                create_category_use_case=CreateCategoryUseCase(category_repository, ctx["redis"]),
                check_category_duplicate_use_case=CheckCategoryDuplicateUseCase(
                    embedding_repository, embedding_generator, settings.CATEGORY_DEDUP_THRESHOLD
                ),
                category_repository=category_repository,
                audio_transcription_port=GeminiAudioTranscriber(),
                media_decryptor=WhatsappMediaDecryptor(),
                message_catalog=message_catalog,
                record_ai_usage_use_case=record_ai_usage_use_case,
            ),
            handle_chat_state_use_case=HandleChatStateUseCase(
                conversation_repository=conversation_repository,
                get_or_create_active_conversation_use_case=GetOrCreateActiveConversationUseCase(
                    conversation_repository,
                    CreateConversationUseCase(conversation_repository),
                    settings.CONVERSATION_ACTIVE_WINDOW_HOURS,
                ),
                generate_ai_response_use_case=GenerateAiResponseUseCase(
                    conversation_repository=conversation_repository,
                    user_repository=SqlAlchemyUserRepository(session),
                    transaction_repository=transaction_repository,
                    chat_completion_port=chat_completion_gateway,
                    search_relevant_context_use_case=SearchRelevantContextUseCase(
                        embedding_repository,
                        embedding_generator,
                        pool_size=settings.RAG_POOL_SIZE,
                        threshold=settings.RAG_SIMILARITY_THRESHOLD,
                        top_k=settings.RAG_TOP_K,
                    ),
                    summarize_old_messages_use_case=SummarizeOldMessagesUseCase(
                        conversation_repository, chat_completion_gateway
                    ),
                    index_conversation_message_embedding_use_case=(
                        IndexConversationMessageEmbeddingUseCase(
                            embedding_repository, embedding_generator
                        )
                    ),
                    summary_threshold=settings.CONVERSATION_SUMMARY_THRESHOLD,
                    check_ai_usage_limit_use_case=check_ai_usage_limit_use_case,
                    record_ai_usage_use_case=record_ai_usage_use_case,
                ),
                message_catalog=message_catalog,
            ),
            handle_report_state_use_case=handle_report_state_use_case,
            handle_feedback_state_use_case=HandleFeedbackStateUseCase(
                submit_feedback_use_case=SubmitFeedbackUseCase(SqlAlchemyFeedbackRepository(session)),
                message_catalog=message_catalog,
            ),
            subscription_repository=SqlAlchemySubscriptionRepository(session),
            plan_limits_repository=SqlAlchemyPlanLimitsRepository(session),
        )

        await use_case.execute(
            ProcessIncomingWhatsappMessageInput(instance_id=instance_id, payload=payload)
        )
        await session.commit()


async def send_whatsapp_welcome_message(ctx: dict, user_id: str) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Job ARQ — envia uma mensagem de boas-vindas pelo WhatsApp
    quando o usuário vincula/troca o número no perfil
    (`UpdateProfileUseCase`, pedido do usuário em 2026-08-16). Best
    effort de propósito: sem instância Evolution ativa, ou qualquer
    falha no envio, só loga e retorna — o perfil já foi salvo antes
    deste job rodar, nada aqui deveria propagar erro pro usuário.
    """
    async with async_session_factory() as session:
        user = await SqlAlchemyUserRepository(session).get_by_id(uuid.UUID(user_id))
        if user is None or not user.phone:
            return

        instance = await SqlAlchemyEvolutionInstanceRepository(session).get_active()
        if instance is None:
            logger.warning(
                "No active Evolution instance — skipping welcome message (user_id=%s)", user_id
            )
            return

        message_catalog = MessageCatalog()
        text = (
            f"{message_catalog.get_message('welcome.intro', user.language)}\n\n"
            f"{message_catalog.render_menu(user.language)}"
        )
        phone_digits = _NON_DIGITS.sub("", user.phone)

        try:
            await EvolutionApiClient().send_text(instance.name, phone_digits, text)
        except Exception:
            logger.warning(
                "Failed to send WhatsApp welcome message (user_id=%s)", user_id, exc_info=True
            )
