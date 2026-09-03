import asyncio
import os

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DEFAULT_DATABASE_URL = "postgresql+asyncpg://localhost/agent_office"

COMMIT_LOCK = asyncio.Lock()


def build_engine(database_url: str | None = None) -> AsyncEngine:
    url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return create_async_engine(url, pool_pre_ping=True)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def commit(db: AsyncSession) -> None:
    """The whole app shares one AsyncSession per unit of work, and background-task-driven runs commit on it too: every writer must go through this same lock, not just RuntimeService's own callers, or two commits can interleave mid-flush."""
    async with COMMIT_LOCK:
        await db.commit()
