from redis.asyncio import Redis

from src.infrastructure.config import get_settings

_redis: Redis | None = None


async def get_redis_client() -> Redis:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Cliente Redis assíncrono cacheado por processo — mesma
    ideia de `infrastructure/queue/pool.py::get_arq_pool`, mas para uso
    direto de comandos Redis (não fila ARQ). Primeiro consumidor: o
    throttle de narrativa IA (`reports/dependencies.py`,
    build-context-05 §2.7). Fica separado do cliente privado de
    `infrastructure/queue/ws_publisher.py` (lado Pub/Sub do `worker`) por
    serem processos/contextos diferentes (dependency do `api`, não job do
    `worker`).
    """
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().REDIS_URL)
    return _redis
