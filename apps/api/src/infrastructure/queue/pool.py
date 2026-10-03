from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from src.infrastructure.config import get_settings

_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Dependency FastAPI — pool de conexão ARQ/Redis cacheado
    por processo (1ª chamada conecta, chamadas seguintes reaproveitam),
    mesma ideia de `config.py::get_settings` mas sem `@lru_cache`
    (função async, `create_pool` não pode rodar na importação do
    módulo). Primeiro ponto do `api` que enfileira um job — até o
    build-context-04, só o `worker` rodava jobs (via cron).
    """
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().REDIS_URL))
    return _pool
