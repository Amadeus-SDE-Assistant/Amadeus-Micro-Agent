"""Async SQLAlchemy engine/session plumbing."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    # SPEC §10: every outbound call bounded. pool_pre_ping transparently replaces
    # dead pooled connections (the practical retry mechanism); connect_args bound
    # connection establishment and statement runtime at the asyncpg level.
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"timeout": 5, "command_timeout": 15},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


async def check_db(engine: AsyncEngine, probe_seconds: float = 2.0) -> bool:
    """Truthful liveness probe for /api/health (SPEC §10)."""
    try:
        async with asyncio.timeout(probe_seconds), engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
