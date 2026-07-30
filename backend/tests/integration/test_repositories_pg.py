"""Postgres conformance — the same assertions as the unit suite, against the real
compose DB (docker compose up -d db && alembic upgrade head first).
"""

import uuid

import pytest

from app.config import get_settings
from app.db import create_engine, create_session_factory, session_scope
from app.models import Candidate
from app.repositories.postgres import (
    PgConversationRepository,
    PgCredentialRepository,
    PgDocumentRepository,
)
from tests.unit.test_repositories import (
    assert_conversation_contract,
    assert_credential_contract,
    assert_document_contract,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def factory():  # type: ignore[no-untyped-def]
    engine = create_engine(get_settings())
    yield create_session_factory(engine)
    await engine.dispose()


async def make_candidate(factory) -> uuid.UUID:  # type: ignore[no-untyped-def]
    async with session_scope(factory) as session:
        row = Candidate(name=f"test-{uuid.uuid4().hex[:8]}", contact={})
        session.add(row)
        await session.flush()
        return row.id


async def test_pg_conversation_contract(factory) -> None:  # type: ignore[no-untyped-def]
    await assert_conversation_contract(PgConversationRepository(factory))


async def test_pg_credential_contract(factory) -> None:  # type: ignore[no-untyped-def]
    candidate_id = await make_candidate(factory)
    await assert_credential_contract(PgCredentialRepository(factory), candidate_id)


async def test_pg_document_contract(factory) -> None:  # type: ignore[no-untyped-def]
    candidate_id = await make_candidate(factory)
    await assert_document_contract(PgDocumentRepository(factory), candidate_id)
