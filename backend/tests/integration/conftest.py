"""Integration fixtures: a dedicated amadeus_test database.

Tests must never write into the dev database (learned in P5, when conformance
fixtures polluted it). This fixture creates amadeus_test on the compose server,
migrates it via Alembic, and truncates between test modules.
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import create_session_factory

ADMIN_URL = "postgresql+asyncpg://postgres:amadeus@localhost:5433/postgres"
TEST_URL = "postgresql+asyncpg://postgres:amadeus@localhost:5433/amadeus_test"


def _migrate_test_db() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        capture_output=True,
        env={**os.environ, "AMADEUS_DATABASE_URL": TEST_URL},
    )


async def _ensure_test_db() -> None:
    admin = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = 'amadeus_test'")
            )
            if not exists:
                await conn.execute(text("CREATE DATABASE amadeus_test"))
    finally:
        await admin.dispose()


@pytest.fixture(scope="session")
def _test_db() -> None:
    asyncio.run(_ensure_test_db())
    _migrate_test_db()


@pytest.fixture
async def factory(_test_db: None) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(TEST_URL)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()
