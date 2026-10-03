import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.conversation.use_cases.create_conversation import CreateConversationUseCase
from src.application.conversation.use_cases.generate_ai_response import (
    GenerateAiResponseInput,
    GenerateAiResponseUseCase,
)
from src.application.conversation.use_cases.get_or_create_active_conversation import (
    GetOrCreateActiveConversationInput,
    GetOrCreateActiveConversationUseCase,
)
from src.domain.conversation.entities import Conversation, ConversationMessage
from src.domain.conversation.exceptions import AllProvidersUnavailableError
from src.domain.conversation.ports import ChatCompletionResult
from src.domain.conversation.value_objects import AiProvider, ConversationChannel, MessageRole
from src.domain.embedding.entities import Embedding, EmbeddingSourceType
from src.domain.transaction.entities import Transaction
from src.domain.transaction.value_objects import Money, TransactionType
from src.infrastructure.ai.chat_completion_gateway import ChatCompletionGateway
from src.infrastructure.database.models.user import User as UserModel
from src.infrastructure.database.repositories.category_repository import (
    SqlAlchemyCategoryRepository,
)
from src.infrastructure.database.repositories.conversation_repository import (
    SqlAlchemyConversationRepository,
)
from src.infrastructure.database.repositories.embedding_repository import (
    SqlAlchemyEmbeddingRepository,
)
from src.infrastructure.database.repositories.transaction_repository import (
    SqlAlchemyTransactionRepository,
)
from src.infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from src.infrastructure.security.jwt_service import JwtService
from tests.conftest import FakeArqPool, auth_headers

pytestmark = pytest.mark.asyncio

DIMENSION = 768


def _vector(primary_index: int = 0) -> list[float]:
    """Vetor unitário com 1.0 num único eixo — cosine similarity previsível para os testes."""
    vector = [0.0] * DIMENSION
    vector[primary_index] = 1.0
    return vector


async def _make_user_with_language(db_session: AsyncSession, language: str) -> tuple[UserModel, str]:
    """Mesmo padrão do `make_user` de conftest.py, mas com `language` escolhido pelo teste."""
    user_id = uuid.uuid4()
    model = UserModel(
        id=user_id,
        name="Test User",
        email=f"user-{user_id.hex[:12]}@example.com",
        password_hash="not-a-real-hash",
        role="user",
        language=language,
    )
    db_session.add(model)
    await db_session.flush()
    token = JwtService().create_access_token(user_id=str(user_id), role="user", language=language)
    return model, token


class _FailingChatClient:
    async def complete(self, system_instruction: str, messages: list) -> tuple[str, int, int]:
        raise RuntimeError("provider unavailable")


class _WorkingChatClient:
    def __init__(self, response: str) -> None:
        self._response = response

    async def complete(self, system_instruction: str, messages: list) -> tuple[str, int, int]:
        return self._response, 10, 5


class _FakeChatCompletionPort:
    def __init__(self, response: str = "Aqui está sua resposta.") -> None:
        self.response = response
        self.received_system_instruction: str | None = None

    async def complete(self, system_instruction: str, messages: list) -> ChatCompletionResult:
        self.received_system_instruction = system_instruction
        return ChatCompletionResult(
            content=self.response,
            provider=AiProvider.GEMINI,
            model="gemini-2.5-flash",
            input_tokens=10,
            output_tokens=5,
        )


class _FakeCheckAiUsageLimitUseCase:
    """Nunca bloqueia — os testes deste arquivo não cobrem limite de plano (ver test_subscriptions.py)."""

    async def execute(self, input_data: object) -> None:
        return None


class _FakeRecordAiUsageUseCase:
    def __init__(self) -> None:
        self.calls: list[object] = []

    async def execute(self, input_data: object) -> None:
        self.calls.append(input_data)


class _FakeSearchRelevantContextUseCase:
    async def execute(self, user_id: uuid.UUID, query_text: str) -> list:
        return []


class _FakeSummarizeOldMessagesUseCase:
    async def execute(self, conversation: Conversation, unsummarized_messages: list) -> Conversation:
        return conversation


class _FakeIndexConversationMessageEmbeddingUseCase:
    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, ConversationMessage]] = []

    async def execute(self, user_id: uuid.UUID, message: ConversationMessage) -> None:
        self.calls.append((user_id, message))


async def test_embedding_search_similar_filters_by_user_id(
    db_session: AsyncSession, make_user: Any
) -> None:
    """RN-01: a busca vetorial nunca deve devolver embedding de outro usuário."""
    user_a, _ = await make_user()
    user_b, _ = await make_user()
    repository = SqlAlchemyEmbeddingRepository(db_session)

    await repository.upsert(
        Embedding(
            user_id=user_a.id,
            source_type=EmbeddingSourceType.TRANSACTION,
            source_id=1,
            content="gasto do usuario a",
            embedding=_vector(0),
        )
    )
    await repository.upsert(
        Embedding(
            user_id=user_b.id,
            source_type=EmbeddingSourceType.TRANSACTION,
            source_id=2,
            content="gasto do usuario b",
            embedding=_vector(0),
        )
    )

    matches = await repository.search_similar(
        user_a.id, _vector(0), pool_size=300, threshold=0.5, top_k=4
    )

    assert len(matches) == 1
    assert matches[0].content == "gasto do usuario a"


async def test_chat_completion_gateway_falls_back_to_grok_when_gemini_fails() -> None:
    gateway = ChatCompletionGateway(
        gemini_client=_FailingChatClient(), grok_client=_WorkingChatClient("resposta do grok")
    )

    result = await gateway.complete("system", [])

    assert result.content == "resposta do grok"
    assert result.provider == AiProvider.GROK


async def test_chat_completion_gateway_raises_when_both_providers_fail() -> None:
    gateway = ChatCompletionGateway(gemini_client=_FailingChatClient(), grok_client=_FailingChatClient())

    with pytest.raises(AllProvidersUnavailableError):
        await gateway.complete("system", [])


async def test_generate_ai_response_uses_user_language_and_sets_title_on_first_reply(
    db_session: AsyncSession,
) -> None:
    """RN-10: a instrução de sistema deve refletir o idioma do perfil do usuário."""
    user, _ = await _make_user_with_language(db_session, "en")
    conversation_repository = SqlAlchemyConversationRepository(db_session)
    conversation = await conversation_repository.create(
        Conversation(user_id=user.id, channel=ConversationChannel.WEB)
    )
    user_message = await conversation_repository.add_message(
        ConversationMessage(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="How much did I spend this month?",
        )
    )

    fake_chat_port = _FakeChatCompletionPort()
    index_use_case = _FakeIndexConversationMessageEmbeddingUseCase()
    use_case = GenerateAiResponseUseCase(
        conversation_repository=conversation_repository,
        user_repository=SqlAlchemyUserRepository(db_session),
        transaction_repository=SqlAlchemyTransactionRepository(db_session),
        chat_completion_port=fake_chat_port,
        search_relevant_context_use_case=_FakeSearchRelevantContextUseCase(),
        summarize_old_messages_use_case=_FakeSummarizeOldMessagesUseCase(),
        index_conversation_message_embedding_use_case=index_use_case,
        summary_threshold=20,
        check_ai_usage_limit_use_case=_FakeCheckAiUsageLimitUseCase(),
        record_ai_usage_use_case=_FakeRecordAiUsageUseCase(),
    )

    result = await use_case.execute(
        GenerateAiResponseInput(conversation_id=conversation.id, message_id=user_message.id)
    )

    assert result is not None
    assert result.role == MessageRole.ASSISTANT
    assert result.provider_used == AiProvider.GEMINI
    assert fake_chat_port.received_system_instruction is not None
    assert "English" in fake_chat_port.received_system_instruction

    updated_conversation = await conversation_repository.get_by_id(conversation.id)
    assert updated_conversation is not None
    assert updated_conversation.title == "How much did I spend this month?"
    assert len(index_use_case.calls) == 2


async def test_generate_ai_response_includes_deterministic_financial_snapshot_even_without_rag(
    db_session: AsyncSession, make_user: Any
) -> None:
    """
    Corrige o bug de produção de 2026-08-12: "quanto gastei esse mês" tem
    baixa similaridade semântica com o texto de uma transação individual,
    então o RAG sozinho não trazia contexto (0 matches) e o modelo
    inventava um número. O snapshot financeiro precisa ter o total real
    mesmo com `_FakeSearchRelevantContextUseCase` devolvendo `[]` de
    propósito (simula o RAG não encontrando nada).
    """
    user, _ = await make_user()
    categories = await SqlAlchemyCategoryRepository(db_session).list_visible_to(user.id)
    category = categories[0]

    transaction_repository = SqlAlchemyTransactionRepository(db_session)
    await transaction_repository.create(
        Transaction(
            user_id=user.id,
            category_id=category.id,
            type=TransactionType.EXPENSE,
            amount=Money.from_decimal(Decimal("258.00")),
            description="Parcela da faculdade",
            date=datetime.now(UTC).date(),
        )
    )

    conversation_repository = SqlAlchemyConversationRepository(db_session)
    conversation = await conversation_repository.create(
        Conversation(user_id=user.id, channel=ConversationChannel.WEB)
    )
    user_message = await conversation_repository.add_message(
        ConversationMessage(
            conversation_id=conversation.id, role=MessageRole.USER, content="Quanto gastei esse mes?"
        )
    )

    fake_chat_port = _FakeChatCompletionPort()
    use_case = GenerateAiResponseUseCase(
        conversation_repository=conversation_repository,
        user_repository=SqlAlchemyUserRepository(db_session),
        transaction_repository=transaction_repository,
        chat_completion_port=fake_chat_port,
        search_relevant_context_use_case=_FakeSearchRelevantContextUseCase(),
        summarize_old_messages_use_case=_FakeSummarizeOldMessagesUseCase(),
        index_conversation_message_embedding_use_case=_FakeIndexConversationMessageEmbeddingUseCase(),
        summary_threshold=20,
        check_ai_usage_limit_use_case=_FakeCheckAiUsageLimitUseCase(),
        record_ai_usage_use_case=_FakeRecordAiUsageUseCase(),
    )

    await use_case.execute(
        GenerateAiResponseInput(conversation_id=conversation.id, message_id=user_message.id)
    )

    assert fake_chat_port.received_system_instruction is not None
    assert "258,00" in fake_chat_port.received_system_instruction
    assert "never guess" in fake_chat_port.received_system_instruction.lower()


async def test_generate_ai_response_snapshot_includes_spending_by_category_ranked(
    db_session: AsyncSession, make_user: Any
) -> None:
    """
    Corrige o segundo caso do mesmo bug de produção (2026-08-12): "em qual
    categoria eu mais gastei" também é uma pergunta de agregação que o RAG
    não resolve (baixa similaridade contra o texto de uma transação
    individual) — sem um total por categoria no snapshot, o modelo dizia
    não ter o dado em vez de inventar (a instrução anti-alucinação já
    funcionava), mas ainda não conseguia responder de verdade. O snapshot
    precisa trazer o ranking de categorias do mês, maior gasto primeiro.
    """
    user, _ = await make_user()
    categories = await SqlAlchemyCategoryRepository(db_session).list_visible_to(user.id)
    category_a, category_b = categories[0], categories[1]

    transaction_repository = SqlAlchemyTransactionRepository(db_session)
    today = datetime.now(UTC).date()
    await transaction_repository.create(
        Transaction(
            user_id=user.id,
            category_id=category_a.id,
            type=TransactionType.EXPENSE,
            amount=Money.from_decimal(Decimal("100.00")),
            description="Gasto menor",
            date=today,
        )
    )
    await transaction_repository.create(
        Transaction(
            user_id=user.id,
            category_id=category_b.id,
            type=TransactionType.EXPENSE,
            amount=Money.from_decimal(Decimal("400.00")),
            description="Gasto maior",
            date=today,
        )
    )

    conversation_repository = SqlAlchemyConversationRepository(db_session)
    conversation = await conversation_repository.create(
        Conversation(user_id=user.id, channel=ConversationChannel.WEB)
    )
    user_message = await conversation_repository.add_message(
        ConversationMessage(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Em qual categoria eu mais gastei?",
        )
    )

    fake_chat_port = _FakeChatCompletionPort()
    use_case = GenerateAiResponseUseCase(
        conversation_repository=conversation_repository,
        user_repository=SqlAlchemyUserRepository(db_session),
        transaction_repository=transaction_repository,
        chat_completion_port=fake_chat_port,
        search_relevant_context_use_case=_FakeSearchRelevantContextUseCase(),
        summarize_old_messages_use_case=_FakeSummarizeOldMessagesUseCase(),
        index_conversation_message_embedding_use_case=_FakeIndexConversationMessageEmbeddingUseCase(),
        summary_threshold=20,
        check_ai_usage_limit_use_case=_FakeCheckAiUsageLimitUseCase(),
        record_ai_usage_use_case=_FakeRecordAiUsageUseCase(),
    )

    await use_case.execute(
        GenerateAiResponseInput(conversation_id=conversation.id, message_id=user_message.id)
    )

    instruction = fake_chat_port.received_system_instruction
    assert instruction is not None
    assert "Spending by category" in instruction
    assert f"{category_b.name}: R$ 400,00" in instruction
    assert f"{category_a.name}: R$ 100,00" in instruction
    # maior gasto (category_b) precisa aparecer antes do menor (category_a)
    assert instruction.index(category_b.name) < instruction.index(category_a.name)


async def test_get_or_create_active_conversation_reuses_within_window_and_creates_after(
    db_session: AsyncSession, make_user: Any
) -> None:
    """Janela de continuação de 24h (PRD §6.5): reaproveita dentro da janela, cria nova fora dela."""
    user, _ = await make_user()
    conversation_repository = SqlAlchemyConversationRepository(db_session)
    create_use_case = CreateConversationUseCase(conversation_repository)
    use_case = GetOrCreateActiveConversationUseCase(
        conversation_repository, create_use_case, active_window_hours=24
    )
    input_data = GetOrCreateActiveConversationInput(user_id=user.id, channel=ConversationChannel.WEB)

    none_result = await use_case.execute(input_data, create_if_missing=False)
    assert none_result is None

    created = await use_case.execute(input_data)
    created.last_message_at = datetime.now(UTC)
    created = await conversation_repository.update(created)

    reused = await use_case.execute(input_data)
    assert reused.id == created.id

    created.last_message_at = datetime.now(UTC) - timedelta(hours=25)
    await conversation_repository.update(created)
    new_conversation = await use_case.execute(input_data)
    assert new_conversation.id != created.id


async def test_conversation_messages_return_404_for_another_users_conversation(
    client: AsyncClient, make_user: Any
) -> None:
    """RN-01: conversa de outro usuário deve responder 404, nunca 403 (não revela existência)."""
    _, token_a = await make_user()
    _, token_b = await make_user()

    create_response = await client.post(
        "/api/v1/conversations", headers=auth_headers(token_a)
    )
    assert create_response.status_code == 201
    public_id = create_response.json()["public_id"]

    list_response = await client.get(
        f"/api/v1/conversations/{public_id}/messages", headers=auth_headers(token_b)
    )
    assert list_response.status_code == 404

    send_response = await client.post(
        f"/api/v1/conversations/{public_id}/messages",
        headers=auth_headers(token_b),
        json={"content": "oi"},
    )
    assert send_response.status_code == 404


async def test_delete_conversation_removes_it_and_returns_404_for_another_user(
    client: AsyncClient, make_user: Any
) -> None:
    """RN-01: excluir conversa de outro usuário deve responder 404, não excluir nada."""
    _, token_a = await make_user()
    _, token_b = await make_user()

    create_response = await client.post("/api/v1/conversations", headers=auth_headers(token_a))
    public_id = create_response.json()["public_id"]

    forbidden_delete = await client.delete(
        f"/api/v1/conversations/{public_id}", headers=auth_headers(token_b)
    )
    assert forbidden_delete.status_code == 404

    own_delete = await client.delete(
        f"/api/v1/conversations/{public_id}", headers=auth_headers(token_a)
    )
    assert own_delete.status_code == 204

    list_response = await client.get(
        f"/api/v1/conversations/{public_id}/messages", headers=auth_headers(token_a)
    )
    assert list_response.status_code == 404


async def test_send_message_enqueues_generate_ai_response_job(
    client: AsyncClient, make_user: Any, fake_arq_pool: FakeArqPool
) -> None:
    """POST /messages nunca chama provider de IA — só persiste e enfileira o job (build-context-04 §2.4)."""
    _, token = await make_user()
    create_response = await client.post("/api/v1/conversations", headers=auth_headers(token))
    public_id = create_response.json()["public_id"]

    response = await client.post(
        f"/api/v1/conversations/{public_id}/messages",
        headers=auth_headers(token),
        json={"content": "quanto gastei esse mes?"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["conversation_public_id"] == public_id
    assert body["status"] == "queued"
    assert len(fake_arq_pool.enqueued) == 1
    function_name, _args = fake_arq_pool.enqueued[0]
    assert function_name == "generate_ai_response"


async def test_account_deletion_cascades_conversations_messages_and_embeddings(
    db_session: AsyncSession, make_user: Any
) -> None:
    """RN-03: excluir a conta remove conversations/conversation_messages/embeddings sem rastro."""
    user, _ = await make_user()
    conversation_repository = SqlAlchemyConversationRepository(db_session)
    embedding_repository = SqlAlchemyEmbeddingRepository(db_session)

    conversation = await conversation_repository.create(
        Conversation(user_id=user.id, channel=ConversationChannel.WEB)
    )
    message = await conversation_repository.add_message(
        ConversationMessage(conversation_id=conversation.id, role=MessageRole.USER, content="oi")
    )
    await embedding_repository.upsert(
        Embedding(
            user_id=user.id,
            source_type=EmbeddingSourceType.CONVERSATION_MESSAGE,
            source_id=message.id,
            content="oi",
            embedding=_vector(1),
        )
    )

    await SqlAlchemyUserRepository(db_session).delete(user.id)
    await db_session.flush()

    assert await conversation_repository.get_by_id(conversation.id) is None
    assert await conversation_repository.get_message_by_id(message.id) is None
    remaining = await embedding_repository.search_similar(
        user.id, _vector(1), pool_size=10, threshold=0.0, top_k=10
    )
    assert remaining == []
