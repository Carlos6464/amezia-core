from enum import Enum


class ConversationChannel(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Canal de origem da conversa — `web` nasce neste
    build-context; `whatsapp` é consumido pelo modo "Chat" do bot
    (build-context-07), que reaproveita este mesmo agregado.
    """

    WEB = "web"
    WHATSAPP = "whatsapp"


class MessageRole(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Papel de quem escreveu a mensagem dentro da conversa —
    não inclui "system": a instrução de sistema (persona + idioma) é
    passada separadamente ao provider via `ChatCompletionPort.complete`,
    nunca persistida como uma ConversationMessage.
    """

    USER = "user"
    ASSISTANT = "assistant"


class AiProvider(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Provider de IA que efetivamente gerou uma resposta —
    persistido em `ConversationMessage.provider_used` (só em mensagens
    assistant) para exibir o badge "Gemini"/"Grok" no frontend.
    """

    GEMINI = "gemini"
    GROK = "grok"
