from typing import Protocol


class JobEnqueuer(Protocol):
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Porta de aplicação para enfileirar jobs assíncronos (ARQ)
    a partir de um use case — implementada estruturalmente por
    `arq.connections.ArqRedis` (injetada via
    `infrastructure/queue/pool.py::get_arq_pool`), sem a application
    layer importar o SDK do ARQ diretamente. Primeiro uso a partir do
    build-context-04 (`SendMessageUseCase`, indexação de embeddings).
    """

    async def enqueue_job(self, function: str, *args: object) -> object: ...
