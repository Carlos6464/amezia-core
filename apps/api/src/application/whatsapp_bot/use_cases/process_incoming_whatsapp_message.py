import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.application.whatsapp_bot.dtos import IncomingMessage
from src.application.whatsapp_bot.use_cases.handle_chat_state import HandleChatStateUseCase
from src.application.whatsapp_bot.use_cases.handle_expense_state import HandleExpenseStateUseCase
from src.application.whatsapp_bot.use_cases.handle_feedback_state import HandleFeedbackStateUseCase
from src.application.whatsapp_bot.use_cases.handle_menu_state import HandleMenuStateUseCase
from src.application.whatsapp_bot.use_cases.handle_report_state import HandleReportStateUseCase
from src.application.whatsapp_bot.use_cases.reset_to_menu import ResetToMenuUseCase
from src.domain.evolution.repository import EvolutionInstanceRepository
from src.domain.subscription.repository import PlanLimitsRepository, SubscriptionRepository
from src.domain.subscription.services import PlanLimitService
from src.domain.user.entities import User
from src.domain.user.ports import PhoneHasherPort
from src.domain.user.repository import UserRepository
from src.domain.user.value_objects import Language
from src.domain.whatsapp_bot.entities import WhatsappSession
from src.domain.whatsapp_bot.ports import MessageCatalogPort, WhatsappGatewayPort
from src.domain.whatsapp_bot.repository import (
    ProcessedBotMessageRepository,
    WhatsappSessionRepository,
)
from src.domain.whatsapp_bot.value_objects import BotMode

logger = logging.getLogger(__name__)

_MENU_OVERRIDE_KEYWORDS = {"0", "menu"}


def _extract_text(message: dict[str, Any]) -> str | None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Extrai texto de um payload de mensagem Evolution/Baileys —
    `conversation` (caso comum), `extendedTextMessage.text` (mensagem
    com preview de link/citação) ou, aninhado um nível mais fundo,
    `ephemeralMessage.message.extendedTextMessage.text` (mensagem
    temporária). Portado do projeto irmão
    (`/home/adriano/Documentos/projetos/Amezia`), que trata os três
    formatos como observados em produção.
    """
    text = message.get("conversation")
    if isinstance(text, str) and text.strip():
        return text

    extended = message.get("extendedTextMessage")
    if isinstance(extended, dict):
        text = extended.get("text")
        if isinstance(text, str) and text.strip():
            return text

    ephemeral = message.get("ephemeralMessage")
    if isinstance(ephemeral, dict):
        inner_extended = (ephemeral.get("message") or {}).get("extendedTextMessage") or {}
        text = inner_extended.get("text")
        if isinstance(text, str) and text.strip():
            return text

    return None


def _extract_audio(data: dict[str, Any], message: dict[str, Any]) -> IncomingMessage | None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Extrai uma mensagem de áudio — `audioMessage` (comum) ou
    `pttMessage` (nota de voz, algumas versões da Evolution API). Na
    prática, a Evolution raramente embute o base64 do áudio inline no
    payload do webhook, mesmo configurada para isso (achado do projeto
    irmão, DIARIO.md 2026-08-15) — por isso sempre extrai também
    `url`/`mediaKey` do próprio `audioMessage`, para
    `HandleExpenseStateUseCase` poder decriptar direto do CDN do
    WhatsApp quando `audio_base64` vier vazio.
    """
    audio_payload = message.get("audioMessage")
    if not isinstance(audio_payload, dict):
        audio_payload = message.get("pttMessage")
    if not isinstance(audio_payload, dict):
        return None

    audio_base64 = audio_payload.get("base64") or message.get("base64") or data.get("base64")
    return IncomingMessage(
        kind="audio",
        audio_base64=audio_base64 if isinstance(audio_base64, str) else None,
        audio_media_url=audio_payload.get("url"),
        audio_media_key=audio_payload.get("mediaKey"),
        audio_mime_type=audio_payload.get("mimetype") or "audio/ogg",
    )


def _extract_incoming_message(data: dict[str, Any]) -> IncomingMessage | None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Normaliza o payload bruto da Evolution API (formato
    Baileys, build-context-07 §2.5) em `IncomingMessage`. Devolve None
    para tipos de conteúdo que o bot não processa (imagem, figurinha,
    localização, reação, etc.) — ignorados silenciosamente, sem resposta
    (não há capacidade nenhuma do bot pra lidar com esse conteúdo, uma
    mensagem de erro genérica seria mais confusa que útil).
    """
    message = data.get("message") or {}

    text = _extract_text(message)
    if text is not None:
        return IncomingMessage(kind="text", text=text)

    return _extract_audio(data, message)


@dataclass
class ProcessIncomingWhatsappMessageInput:
    instance_id: int
    payload: dict[str, Any]


class ProcessIncomingWhatsappMessageUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Orquestrador completo do Bot WhatsApp (build-context-07
    §2.6) — roda dentro do job ARQ `process_incoming_whatsapp_message`,
    fora do ciclo da requisição HTTP do webhook (RN-07). Idempotência
    (RN-04) é sempre o primeiro efeito colateral; nenhuma chamada de IA
    ou escrita em `whatsapp_sessions` acontece antes dela. Nunca deixa
    uma exceção de handler subir — captura, loga e responde com
    `common.generic_error`, para o job nunca falhar/reprocessar (RN-04:
    a mensagem já foi marcada como processada no passo 1).
    """

    def __init__(
        self,
        processed_bot_message_repository: ProcessedBotMessageRepository,
        whatsapp_session_repository: WhatsappSessionRepository,
        user_repository: UserRepository,
        evolution_instance_repository: EvolutionInstanceRepository,
        whatsapp_gateway: WhatsappGatewayPort,
        phone_hasher: PhoneHasherPort,
        message_catalog: MessageCatalogPort,
        reset_to_menu_use_case: ResetToMenuUseCase,
        handle_menu_state_use_case: HandleMenuStateUseCase,
        handle_expense_state_use_case: HandleExpenseStateUseCase,
        handle_chat_state_use_case: HandleChatStateUseCase,
        handle_report_state_use_case: HandleReportStateUseCase,
        handle_feedback_state_use_case: HandleFeedbackStateUseCase,
        subscription_repository: SubscriptionRepository,
        plan_limits_repository: PlanLimitsRepository,
    ) -> None:
        self._processed_bot_message_repository = processed_bot_message_repository
        self._whatsapp_session_repository = whatsapp_session_repository
        self._user_repository = user_repository
        self._evolution_instance_repository = evolution_instance_repository
        self._whatsapp_gateway = whatsapp_gateway
        self._phone_hasher = phone_hasher
        self._message_catalog = message_catalog
        self._reset_to_menu_use_case = reset_to_menu_use_case
        self._handle_menu_state_use_case = handle_menu_state_use_case
        self._handle_expense_state_use_case = handle_expense_state_use_case
        self._handle_chat_state_use_case = handle_chat_state_use_case
        self._handle_report_state_use_case = handle_report_state_use_case
        self._handle_feedback_state_use_case = handle_feedback_state_use_case
        self._subscription_repository = subscription_repository
        self._plan_limits_repository = plan_limits_repository
        self._plan_limit_service = PlanLimitService()

    async def execute(self, input_data: ProcessIncomingWhatsappMessageInput) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Passo a passo exato do build-context-07 §2.6 — filtra
        eco/grupo, garante idempotência, resolve sessão/usuário, aplica
        TTL e override global "0"/"menu", guarda de áudio, despacha por
        estado e persiste + responde ao final.
        """
        data = input_data.payload.get("data", {})
        key = data.get("key", {})
        whatsapp_message_id = key.get("id")
        remote_jid = key.get("remoteJid", "")
        from_me = bool(key.get("fromMe", False))

        if from_me or not whatsapp_message_id or not remote_jid or remote_jid.endswith("@g.us"):
            return

        inserted = await self._processed_bot_message_repository.try_mark_processed(
            input_data.instance_id, whatsapp_message_id
        )
        if not inserted:
            return

        message = _extract_incoming_message(data)
        if message is None:
            return

        instance = await self._evolution_instance_repository.get_by_id(input_data.instance_id)
        if instance is None:
            return

        remote_phone_number = remote_jid.split("@")[0]
        phone_hash = self._phone_hasher.hash(remote_phone_number)

        session, user = await self._resolve_session_and_user(phone_hash)
        if user is None:
            await self._whatsapp_gateway.send_text(
                instance.name,
                remote_phone_number,
                self._message_catalog.get_message("common.unlinked_number", Language.PT_BR),
            )
            return
        assert session is not None
        await self._processed_bot_message_repository.set_user_id(
            input_data.instance_id, whatsapp_message_id, user.id
        )

        now = datetime.now(UTC)
        if session.is_expired(now):
            session.reset_to_menu()

        if message.kind == "text" and (message.text or "").strip().lower() in _MENU_OVERRIDE_KEYWORDS:
            reply_text = await self._reset_to_menu_use_case.execute(session, user.language)
            await self._finish(session, now, instance.name, remote_phone_number, reply_text)
            return

        if message.kind == "audio" and session.current_state != BotMode.EXPENSE:
            reply_text = self._message_catalog.get_message("common.audio_not_supported", user.language)
            await self._finish(session, now, instance.name, remote_phone_number, reply_text)
            return

        limit_reached_reply = await self._check_plan_limit(user)
        if limit_reached_reply is not None:
            await self._finish(session, now, instance.name, remote_phone_number, limit_reached_reply)
            return

        try:
            reply_text = await self._dispatch(user, session, message)
        except Exception:
            logger.exception("WhatsApp bot state handler failed (user_id=%s)", user.id)
            reply_text = self._message_catalog.get_message("common.generic_error", user.language)

        await self._finish(session, now, instance.name, remote_phone_number, reply_text)

    async def _resolve_session_and_user(
        self, phone_hash: str
    ) -> tuple[WhatsappSession | None, User | None]:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Caminho rápido (sessão já existe) ou fallback via
        `UserRepository.get_by_phone_hash` + criação da 1ª sessão
        (build-context-07 §2.6, passo 3). `user=None` sinaliza "número
        sem usuário vinculado" para `execute()` responder e encerrar sem
        criar sessão (RN-06).
        """
        session = await self._whatsapp_session_repository.get_by_phone_hash(phone_hash)
        if session is not None:
            user = await self._user_repository.get_by_id(session.user_id)
            return session, user

        user = await self._user_repository.get_by_phone_hash(phone_hash)
        if user is None:
            return None, None

        created_session = await self._whatsapp_session_repository.create(
            WhatsappSession(user_id=user.id, phone_hash=phone_hash)
        )
        return created_session, user

    async def _check_plan_limit(self, user: User) -> str | None:
        """
        Autor: Carlos Adriano
        Data: 2026-09-10
        Descrição: Enforcement do limite mensal de mensagens do Bot
        (build-context-09 §2.6, RN-06 revisada) — conta
        `processed_bot_messages` do usuário desde o início do mês atual
        (a mensagem sendo processada agora já está contada, inserida no
        passo de idempotência) e compara com
        `PlanLimits.whatsapp_bot_messages_per_month` do plano efetivo.
        `None` = dentro do limite, `str` = mensagem de upgrade a
        responder em vez de despachar por estado. Ilimitado
        (`limit is None`, Pro/Premium) nunca conta no banco à toa.
        """
        subscription = await self._subscription_repository.get_by_user_id(user.id)
        if subscription is None:
            return None
        plan_limits = await self._plan_limits_repository.get_by_plan(
            subscription.resolve_effective_plan()
        )
        if plan_limits is None:
            return None

        limit = self._plan_limit_service.whatsapp_bot_message_limit(plan_limits)
        if limit is None:
            return None

        month_start = datetime.now(UTC).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        count = await self._processed_bot_message_repository.count_for_user_since(
            user.id, month_start
        )
        if count <= limit:
            return None
        return self._message_catalog.get_message("common.plan_limit_reached", user.language)

    async def _dispatch(
        self, user: User, session: WhatsappSession, message: IncomingMessage
    ) -> str:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Despacha para o handler do estado atual —
        `current_state is None` é o Menu (build-context-07 §2.3).
        """
        if session.current_state is None:
            return await self._handle_menu_state_use_case.execute(user, session, message)
        if session.current_state == BotMode.EXPENSE:
            return await self._handle_expense_state_use_case.execute(user, session, message)
        if session.current_state == BotMode.CHAT:
            return await self._handle_chat_state_use_case.execute(user, session, message)
        if session.current_state == BotMode.REPORT:
            return await self._handle_report_state_use_case.execute(user, session, message)
        return await self._handle_feedback_state_use_case.execute(user, session, message)

    async def _finish(
        self,
        session: WhatsappSession,
        now: datetime,
        instance_name: str,
        remote_phone_number: str,
        reply_text: str,
    ) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Passo final comum a toda mensagem processada
        (build-context-07 §2.6, passo 9) — `touch` + persiste a sessão
        antes de enviar a resposta, para o estado nunca ficar
        desatualizado mesmo se o envio falhar. O envio em si
        (`send_text`) é isolado num `try/except` próprio (2026-08-16) —
        sem isso, uma falha da Evolution API neste último passo (a
        própria API fora do ar, timeout, alguma peculiaridade de payload
        ainda não descoberta) derrubava o job **depois** da idempotência
        já ter marcado a mensagem como processada (RN-04): sem retry
        possível e sem log específico, o usuário simplesmente nunca via
        resposta nenhuma. Mesmo espírito do `try/except` em volta de
        `_dispatch()` — nunca deixar uma falha de I/O externo virar
        exceção não tratada neste orquestrador.
        """
        session.touch(now)
        await self._whatsapp_session_repository.update(session)
        try:
            await self._whatsapp_gateway.send_text(instance_name, remote_phone_number, reply_text)
        except Exception:
            logger.exception(
                "Failed to send WhatsApp reply (user_id=%s, phone=%s)",
                session.user_id,
                remote_phone_number,
            )
