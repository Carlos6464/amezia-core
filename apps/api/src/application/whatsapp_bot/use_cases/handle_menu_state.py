from src.application.whatsapp_bot.dtos import IncomingMessage
from src.application.whatsapp_bot.use_cases.handle_report_state import HandleReportStateUseCase
from src.domain.user.entities import User
from src.domain.whatsapp_bot.entities import WhatsappSession
from src.domain.whatsapp_bot.ports import MessageCatalogPort
from src.domain.whatsapp_bot.value_objects import BotMode

_OPTION_TO_MODE: dict[str, BotMode] = {
    "1": BotMode.EXPENSE,
    "registrar": BotMode.EXPENSE,
    "2": BotMode.CHAT,
    "chat": BotMode.CHAT,
    "3": BotMode.REPORT,
    "relatorio": BotMode.REPORT,
    "relatório": BotMode.REPORT,
    "4": BotMode.FEEDBACK,
    "feedback": BotMode.FEEDBACK,
}

_ENTERED_MESSAGE_KEY: dict[BotMode, str] = {
    BotMode.EXPENSE: "expense.entered",
    BotMode.CHAT: "chat.entered",
    BotMode.FEEDBACK: "feedback.prompt",
}


class HandleMenuStateUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Interpreta a entrada do usuário no estado Menu
    (build-context-07 §2.3) — número 1-4 ou palavra-chave transiciona
    para o modo correspondente; qualquer outra entrada reenvia o menu
    com uma nota de "não entendi".
    """

    def __init__(
        self,
        message_catalog: MessageCatalogPort,
        handle_report_state_use_case: HandleReportStateUseCase,
    ) -> None:
        self._message_catalog = message_catalog
        self._handle_report_state_use_case = handle_report_state_use_case

    async def execute(self, user: User, session: WhatsappSession, message: IncomingMessage) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Mensagem chega sempre como texto neste estado — o
        guard de áudio (`ProcessIncomingWhatsappMessageUseCase`) já
        garante isso antes do dispatch, já que o Menu não é o modo
        `expense`. Entrar no modo Relatório (2026-08-18) delega direto
        pra `HandleReportStateUseCase` — o texto+link do painel é
        montado lá, e é o mesmo handler que responde a qualquer
        mensagem seguinte enquanto o usuário segue nesse modo; assim a
        lógica de gerar o link mágico existe num único lugar.
        """
        choice = (message.text or "").strip().lower()
        mode = _OPTION_TO_MODE.get(choice)

        if mode is None:
            invalid_notice = self._message_catalog.get_message("menu.invalid_option", user.language)
            return f"{invalid_notice}\n\n{self._message_catalog.render_menu(user.language)}"

        if mode == BotMode.REPORT:
            return await self._handle_report_state_use_case.execute(user, session, message)

        session.transition_to(mode)
        return self._message_catalog.get_message(_ENTERED_MESSAGE_KEY[mode], user.language)
