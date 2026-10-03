from enum import Enum


class BotMode(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Modo conversacional do Bot WhatsApp (build-context-07
    §2.3) — corresponde ao enum Postgres `whatsapp_bot_mode`. O estado
    Menu não é um membro deste enum: é representado por
    `WhatsappSession.current_state is None`, exatamente como a tabela
    `whatsapp_sessions.current_state` aceita NULL para esse caso.
    """

    EXPENSE = "expense"
    CHAT = "chat"
    REPORT = "report"
    FEEDBACK = "feedback"
