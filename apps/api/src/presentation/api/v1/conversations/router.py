from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.conversation.use_cases.create_conversation import (
    CreateConversationInput,
    CreateConversationUseCase,
)
from src.application.conversation.use_cases.delete_conversation import (
    DeleteConversationInput,
    DeleteConversationUseCase,
)
from src.application.conversation.use_cases.get_or_create_active_conversation import (
    GetOrCreateActiveConversationInput,
    GetOrCreateActiveConversationUseCase,
)
from src.application.conversation.use_cases.list_conversation_messages import (
    ListConversationMessagesUseCase,
)
from src.application.conversation.use_cases.list_conversations import ListConversationsUseCase
from src.application.conversation.use_cases.send_message import (
    SendMessageInput,
    SendMessageUseCase,
)
from src.domain.conversation.exceptions import ConversationNotFoundError
from src.domain.conversation.value_objects import ConversationChannel
from src.domain.shared.value_objects import PublicId
from src.domain.user.entities import User
from src.infrastructure.config import get_settings
from src.infrastructure.database.repositories.conversation_repository import (
    SqlAlchemyConversationRepository,
)
from src.infrastructure.database.repositories.embedding_repository import (
    SqlAlchemyEmbeddingRepository,
)
from src.infrastructure.database.session import get_db
from src.infrastructure.queue.pool import get_arq_pool
from src.presentation.api.v1.conversations.schemas import (
    ConversationListResponse,
    ConversationResponse,
    MessageAcceptedResponse,
    MessageCreateRequest,
    MessageListResponse,
)
from src.presentation.api.v1.dependencies.auth import get_current_user

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _parse_conversation_public_id(raw: str) -> PublicId:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Faz o parse do public_id de conversa vindo da URL. Um
    ULID malformado é tratado como "não encontrado" (404), nunca como
    erro de validação — RN-01 (não revelar detalhe interno).
    """
    try:
        return PublicId(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found") from exc


def _get_or_create_active_use_case(db: AsyncSession) -> GetOrCreateActiveConversationUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Fábrica compartilhada por `GET /conversations/active` e
    `POST /conversations/{public_id}/messages` (via SendMessageUseCase) —
    evita duplicar o wiring do use case da janela de 24h nos dois pontos.
    """
    conversation_repository = SqlAlchemyConversationRepository(db)
    create_conversation_use_case = CreateConversationUseCase(conversation_repository)
    return GetOrCreateActiveConversationUseCase(
        conversation_repository,
        create_conversation_use_case,
        active_window_hours=get_settings().CONVERSATION_ACTIVE_WINDOW_HOURS,
    )


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: POST /conversations — cria uma conversa vazia
    (`title=null`), `channel="web"`.
    """
    use_case = CreateConversationUseCase(SqlAlchemyConversationRepository(db))
    conversation = await use_case.execute(
        CreateConversationInput(user_id=current_user.id, channel=ConversationChannel.WEB)
    )
    await db.commit()
    return ConversationResponse.from_entity(conversation)


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: GET /conversations — lista paginada das conversas do
    usuário autenticado, ordenada por `last_message_at DESC NULLS LAST`.
    """
    use_case = ListConversationsUseCase(SqlAlchemyConversationRepository(db))
    result = await use_case.execute(current_user.id, page, page_size)
    return ConversationListResponse.from_result(result, page, page_size)


@router.get("/active", response_model=ConversationResponse | None)
async def get_active_conversation(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ConversationResponse | None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: GET /conversations/active — conversa ativa dentro da
    janela de 24h em modo leitura (`create_if_missing=False`), ou `null`
    se não houver nenhuma — o frontend usa isso para decidir entre
    retomar ou iniciar uma nova ao abrir a tela.
    """
    use_case = _get_or_create_active_use_case(db)
    conversation = await use_case.execute(
        GetOrCreateActiveConversationInput(user_id=current_user.id, channel=ConversationChannel.WEB),
        create_if_missing=False,
    )
    return ConversationResponse.from_entity(conversation) if conversation else None


@router.get("/{public_id}/messages", response_model=MessageListResponse)
async def list_conversation_messages(
    public_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageListResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: GET /conversations/{public_id}/messages — mensagens da
    conversa em ordem cronológica, paginadas.
    """
    use_case = ListConversationMessagesUseCase(SqlAlchemyConversationRepository(db))
    try:
        result = await use_case.execute(
            current_user.id, _parse_conversation_public_id(public_id), page, page_size
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found") from exc
    return MessageListResponse.from_result(result, page, page_size)


@router.post(
    "/{public_id}/messages",
    response_model=MessageAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_message(
    public_id: str,
    payload: MessageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> MessageAcceptedResponse:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: POST /conversations/{public_id}/messages — persiste a
    mensagem do usuário e enfileira `generate_ai_response`; a resposta
    da IA chega depois via WebSocket (`ai_message_ready`/
    `ai_response_failed`, build-context-04 §2.7/§2.8), nunca no corpo
    desta resposta HTTP.
    """
    conversation_repository = SqlAlchemyConversationRepository(db)
    use_case = SendMessageUseCase(
        conversation_repository, _get_or_create_active_use_case(db), arq_pool
    )
    try:
        result = await use_case.execute(
            SendMessageInput(
                user_id=current_user.id,
                content=payload.content,
                conversation_public_id=_parse_conversation_public_id(public_id),
            )
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found") from exc

    await db.commit()
    return MessageAcceptedResponse(
        conversation_public_id=str(result.conversation.public_id),
        message_id=str(result.message.public_id),
    )


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    public_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-12
    Descrição: DELETE /conversations/{public_id} — exclui a conversa e
    os embeddings de suas mensagens (layout replicado do projeto
    irmão: exclusão direta pelo botão do card, sem diálogo de
    confirmação).
    """
    use_case = DeleteConversationUseCase(
        SqlAlchemyConversationRepository(db), SqlAlchemyEmbeddingRepository(db)
    )
    try:
        await use_case.execute(
            DeleteConversationInput(
                user_id=current_user.id, public_id=_parse_conversation_public_id(public_id)
            )
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found") from exc

    await db.commit()
