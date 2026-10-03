from datetime import datetime

from pydantic import BaseModel, Field

from src.application.conversation.dtos import ConversationListResult, ConversationMessageListResult
from src.domain.conversation.entities import Conversation, ConversationMessage

PREVIEW_LENGTH = 80


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ConversationMessageResponse(BaseModel):
    public_id: str
    role: str
    content: str
    provider_used: str | None
    created_at: datetime

    @classmethod
    def from_entity(cls, message: ConversationMessage) -> "ConversationMessageResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Converte a entidade de domínio ConversationMessage no
        schema de resposta HTTP.
        """
        return cls(
            public_id=str(message.public_id),
            role=message.role.value,
            content=message.content,
            provider_used=message.provider_used.value if message.provider_used else None,
            created_at=message.created_at,
        )


class ConversationResponse(BaseModel):
    public_id: str
    title: str | None
    channel: str
    last_message_at: datetime | None
    last_message_preview: str | None
    created_at: datetime

    @classmethod
    def from_entity(
        cls, conversation: Conversation, last_message: ConversationMessage | None = None
    ) -> "ConversationResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Converte a entidade de domínio Conversation no schema
        de resposta HTTP — `last_message_preview` (truncado a
        `PREVIEW_LENGTH`) alimenta o trecho exibido na lista lateral do
        frontend (build-context-04 §3.2), sem o cliente precisar
        carregar as mensagens de cada conversa só para montar a lista.
        """
        preview = None
        if last_message is not None:
            preview = last_message.content[:PREVIEW_LENGTH]
            if len(last_message.content) > PREVIEW_LENGTH:
                preview += "…"
        return cls(
            public_id=str(conversation.public_id),
            title=conversation.title,
            channel=conversation.channel.value,
            last_message_at=conversation.last_message_at,
            last_message_preview=preview,
            created_at=conversation.created_at,
        )


class PaginationInfo(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


def _total_pages(total: int, page_size: int) -> int:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Divisão de teto (ceiling division) — número de páginas
    necessário para cobrir `total` itens a `page_size` por página.
    """
    return (total + page_size - 1) // page_size if page_size else 0


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    pagination: PaginationInfo

    @classmethod
    def from_result(
        cls, result: ConversationListResult, page: int, page_size: int
    ) -> "ConversationListResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Converte o resultado de ListConversationsUseCase na
        resposta HTTP paginada.
        """
        return cls(
            items=[
                ConversationResponse.from_entity(item.conversation, item.last_message)
                for item in result.items
            ],
            pagination=PaginationInfo(
                page=page, page_size=page_size, total=result.total, total_pages=_total_pages(
                    result.total, page_size
                )
            ),
        )


class MessageListResponse(BaseModel):
    items: list[ConversationMessageResponse]
    pagination: PaginationInfo

    @classmethod
    def from_result(
        cls, result: ConversationMessageListResult, page: int, page_size: int
    ) -> "MessageListResponse":
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: Converte o resultado de ListConversationMessagesUseCase
        na resposta HTTP paginada, em ordem cronológica.
        """
        return cls(
            items=[ConversationMessageResponse.from_entity(message) for message in result.items],
            pagination=PaginationInfo(
                page=page, page_size=page_size, total=result.total, total_pages=_total_pages(
                    result.total, page_size
                )
            ),
        )


class MessageAcceptedResponse(BaseModel):
    conversation_public_id: str
    message_id: str
    status: str = "queued"
