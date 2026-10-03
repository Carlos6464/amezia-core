from typing import ClassVar

from arq import cron
from arq.connections import RedisSettings

from src.infrastructure.config import get_settings
from src.infrastructure.queue.jobs.evolution_webhook_jobs import (
    connection_update,
    dispatch_message_to_bot,
    qrcode_updated,
    send_message,
)
from src.infrastructure.queue.jobs.generate_ai_narrative_job import generate_ai_narrative_job
from src.infrastructure.queue.jobs.generate_ai_response import generate_ai_response
from src.infrastructure.queue.jobs.index_category_embedding import (
    delete_category_embedding,
    index_category_embedding,
)
from src.infrastructure.queue.jobs.index_transaction_embedding import (
    delete_transaction_embedding,
    index_transaction_embedding,
)
from src.infrastructure.queue.jobs.recurring_transactions import generate_recurring_transactions
from src.infrastructure.queue.jobs.whatsapp_jobs import (
    process_incoming_whatsapp_message,
    send_whatsapp_welcome_message,
)

settings = get_settings()


class WorkerSettings:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Configuração base do worker ARQ. `generate_ai_response` e
    `index_transaction_embedding`/`delete_transaction_embedding` são os
    primeiros jobs reais do projeto (build-context-04) — a function
    `noop` (placeholder da fundação, build-context-00) foi removida
    aqui, já não é mais necessária. `cron_jobs` nasce no build-context-03
    (2026-08-09) com o primeiro job agendado do projeto.
    `generate_ai_narrative_job` (build-context-05) reaproveita o mesmo
    padrão de job assíncrono + WebSocket do módulo de Relatórios.
    `connection_update`/`qrcode_updated`/`send_message`/
    `dispatch_message_to_bot` (build-context-06) processam os eventos do
    webhook da Evolution API fora do ciclo da requisição HTTP (RN-07).
    `process_incoming_whatsapp_message` (build-context-07) é o pipeline
    dos 5 modos do bot — chamado diretamente por `dispatch_message_to_bot`
    (mesmo job, sem um segundo enfileiramento), registrado aqui também
    para poder ser invocado via ARQ de forma independente se necessário.
    `send_whatsapp_welcome_message` (2026-08-16) é enfileirado por
    `UpdateProfileUseCase` sempre que o usuário vincula/troca o número de
    WhatsApp no perfil. `index_category_embedding` (build-context-12,
    2026-09-09) é enfileirado por `CreateCategoryUseCase`/
    `UpdateCategoryUseCase` sempre que uma categoria é criada ou
    renomeada, base da checagem de duplicata semântica no bot.
    """

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions: ClassVar[list] = [
        generate_ai_response,
        index_transaction_embedding,
        delete_transaction_embedding,
        index_category_embedding,
        delete_category_embedding,
        generate_ai_narrative_job,
        connection_update,
        qrcode_updated,
        send_message,
        dispatch_message_to_bot,
        process_incoming_whatsapp_message,
        send_whatsapp_welcome_message,
    ]
    cron_jobs: ClassVar[list] = [cron(generate_recurring_transactions, hour=3, minute=0)]
