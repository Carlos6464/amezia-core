import logging
import secrets
from dataclasses import dataclass
from typing import Any

from src.application.shared.ports import JobEnqueuer
from src.domain.evolution.exceptions import (
    EvolutionInstanceNotFoundError,
    InvalidWebhookSignatureError,
)
from src.domain.evolution.repository import EvolutionInstanceRepository
from src.domain.shared.value_objects import PublicId

logger = logging.getLogger(__name__)

_EVENT_JOB_MAP = {
    "CONNECTION_UPDATE": "connection_update",
    "QRCODE_UPDATED": "qrcode_updated",
    "SEND_MESSAGE": "send_message",
    "MESSAGES_UPSERT": "dispatch_message_to_bot",
}


@dataclass
class ReceiveEvolutionWebhookInput:
    instance_public_id: PublicId
    secret: str
    event: str
    payload: dict[str, Any]


class ReceiveEvolutionWebhookUseCase:
    """
    Autor: Carlos Adriano
    Data: 2026-08-15
    Descrição: Valida a instância + `webhook_secret` (RN-07, build-context-06
    §2.5) e enfileira o job ARQ correspondente ao evento — nunca processa
    nada de forma síncrona. A comparação do secret usa
    `secrets.compare_digest` (tempo constante), evitando um timing attack
    contra o valor real. Eventos fora de `_EVENT_JOB_MAP` são
    silenciosamente ignorados (nenhum job enfileirado), mas ainda contam
    como recebidos com sucesso — a Evolution API não deveria receber erro
    por mandar um evento que este módulo não trata.
    """

    def __init__(
        self, evolution_instance_repository: EvolutionInstanceRepository, job_enqueuer: JobEnqueuer
    ) -> None:
        self._repository = evolution_instance_repository
        self._job_enqueuer = job_enqueuer

    async def execute(self, data: ReceiveEvolutionWebhookInput) -> None:
        """
        Autor: Carlos Adriano
        Data: 2026-08-15
        Descrição: Valida instância + secret (tempo constante) e
        enfileira o job do evento correspondente — nunca processa nada
        de forma síncrona (RN-07). `event` é normalizado
        (`"messages.upsert"` → `"MESSAGES_UPSERT"`) antes de bater contra
        `_EVENT_JOB_MAP`: a instância Evolution real deste projeto manda
        o nome do evento em minúsculo com ponto, não no formato
        `SCREAMING_SNAKE_CASE` usado para *assinar* os eventos em
        `EvolutionApiClient.set_webhook` — confirmado em 2026-08-16 (log
        de diagnóstico: `event='messages.upsert'`), mesmo tipo de
        inconsistência de payload já visto no `set_webhook`/`send_text`.
        """
        instance = await self._repository.get_by_public_id(data.instance_public_id)
        if instance is None:
            raise EvolutionInstanceNotFoundError(str(data.instance_public_id))
        if not secrets.compare_digest(data.secret, instance.webhook_secret):
            raise InvalidWebhookSignatureError()

        normalized_event = data.event.upper().replace(".", "_")
        job_name = _EVENT_JOB_MAP.get(normalized_event)
        if job_name is not None:
            await self._job_enqueuer.enqueue_job(job_name, instance.id, data.payload)
        else:
            logger.info(
                "Evolution webhook event not in _EVENT_JOB_MAP, ignored: event=%r normalized=%r",
                data.event,
                normalized_event,
            )
