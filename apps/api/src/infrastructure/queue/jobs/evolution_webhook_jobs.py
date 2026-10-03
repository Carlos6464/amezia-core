from typing import Any

from src.application.evolution.use_cases.apply_connection_update import (
    ApplyConnectionUpdateUseCase,
)
from src.application.evolution.use_cases.apply_qrcode_update import ApplyQrCodeUpdateUseCase
from src.application.evolution.use_cases.record_message_sent import RecordMessageSentUseCase
from src.infrastructure.config import get_settings
from src.infrastructure.database.repositories.sqlalchemy_evolution_instance_repository import (
    SqlAlchemyEvolutionInstanceRepository,
)
from src.infrastructure.database.session import async_session_factory
from src.infrastructure.queue.jobs.whatsapp_jobs import process_incoming_whatsapp_message


async def connection_update(ctx: dict, instance_id: int, payload: dict[str, Any]) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Job ARQ do evento `CONNECTION_UPDATE` (build-context-06
    §2.5) — enfileirado por ReceiveEvolutionWebhookUseCase, roda no
    worker, fora do ciclo da requisição HTTP do webhook (RN-07). Payload
    esperado no formato `{"data": {"state": "open"|"connecting"|"close",
    "owner"?: "<jid>"}}` (contrato padrão da Evolution API v2).
    """
    data = payload.get("data", {})
    raw_state = data.get("state", "close")
    owner = data.get("owner")
    phone_number = owner.split("@")[0] if owner else None

    async with async_session_factory() as session:
        use_case = ApplyConnectionUpdateUseCase(SqlAlchemyEvolutionInstanceRepository(session))
        await use_case.execute(instance_id, raw_state, phone_number)
        await session.commit()


async def qrcode_updated(ctx: dict, instance_id: int, payload: dict[str, Any]) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Job ARQ do evento `QRCODE_UPDATED` (build-context-06
    §2.5). Payload esperado no formato `{"data": {"qrcode": {"base64":
    "..."}}}` (contrato padrão da Evolution API v2) — sem `base64`, o
    evento é ignorado silenciosamente (nada para gravar).
    """
    data = payload.get("data", {})
    qr_code = data.get("qrcode", {}).get("base64") or data.get("base64")
    if qr_code is None:
        return

    async with async_session_factory() as session:
        use_case = ApplyQrCodeUpdateUseCase(
            SqlAlchemyEvolutionInstanceRepository(session),
            get_settings().EVOLUTION_QR_CODE_TTL_SECONDS,
        )
        await use_case.execute(instance_id, qr_code)
        await session.commit()


async def send_message(ctx: dict, instance_id: int, payload: dict[str, Any]) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Job ARQ do evento `SEND_MESSAGE` (build-context-06 §2.5) —
    atualiza `last_message_at` da instância que enviou a mensagem.
    """
    async with async_session_factory() as session:
        use_case = RecordMessageSentUseCase(SqlAlchemyEvolutionInstanceRepository(session))
        await use_case.execute(instance_id)
        await session.commit()


async def dispatch_message_to_bot(ctx: dict, instance_id: int, payload: dict[str, Any]) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Entry point do evento `MESSAGES_UPSERT` (build-context-06
    §2.5) — delega ao pipeline completo do Bot WhatsApp
    (`process_incoming_whatsapp_message`, build-context-07 §2.6) como
    chamada direta em processo, não um novo enfileiramento: este job já
    roda no worker, fora do ciclo da requisição HTTP (RN-07), então um
    segundo round-trip pelo Redis só adicionaria latência sem nenhum
    ganho de desacoplamento real.
    """
    await process_incoming_whatsapp_message(ctx, instance_id, payload)
