from dataclasses import dataclass

from src.domain.conversation.entities import Conversation, ConversationMessage


@dataclass
class ConversationSummary:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Par Conversation + sua última mensagem (se houver) — usado
    pela listagem (`GET /conversations`) para exibir o trecho de prévia
    sem o frontend precisar carregar as mensagens de cada conversa.
    """

    conversation: Conversation
    last_message: ConversationMessage | None


@dataclass
class ConversationListResult:
    items: list[ConversationSummary]
    total: int


@dataclass
class ConversationMessageListResult:
    items: list[ConversationMessage]
    total: int
