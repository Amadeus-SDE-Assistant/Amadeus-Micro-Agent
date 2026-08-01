"""job_search_match promotion (SPEC §15 T12.6): job_id given -> real fit
assessment grounded in stored Job + Credential text; job_id omitted (or
unknown) -> falls back to the original general-guidance behavior. raw_llm is
faked to avoid a real LLM call and to inspect what gets sent to it.
"""

import uuid
from typing import Any

import pytest

from app.capabilities.context import CapabilityContext, set_capability_context
from app.capabilities.stubs import job_search_match as module
from app.repositories.base import CredentialIn, JobIn
from app.repositories.memory import (
    MemoryApplicationRepository,
    MemoryCredentialRepository,
    MemoryJobRepository,
    MemoryProfileRepository,
)


async def make_context() -> tuple[MemoryJobRepository, MemoryCredentialRepository, uuid.UUID]:
    candidate_id = uuid.uuid4()
    jobs = MemoryJobRepository()
    credentials = MemoryCredentialRepository()
    set_capability_context(
        CapabilityContext(
            credentials=credentials,
            candidate_id=candidate_id,
            jobs=jobs,
            applications=MemoryApplicationRepository(),
            profile=MemoryProfileRepository(),
        )
    )
    return jobs, credentials, candidate_id


def text_of(result: dict[str, Any]) -> str:
    return str(result["content"][0]["text"])


async def test_job_id_given_assesses_real_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    jobs, credentials, candidate_id = await make_context()
    job = await jobs.add(JobIn(title="Backend Engineer", company="Acme", jd_text="Python, SQL"))
    await credentials.add_many(
        candidate_id,
        [CredentialIn(kind="skill", title="Languages", body={"bullets": ["Python", "Go"]})],
    )

    captured: dict[str, str] = {}

    async def fake_raw_llm(system: str, user: str) -> str:
        captured["system"] = system
        captured["user"] = user
        return "Strong fit."

    monkeypatch.setattr(module, "raw_llm", fake_raw_llm)

    result = await module.job_search_match.handler({"query": "", "job_id": str(job.id)})
    assert text_of(result) == "Strong fit."
    assert "Backend Engineer" in captured["user"] and "Acme" in captured["user"]
    # credential body (not just kind/title) must be grounded in the prompt
    assert "Python" in captured["user"] and "Go" in captured["user"]
    assert captured["system"] == module.JOB_MATCH_ASSESSMENT_PROMPT


async def test_missing_job_id_falls_back_to_general_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await make_context()
    captured: dict[str, str] = {}

    async def fake_raw_llm(system: str, user: str) -> str:
        captured["system"] = system
        captured["user"] = user
        return "General guidance."

    monkeypatch.setattr(module, "raw_llm", fake_raw_llm)

    result = await module.job_search_match.handler({"query": "What should I target?", "job_id": ""})
    assert text_of(result) == "General guidance."
    assert captured["system"] == module.JOB_SEARCH_MATCH_PROMPT
    assert captured["user"] == "What should I target?"


async def test_unknown_job_id_falls_back_to_general_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await make_context()

    async def fake_raw_llm(system: str, user: str) -> str:
        return "General guidance."

    monkeypatch.setattr(module, "raw_llm", fake_raw_llm)

    result = await module.job_search_match.handler({"query": "", "job_id": str(uuid.uuid4())})
    assert text_of(result) == "General guidance."
