from datetime import UTC, datetime
from decimal import Decimal

from src.application.reports.use_cases.get_financial_summary import (
    GetFinancialSummaryInput,
    GetFinancialSummaryUseCase,
)
from src.application.whatsapp_bot.dtos import IncomingMessage
from src.domain.reports.value_objects import PeriodRange
from src.domain.transaction.value_objects import Period
from src.domain.user.entities import User
from src.domain.whatsapp_bot.entities import WhatsappSession
from src.domain.whatsapp_bot.ports import MessageCatalogPort
from src.domain.whatsapp_bot.value_objects import BotMode
from src.infrastructure.config import get_settings
from src.infrastructure.security.jwt_service import JwtService


def _format_cents(cents: int) -> str:
    return f"{(Decimal(cents) / 100):.2f}".replace(".", ",")


class HandleReportStateUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-18
    Descrição: Handler do modo Relatório (build-context-07 §2.9,
    reescrito em 2026-08-18 a pedido do usuário) — não responde mais
    perguntas em linguagem natural via IA (Q&A stateless sobre dados
    estruturados, comportamento original de 2026-08-15). Toda vez que o
    usuário entra ou já está no modo Relatório, o bot manda um texto
    curto (total gasto no mês, pra dar contexto rápido) + o link do
    "painel de relatórios" — a mesma tela `/reports` do app web,
    aberta via um token de link mágico (`report_view`, `JwtService`),
    sem precisar logar. Chamado tanto na entrada do modo (delegação de
    `HandleMenuStateUseCase`) quanto em qualquer mensagem subsequente
    enquanto o usuário segue em modo Relatório — o mesmo link (recém-
    emitido a cada chamada) é reenviado sempre, sem distinção entre
    "1ª vez" e "de novo".
    """

    def __init__(
        self,
        get_financial_summary_use_case: GetFinancialSummaryUseCase,
        message_catalog: MessageCatalogPort,
        jwt_service: JwtService,
    ) -> None:
        self._get_financial_summary_use_case = get_financial_summary_use_case
        self._message_catalog = message_catalog
        self._jwt_service = jwt_service

    async def execute(self, user: User, session: WhatsappSession, message: IncomingMessage) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-18
        Descrição: Período sempre o mês corrente (mesma limitação já
        documentada antes desta reescrita — MVP1 não faz parsing de
        período em linguagem natural). `message` não é mais usado pra
        formar uma pergunta pra IA — o parâmetro continua na assinatura
        só pra manter a mesma interface dos outros handlers de estado
        (`ProcessIncomingWhatsappMessageUseCase._dispatch` chama todos
        eles do mesmo jeito).
        """
        session.transition_to(BotMode.REPORT)

        today = datetime.now(UTC).date()
        period = PeriodRange(start=Period(today.year, today.month), end=Period(today.year, today.month))
        summary = await self._get_financial_summary_use_case.execute(
            GetFinancialSummaryInput(user_id=user.id, period=period)
        )

        token = self._jwt_service.create_report_view_token(str(user.id))
        settings = get_settings()
        url = f"{settings.FRONTEND_URL}/reports/shared?token={token}"

        return self._message_catalog.get_message(
            "report.link_message",
            user.language,
            total=_format_cents(summary.total_expense),
            url=url,
        )
