import json
import logging

from redis.asyncio import Redis

from src.infrastructure.config import get_settings
from src.presentation.websocket.manager import manager

logger = logging.getLogger(__name__)

CHANNEL_PATTERN = "ws:user:*"


async def listen_for_ws_events() -> None:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Task de background do processo `api` (iniciada no
    `lifespan` de `main.py`) — assina o padrão Redis Pub/Sub
    `ws:user:*`, publicado pelo `worker` via
    `infrastructure/queue/ws_publisher.py`, e repassa cada evento para
    as conexões WebSocket abertas do usuário correspondente via
    `ConnectionManager.send_to_user`. É a ponte que permite ao `worker`
    empurrar respostas de IA assíncronas para o cliente sem os dois
    processos compartilharem memória (build-context-04 §2.8).
    """
    redis = Redis.from_url(get_settings().REDIS_URL)
    pubsub = redis.pubsub()
    await pubsub.psubscribe(CHANNEL_PATTERN)
    try:
        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue
            try:
                channel = _decode(message["channel"])
                user_id = channel.removeprefix("ws:user:")
                payload = json.loads(_decode(message["data"]))
                await manager.send_to_user(user_id, payload)
            except Exception:
                logger.warning("Failed to process ws pub/sub message", exc_info=True)
    finally:
        await pubsub.punsubscribe(CHANNEL_PATTERN)
        await pubsub.aclose()
        await redis.aclose()


def _decode(value: bytes | str) -> str:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: O client Redis devolve `bytes` por padrão — normaliza
    para `str` antes de fazer parse do canal/payload.
    """
    return value.decode() if isinstance(value, bytes) else value
