from src.application.feedback.use_cases.submit_feedback import (
    SubmitFeedbackInput,
    SubmitFeedbackUseCase,
)
from src.application.whatsapp_bot.dtos import IncomingMessage
from src.domain.feedback.value_objects import FeedbackChannel
from src.domain.user.entities import User
from src.domain.whatsapp_bot.entities import WhatsappSession
from src.domain.whatsapp_bot.ports import MessageCatalogPort


class HandleFeedbackStateUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-16
    Descrição: Handler do modo Feedback (build-context-07 §2.8) — sem
    fluxo multi-etapa: captura a mensagem livre, persiste via
    `SubmitFeedbackUseCase` (`channel=whatsapp`, sem tipo/NPS/assunto) e
    força o retorno ao Menu (único estado que não é "sticky",
    build-context-07 §2.3).
    """

    def __init__(
        self, submit_feedback_use_case: SubmitFeedbackUseCase, message_catalog: MessageCatalogPort
    ) -> None:
        self._submit_feedback_use_case = submit_feedback_use_case
        self._message_catalog = message_catalog

    async def execute(self, user: User, session: WhatsappSession, message: IncomingMessage) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: `session.reset_to_menu()` acontece aqui (não no
        orquestrador) porque é uma regra específica deste estado — os
        demais handlers permanecem no próprio modo.
        """
        await self._submit_feedback_use_case.execute(
            SubmitFeedbackInput(
                user_id=user.id, message=message.text or "", channel=FeedbackChannel.WHATSAPP
            )
        )
        session.reset_to_menu()

        thanks = self._message_catalog.get_message("feedback.thanks", user.language)
        menu = self._message_catalog.render_menu(user.language)
        return f"{thanks}\n\n{menu}"
