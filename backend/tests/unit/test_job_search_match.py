"""job_search_match promotion (SPEC §15 T12.6): job_id given -> real fit
assessment grounded in stored Job + Credential text; job_id omitted (or
unknown) -> falls back to the original general-guidance behavior. raw_llm is
faked to avoid a real LLM call and to inspect what gets sent to it.

Phase 13 (SPEC §16 T13.1) adds the profile layer to BOTH branches. The
empty-profile assertions here are load-bearing: D4 requires that with no facts
on file the prompts are byte-identical to the pre-Phase-13 implementation.
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


async def make_context() -> tuple[
    MemoryJobRepository, MemoryCredentialRepository, MemoryProfileRepository, uuid.UUID
]:
    candidate_id = uuid.uuid4()
    jobs = MemoryJobRepository()
    credentials = MemoryCredentialRepository()
    profile = MemoryProfileRepository()
    set_capability_context(
        CapabilityContext(
            credentials=credentials,
            candidate_id=candidate_id,
            jobs=jobs,
            applications=MemoryApplicationRepository(),
            profile=profile,
        )
    )
    return jobs, credentials, profile, candidate_id


def text_of(result: dict[str, Any]) -> str:
    return str(result["content"][0]["text"])


async def test_job_id_given_assesses_real_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    jobs, credentials, _profile, candidate_id = await make_context()
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


# --- Phase 13 (SPEC §16 T13.1): profile layer reaches both branches ---


async def test_profile_facts_reach_the_fit_assessment(monkeypatch: pytest.MonkeyPatch) -> None:
    jobs, credentials, profile, candidate_id = await make_context()
    job = await jobs.add(
        JobIn(title="Backend Engineer", company="Acme", jd_text="Onsite in NYC. Python, SQL.")
    )
    await credentials.add_many(
        candidate_id,
        [CredentialIn(kind="skill", title="Languages", body={"bullets": ["Python"]})],
    )
    await profile.set(candidate_id, "work_mode", "remote only")
    await profile.set(candidate_id, "comp_floor", "165k minimum")

    captured: dict[str, str] = {}

    async def fake_raw_llm(system: str, user: str) -> str:
        captured["system"] = system
        captured["user"] = user
        return "Moderate fit, but onsite conflicts with your remote-only constraint."

    monkeypatch.setattr(module, "raw_llm", fake_raw_llm)

    await module.job_search_match.handler({"query": "", "job_id": str(job.id)})
    # both the stored constraint and the job text must be present for the model to
    # have any chance of naming the conflict (SPEC §16 D3)
    assert "remote only" in captured["user"] and "165k minimum" in captured["user"]
    assert "work_mode" in captured["user"]
    assert "Onsite in NYC" in captured["user"]
    assert captured["system"] == module.JOB_MATCH_ASSESSMENT_PROMPT


async def test_profile_facts_reach_general_guidance(monkeypatch: pytest.MonkeyPatch) -> None:
    _jobs, _credentials, profile, candidate_id = await make_context()
    await profile.set(candidate_id, "industry", "fintech or dev tools")

    captured: dict[str, str] = {}

    async def fake_raw_llm(system: str, user: str) -> str:
        captured["system"] = system
        captured["user"] = user
        return "Guidance."

    monkeypatch.setattr(module, "raw_llm", fake_raw_llm)

    # no job_id: the branch where stated preferences matter most, since there is
    # no posting to anchor the answer (SPEC §16 D1)
    await module.job_search_match.handler({"query": "What should I target?", "job_id": ""})
    assert "What should I target?" in captured["user"]
    assert "fintech or dev tools" in captured["user"]
    assert captured["system"] == module.JOB_SEARCH_MATCH_PROMPT


async def test_empty_profile_leaves_the_assessment_prompt_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D4: no facts on file -> no preferences section anywhere in the prompt."""
    jobs, credentials, _profile, candidate_id = await make_context()
    job = await jobs.add(JobIn(title="Backend Engineer", company="Acme", jd_text="Python"))
    await credentials.add_many(
        candidate_id,
        [CredentialIn(kind="skill", title="Languages", body={"bullets": ["Python"]})],
    )

    captured: dict[str, str] = {}

    async def fake_raw_llm(system: str, user: str) -> str:
        captured["user"] = user
        return "Fit."

    monkeypatch.setattr(module, "raw_llm", fake_raw_llm)

    await module.job_search_match.handler({"query": "", "job_id": str(job.id)})
    assert "preferences" not in captured["user"].lower()
    assert "constraint" not in captured["user"].lower()


def test_profile_block_skips_blank_values() -> None:
    """A fact stored with an empty value must not emit a dangling bullet."""
    from app.repositories.base import ProfileFactOut

    cid = uuid.uuid4()
    facts = [
        ProfileFactOut(id=uuid.uuid4(), candidate_id=cid, key="work_mode", value="remote only"),
        ProfileFactOut(id=uuid.uuid4(), candidate_id=cid, key="stale", value="   "),
    ]
    block = module._profile_block(facts)
    assert "remote only" in block
    assert "stale" not in block

    assert module._profile_block([]) == ""
