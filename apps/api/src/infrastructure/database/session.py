from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Autor: Carlos Adriano
    Data: 2026-08-06
    Descrição: Dependency do FastAPI que abre uma AsyncSession por requisição
    e garante o fechamento mesmo em caso de exceção.
    """
    async with async_session_factory() as session:
        yield session
