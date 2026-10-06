from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from src.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    future=True
)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

def create_worker_session_maker() -> async_sessionmaker:
    """
    Session factory for the Celery worker.

    Each task runs its coroutine with a fresh asyncio.run() event loop, so pooled
    connections must not outlive a single loop. NullPool opens a connection per
    session and closes it afterwards, which keeps connections loop-local.
    """
    worker_engine = create_async_engine(settings.DATABASE_URL, echo=settings.SQL_ECHO, poolclass=NullPool)
    return async_sessionmaker(worker_engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
