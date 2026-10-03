from enum import Enum


class FeedbackChannel(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Canal de origem de um feedback (PRD §6.9) — web (dashboard)
    ou whatsapp (bot). Definido sempre pelo caller do use case, nunca pelo
    usuário final.
    """

    WEB = "web"
    WHATSAPP = "whatsapp"


class FeedbackType(str, Enum):
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Tipo de feedback (build-context-08 §2.2) — chips
    "Elogio/Sugestão/Bug/Outro" do protótipo web. O bot WhatsApp não expõe
    seleção de tipo (sempre `None` na entrada), o use case aplica
    `OTHER` como default nos dois canais.
    """

    PRAISE = "praise"
    SUGGESTION = "suggestion"
    BUG = "bug"
    OTHER = "other"
