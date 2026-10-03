import uuid
from collections.abc import AsyncGenerator, Callable
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.cache.redis_client import get_redis_client
from src.infrastructure.config import get_settings
from src.infrastructure.database.models.subscription import Subscription as SubscriptionModel
from src.infrastructure.database.models.user import User as UserModel
from src.infrastructure.database.session import get_db
from src.infrastructure.queue.pool import get_arq_pool
from src.infrastructure.security.jwt_service import JwtService
from src.presentation.main import app


class FakeArqPool:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: Substituto de `ArqRedis` para testes — só grava as
    chamadas em memória (`enqueued`), sem tocar o Redis real. Evita dois
    problemas: (1) acoplar testes de negócio ao Redis estar de pé; (2) o
    pool real do `get_arq_pool` é cacheado por processo e fica preso ao
    event loop do primeiro teste que o usa — o `pytest-asyncio` cria um
    event loop novo por teste (`asyncio_mode=auto`), então reusar o pool
    real em testes seguintes derruba com `RuntimeError: Event loop is
    closed`.
    """

    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, function: str, *args: Any) -> None:
        self.enqueued.append((function, args))


class FakeRedisClient:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: Substituto em memória de `redis.asyncio.Redis` para
    testes — implementa só os comandos usados pelo throttle de
    narrativa IA (`INCR`/`EXPIRE`/`TTL`, build-context-05 §2.7), sem
    tocar o Redis real. Mesmo motivo do `FakeArqPool` acima: o cliente
    real cacheado por processo
    (`infrastructure/cache/redis_client.py::get_redis_client`) fica
    preso ao event loop do primeiro teste que o usa, e o
    `pytest-asyncio` cria um event loop novo por teste — sem este fake,
    o 2º teste que tocasse o throttle derrubaria com `RuntimeError:
    Event loop is closed` (bug real, encontrado ao rodar a suíte pela
    primeira vez).
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def expire(self, key: str, seconds: int) -> None:
        return None

    async def ttl(self, key: str) -> int:
        return 60


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Abre uma conexão + transação externa contra o Postgres real
    do docker compose e liga a Session a ela em modo "create_savepoint" —
    cada `db.commit()` feito pelo router vira só um SAVEPOINT, e a
    transação externa é revertida no teardown. Isolamento entre testes sem
    precisar de um banco de teste separado (padrão oficial do SQLAlchemy
    para suíte de testes, ver docs "Joining a Session into an External
    Transaction").
    """
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    connection = await engine.connect()
    outer_transaction = await connection.begin()

    session_factory = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = session_factory()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        await session.close()
        await outer_transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Cliente HTTP assíncrono contra a app FastAPI in-process
    (ASGITransport) — sem subir um servidor real.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(autouse=True)
async def fake_arq_pool() -> AsyncGenerator[FakeArqPool, None]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-11
    Descrição: `autouse` — substitui `get_arq_pool` por `FakeArqPool` em
    todo teste automaticamente (nenhum teste precisa declarar essa
    fixture explicitamente), já que qualquer endpoint que crie/edite/
    exclua transação ou envie mensagem no Agente de IA depende dela
    desde o build-context-04.
    """
    pool = FakeArqPool()
    app.dependency_overrides[get_arq_pool] = lambda: pool
    try:
        yield pool
    finally:
        app.dependency_overrides.pop(get_arq_pool, None)


@pytest_asyncio.fixture(autouse=True)
async def fake_redis_client() -> AsyncGenerator[FakeRedisClient, None]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-14
    Descrição: `autouse` — mesmo espírito de `fake_arq_pool`, substitui
    `get_redis_client` por `FakeRedisClient` em todo teste
    automaticamente.
    """
    redis_client = FakeRedisClient()
    app.dependency_overrides[get_redis_client] = lambda: redis_client
    try:
        yield redis_client
    finally:
        app.dependency_overrides.pop(get_redis_client, None)


@pytest_asyncio.fixture
async def make_user(
    db_session: AsyncSession,
) -> Callable[..., Any]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Factory de usuário de teste — persiste um User real (dentro
    da mesma transação de teste) e devolve o par (model, access_token),
    já que get_current_user faz lookup em banco a partir do JWT. Também
    cria a `Subscription(plan=free)` correspondente (build-context-09
    §2.5 passo 1) — mesma invariante que `RegisterUserUseCase`/
    `LoginWithGoogleUseCase` garantem fora de teste, necessária pra
    qualquer endpoint que dependa de `GetMySubscriptionUseCase`/
    enforcement de plano (Bot WhatsApp, export CSV) não quebrar por
    "usuário sem assinatura" nos testes que criam usuário direto no
    banco em vez de via `POST /auth/register`.
    """

    async def _make_user(*, role: str = "user") -> tuple[UserModel, str]:
        user_id = uuid.uuid4()
        model = UserModel(
            id=user_id,
            name="Test User",
            email=f"user-{user_id.hex[:12]}@example.com",
            password_hash="not-a-real-hash",
            role=role,
            language="pt-BR",
        )
        db_session.add(model)
        await db_session.flush()
        db_session.add(SubscriptionModel(user_id=user_id))
        await db_session.flush()

        token = JwtService().create_access_token(
            user_id=str(user_id), role=role, language="pt-BR"
        )
        return model, token

    return _make_user


def auth_headers(token: str) -> dict[str, str]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-08
    Descrição: Monta o header Authorization Bearer a partir de um access
    token — atalho usado por todos os testes autenticados.
    """
    return {"Authorization": f"Bearer {token}"}
