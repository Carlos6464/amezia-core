from src.domain.user.value_objects import Language
from src.domain.whatsapp_bot.entities import WhatsappSession
from src.domain.whatsapp_bot.ports import MessageCatalogPort


class ResetToMenuUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Volta a sessão ao estado Menu e monta o texto do Menu no
    idioma do usuário (build-context-07 §2.8) — usado pelo TTL de 30min
    e pelo override global "0"/"menu" (§2.6, passos 4-5). Não persiste a
    sessão: quem chama (`ProcessIncomingWhatsappMessageUseCase`) faz o
    `touch`/`update` uma única vez, ao final do processamento.
    """

    def __init__(self, message_catalog: MessageCatalogPort) -> None:
        self._message_catalog = message_catalog

    async def execute(self, session: WhatsappSession, language: Language) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: `session.reset_to_menu()` é idempotente — chamar de
        novo numa sessão já no Menu não tem efeito colateral.
        """
        session.reset_to_menu()
        return self._message_catalog.render_menu(language)
