import json
import uuid
from typing import Any

from redis.asyncio import Redis

from src.infrastructure.config import get_settings

_redis: Redis | None = None


def _get_redis() -> Redis:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Cliente Redis assíncrono cacheado por processo — usado só
    pelo lado `worker` da ponte Pub/Sub (build-context-04 §2.8).
    """
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().REDIS_URL)
    return _redis


async def publish_to_user(user_id: uuid.UUID, payload: dict[str, Any]) -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Publica um evento no canal Redis `ws:user:{user_id}` —
    lado `worker` da ponte Pub/Sub. O `api` (que mantém as conexões
    WebSocket de verdade) assina esse canal via
    `presentation/websocket/redis_subscriber.py` e repassa para o
    cliente. Necessário porque `api` e `worker` são containers/processos
    separados que não compartilham memória (build-context-04 §2.8).
    """
    channel = f"ws:user:{user_id}"
    await _get_redis().publish(channel, json.dumps(payload))
