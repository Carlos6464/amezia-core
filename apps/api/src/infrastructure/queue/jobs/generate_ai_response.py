from src.application.ai_usage.use_cases.check_ai_usage_limit import CheckAiUsageLimitUseCase
from src.application.ai_usage.use_cases.record_ai_usage import RecordAiUsageUseCase
from src.application.conversation.use_cases.generate_ai_response import (
    GenerateAiResponseInput,
    GenerateAiResponseUseCase,
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
from src.domain.ai_usage.exceptions import AiUsageLimitExceededError
from src.domain.conversation.exceptions import AllProvidersUnavailableError
from src.infrastructure.ai.chat_completion_gateway import ChatCompletionGateway
from src.infrastructure.ai.gemini_client import GeminiEmbeddingClient
from src.infrastructure.config import get_settings
from src.infrastructure.database.repositories.ai_usage_repository import (
    SqlAlchemyAiUsageRepository,
)
from src.infrastructure.database.repositories.conversation_repository import (
    SqlAlchemyConversationRepository,
)
from src.infrastructure.database.repositories.embedding_repository import (
    SqlAlchemyEmbeddingRepository,
)
from src.infrastructure.database.repositories.subscription_repository import (
    SqlAlchemyPlanLimitsRepository,
    SqlAlchemySubscriptionRepository,
)
from src.infrastructure.database.repositories.transaction_repository import (
    SqlAlchemyTransactionRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.database.session import async_session_factory
from src.infrastructure.queue.ws_publisher import publish_to_user


async def generate_ai_response(ctx: dict, conversation_id: int, message_id: int) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Job ARQ (registrado em
    `infrastructure/queue/worker.py::WorkerSettings.functions`) —
    enfileirado por `SendMessageUseCase` a cada mensagem enviada pelo
    usuário. Roda fora do ciclo de requisição HTTP, então abre sua
    própria `AsyncSession` e comita ao final (mesmo padrão de
    `generate_recurring_transactions`). Em caso de falha dos dois
    providers (`AllProvidersUnavailableError`), nenhuma mensagem de
    assistente é persistida — publica `ai_response_failed` em vez de
    `ai_message_ready` (build-context-04 §2.4, passo 10).
    """
    settings = get_settings()
    async with async_session_factory() as session:
        conversation_repository = SqlAlchemyConversationRepository(session)
        embedding_repository = SqlAlchemyEmbeddingRepository(session)
        embedding_generator = GeminiEmbeddingClient()
        chat_completion_gateway = ChatCompletionGateway()

        conversation = await conversation_repository.get_by_id(conversation_id)
        user_message = await conversation_repository.get_message_by_id(message_id)
        if conversation is None or user_message is None:
            return

        use_case = GenerateAiResponseUseCase(
            conversation_repository=conversation_repository,
            user_repository=SqlAlchemyUserRepository(session),
            transaction_repository=SqlAlchemyTransactionRepository(session),
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
                IndexConversationMessageEmbeddingUseCase(embedding_repository, embedding_generator)
            ),
            summary_threshold=settings.CONVERSATION_SUMMARY_THRESHOLD,
            check_ai_usage_limit_use_case=CheckAiUsageLimitUseCase(
                SqlAlchemySubscriptionRepository(session),
                SqlAlchemyPlanLimitsRepository(session),
                SqlAlchemyAiUsageRepository(session),
            ),
            record_ai_usage_use_case=RecordAiUsageUseCase(SqlAlchemyAiUsageRepository(session)),
        )

        try:
            assistant_message = await use_case.execute(
                GenerateAiResponseInput(conversation_id=conversation_id, message_id=message_id)
            )
        except AllProvidersUnavailableError:
            await session.commit()
            await publish_to_user(
                conversation.user_id,
                {
                    "event": "ai_response_failed",
                    "conversation_public_id": str(conversation.public_id),
                    "user_message_id": str(user_message.public_id),
                    "error": "ai.responseFailed",
                },
            )
            return
        except AiUsageLimitExceededError:
            await session.commit()
            await publish_to_user(
                conversation.user_id,
                {
                    "event": "ai_response_failed",
                    "conversation_public_id": str(conversation.public_id),
                    "user_message_id": str(user_message.public_id),
                    "error": "ai.usageLimitExceeded",
                },
            )
            return

        await session.commit()
        if assistant_message is None:
            return

        await publish_to_user(
            conversation.user_id,
            {
                "event": "ai_message_ready",
                "conversation_public_id": str(conversation.public_id),
                "message": {
                    "public_id": str(assistant_message.public_id),
                    "role": assistant_message.role.value,
                    "content": assistant_message.content,
                    "provider_used": (
                        assistant_message.provider_used.value
                        if assistant_message.provider_used
                        else None
                    ),
                    "created_at": assistant_message.created_at.isoformat(),
                },
            },
        )
