"""profile_save / profile_recall (SPEC §15 T12.2): generic personal-fact store,
proven via round-trip — write via profile_save, read back via profile_recall.
"""

import uuid
from typing import Any

from app.capabilities.context import CapabilityContext, set_capability_context
from app.capabilities.profile import profile_recall, profile_save
from app.repositories.memory import MemoryProfileRepository


def make_context() -> tuple[MemoryProfileRepository, uuid.UUID]:
    profile = MemoryProfileRepository()
    candidate_id = uuid.uuid4()
    set_capability_context(
        CapabilityContext(
            credentials=None,  # type: ignore[arg-type]  # unused by this capability
            candidate_id=candidate_id,
            jobs=None,  # type: ignore[arg-type]
            applications=None,  # type: ignore[arg-type]
            profile=profile,
        )
    )
    return profile, candidate_id


def text_of(result: dict[str, Any]) -> str:
    return str(result["content"][0]["text"])


async def test_profile_save_persists_one_or_more_facts() -> None:
    profile, candidate_id = make_context()
    result = await profile_save.handler(
        {"facts": {"target_role": "Staff Engineer", "location_preference": "Remote"}}
    )
    text = text_of(result)
    assert "target_role" in text and "location_preference" in text
    stored = await profile.get_all(candidate_id)
    assert {f.key: f.value for f in stored} == {
        "target_role": "Staff Engineer",
        "location_preference": "Remote",
    }


async def test_profile_save_upserts_not_duplicates() -> None:
    profile, candidate_id = make_context()
    await profile_save.handler({"facts": {"target_role": "Backend Engineer"}})
    await profile_save.handler({"facts": {"target_role": "Staff Engineer"}})
    stored = await profile.get_all(candidate_id)
    assert len(stored) == 1
    assert stored[0].value == "Staff Engineer"


async def test_profile_save_with_no_facts_saves_nothing() -> None:
    profile, candidate_id = make_context()
    result = await profile_save.handler({"facts": {}})
    assert "No facts" in text_of(result)
    assert await profile.get_all(candidate_id) == []


async def test_profile_recall_returns_saved_facts() -> None:
    profile, candidate_id = make_context()
    await profile.set(candidate_id, "target_role", "Staff Engineer")
    result = await profile_recall.handler({})
    assert "target_role: Staff Engineer" in text_of(result)


async def test_profile_recall_on_empty_profile_says_so() -> None:
    make_context()
    result = await profile_recall.handler({})
    assert "Nothing saved" in text_of(result)
