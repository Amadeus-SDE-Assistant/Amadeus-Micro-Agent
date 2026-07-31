"""Postgres conformance — the same assertions as the unit suite, against the real
compose DB (docker compose up -d db && alembic upgrade head first).
"""

import uuid

import pytest

from app.db import session_scope
from app.models import Candidate
from app.repositories.base import JobIn
from app.repositories.postgres import (
    PgApplicationRepository,
    PgApprovalRepository,
    PgConversationRepository,
    PgCredentialRepository,
    PgDocumentRepository,
    PgJobRepository,
    PgProfileRepository,
)
from tests.unit.test_repositories import (
    assert_application_contract,
    assert_conversation_contract,
    assert_credential_contract,
    assert_document_contract,
    assert_job_contract,
    assert_profile_contract,
)

pytestmark = pytest.mark.integration


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


async def test_pg_job_contract(factory) -> None:  # type: ignore[no-untyped-def]
    await assert_job_contract(PgJobRepository(factory))


async def test_pg_application_contract(factory) -> None:  # type: ignore[no-untyped-def]
    candidate_id = await make_candidate(factory)
    job = await PgJobRepository(factory).add(JobIn(title="x", company="y"))
    await assert_application_contract(PgApplicationRepository(factory), candidate_id, job.id)


async def test_pg_profile_contract(factory) -> None:  # type: ignore[no-untyped-def]
    candidate_id = await make_candidate(factory)
    await assert_profile_contract(PgProfileRepository(factory), candidate_id)


async def test_pg_approval_contract(factory) -> None:  # type: ignore[no-untyped-def]
    repo = PgApprovalRepository(factory)
    approval_id = await repo.create(
        "mcp__jobseeker__resume_store", "Save your resume?", {"resume_text": "x"}
    )
    assert await repo.decide(approval_id, "approved") is True
    assert await repo.decide(approval_id, "denied") is False  # already decided
    assert await repo.decide(uuid.uuid4(), "approved") is False  # unknown
