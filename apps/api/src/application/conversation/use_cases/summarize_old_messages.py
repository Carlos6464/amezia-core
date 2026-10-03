from src.domain.conversation.entities import Conversation, ConversationMessage
from src.domain.conversation.ports import ChatCompletionPort, ChatMessage
from src.domain.conversation.repository import ConversationRepository
from src.domain.conversation.value_objects import MessageRole

_SUMMARY_SYSTEM_INSTRUCTION = (
    "You summarize personal-finance chat conversations. Combine the previous summary "
    "(if any) with the new messages below into a single concise summary, a few "
    "sentences long, preserving facts, numbers and decisions relevant for future "
    "context. Reply with only the summary text, no preamble."
)


def _build_summary_prompt(previous_summary: str | None, messages: list[ConversationMessage]) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Monta o texto enviado ao provider para gerar o novo
    resumo — combina o resumo anterior (se houver) com o trecho de
    mensagens a incorporar.
    """
    lines: list[str] = []
    if previous_summary:
        lines.append(f"Previous summary:\n{previous_summary}\n")
    lines.append("New messages:")
    for message in messages:
        speaker = "User" if message.role == MessageRole.USER else "Assistant"
        lines.append(f"{speaker}: {message.content}")
    return "\n".join(lines)


class SummarizeOldMessagesUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Mecanismo de "memória comprimida" (PRD §6.5) — comprime as
    mensagens mais antigas ainda não resumidas, exceto uma janela recente
    (`recent_window_size`, continua verbatim no prompt), num novo
    `summary`, avançando `summarized_until_message_id`. Evita que
    conversas longas estourem o contexto do prompt (build-context-04
    §2.4).
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        chat_completion_port: ChatCompletionPort,
        recent_window_size: int = 10,
    ) -> None:
        self._conversation_repository = conversation_repository
        self._chat_completion_port = chat_completion_port
        self._recent_window_size = recent_window_size

    async def execute(
        self, conversation: Conversation, unsummarized_messages: list[ConversationMessage]
    ) -> Conversation:
        """
        Autor: Carlos Adriano
        Data: 2026-08-11
        Descrição: `unsummarized_messages` já vem ordenada
        cronologicamente (mais antiga primeiro). As últimas
        `recent_window_size` mensagens ficam de fora do trecho
        resumido — continuam verbatim no prompt até virarem "antigas"
        também, num ciclo seguinte.
        """
        to_summarize = unsummarized_messages[: -self._recent_window_size]
        if not to_summarize:
            return conversation

        prompt = _build_summary_prompt(conversation.summary, to_summarize)
        result = await self._chat_completion_port.complete(
            system_instruction=_SUMMARY_SYSTEM_INSTRUCTION,
            messages=[ChatMessage(role=MessageRole.USER, content=prompt)],
        )

        conversation.summary = result.content
        conversation.summarized_until_message_id = to_summarize[-1].id
        return await self._conversation_repository.update(conversation)
