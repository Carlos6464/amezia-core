import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.conversation.value_objects import AiProvider, ConversationChannel, MessageRole
from src.domain.shared.value_objects import PublicId


@dataclass
class Conversation:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Aggregate root do módulo de Agente de IA (DDD tático,
    PRD §5) — garante a consistência do agregado: uma ConversationMessage
    só nasce através de um use case que passa pela conversa (ex.:
    SendMessageUseCase/GenerateAiResponseUseCase), nunca criada isolada
    diretamente no repositório de mensagens. `title`/`summary` ficam
    `None` até a 1ª resposta da IA e até a conversa acumular mensagens
    suficientes para comprimir (build-context-04 §2.4), respectivamente.
    """

    user_id: uuid.UUID
    channel: ConversationChannel = ConversationChannel.WEB
    title: str | None = None
    summary: str | None = None
    summarized_until_message_id: int | None = None
    last_message_at: datetime | None = None
    id: int | None = None
    public_id: PublicId = field(default_factory=PublicId.generate)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ConversationMessage:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Uma mensagem (usuário ou assistente) dentro de uma
    Conversation. `provider_used` só é preenchido em mensagens
    `role=assistant` — indica qual provider (Gemini ou Grok) gerou o
    texto (build-context-04 §2.5).
    """

    conversation_id: int
    role: MessageRole
    content: str
    provider_used: AiProvider | None = None
    id: int | None = None
    public_id: PublicId = field(default_factory=PublicId.generate)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
