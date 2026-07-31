"""job_capture (SPEC §15 T12.4): pasted job text -> extraction -> stored Job.

The approval gate itself is tested in test_approval_gate.py; this covers the
capability body only, with extract_job faked to avoid a real LLM call.
"""

import uuid
from typing import Any

import pytest

from app.capabilities.context import CapabilityContext, set_capability_context
from app.capabilities.job_capture import job_capture
from app.ingestion.job_extract import JobExtractionError
from app.repositories.base import JobIn
from app.repositories.memory import MemoryJobRepository, MemoryProfileRepository


def make_context() -> MemoryJobRepository:
    jobs = MemoryJobRepository()
    set_capability_context(
        CapabilityContext(
            credentials=None,  # type: ignore[arg-type]  # unused by this capability
            candidate_id=uuid.uuid4(),
            jobs=jobs,
            applications=None,  # type: ignore[arg-type]
            profile=MemoryProfileRepository(),
        )
    )
    return jobs


def text_of(result: dict[str, Any]) -> str:
    return str(result["content"][0]["text"])


async def test_job_capture_stores_extracted_job(monkeypatch: pytest.MonkeyPatch) -> None:
    jobs = make_context()

    async def fake_extract(_text: str) -> JobIn:
        return JobIn(
            title="Backend Engineer",
            company="Acme",
            jd_text="posting text",
            raw={"requirements": ["Python"]},
        )

    monkeypatch.setattr("app.capabilities.job_capture.extract_job", fake_extract)

    result = await job_capture.handler({"posting_text": "Backend Engineer at Acme..."})
    text = text_of(result)
    assert "Backend Engineer" in text and "Acme" in text
    assert len(jobs._rows) == 1
    (row,) = jobs._rows.values()
    assert row.source == "user_pasted"  # distinct from application_track's user_reported
    assert row.raw == {"requirements": ["Python"]}


async def test_job_capture_handles_extraction_failure_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jobs = make_context()

    async def fake_extract(_text: str) -> JobIn:
        raise JobExtractionError("couldn't identify a title and company in that text")

    monkeypatch.setattr("app.capabilities.job_capture.extract_job", fake_extract)

    result = await job_capture.handler({"posting_text": "not a job posting"})
    assert "couldn't find a job posting" in text_of(result)
    assert len(jobs._rows) == 0
