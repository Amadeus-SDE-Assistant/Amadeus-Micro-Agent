"""application_track promotion (SPEC §14 T11.2): no job dedup by design — a
call without a known application_id always creates a fresh Job + Application;
a call with one appends an ApplicationEvent and updates status instead.
"""

import re
import uuid
from typing import Any

from app.capabilities.context import CapabilityContext, set_capability_context
from app.capabilities.stubs.application_track import application_track
from app.repositories.memory import (
    MemoryApplicationRepository,
    MemoryJobRepository,
    MemoryProfileRepository,
)

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def make_context() -> tuple[MemoryJobRepository, MemoryApplicationRepository]:
    jobs = MemoryJobRepository()
    applications = MemoryApplicationRepository()
    set_capability_context(
        CapabilityContext(
            credentials=None,  # type: ignore[arg-type]  # unused by this capability
            candidate_id=uuid.uuid4(),
            jobs=jobs,
            applications=applications,
            profile=MemoryProfileRepository(),
        )
    )
    return jobs, applications


def text_of(result: dict[str, Any]) -> str:
    return str(result["content"][0]["text"])


async def test_new_application_creates_job_and_application() -> None:
    jobs, applications = make_context()
    result = await application_track.handler(
        {"company": "Acme", "title": "Backend Engineer", "status": "applied",
         "notes": "", "application_id": ""}
    )
    text = text_of(result)
    assert "Acme" in text and "Backend Engineer" in text
    assert len(jobs._rows) == 1
    assert len(applications._rows) == 1
    (app_row,) = applications._rows.values()
    assert app_row.status == "applied"


async def test_follow_up_with_application_id_appends_event_not_duplicate() -> None:
    jobs, applications = make_context()
    first = await application_track.handler(
        {"company": "Acme", "title": "Backend Engineer", "status": "applied",
         "notes": "", "application_id": ""}
    )
    match = UUID_RE.search(text_of(first))
    assert match is not None  # the id must be surfaced so a later turn can reuse it
    app_id = match.group(0)

    second = await application_track.handler(
        {"company": "Acme", "title": "Backend Engineer", "status": "interviewing",
         "notes": "phone screen scheduled", "application_id": app_id}
    )

    assert len(jobs._rows) == 1  # no second Job created
    assert len(applications._rows) == 1  # no second Application created
    (app_row,) = applications._rows.values()
    assert app_row.status == "interviewing"
    assert applications.events[app_row.id][-1][0] == "status_update"
    assert "interviewing" in text_of(second)


async def test_unknown_application_id_falls_back_to_creating_new() -> None:
    jobs, applications = make_context()
    result = await application_track.handler(
        {"company": "Acme", "title": "Backend Engineer", "status": "applied",
         "notes": "", "application_id": str(uuid.uuid4())}
    )
    assert len(jobs._rows) == 1
    assert len(applications._rows) == 1
    assert "Acme" in text_of(result)
