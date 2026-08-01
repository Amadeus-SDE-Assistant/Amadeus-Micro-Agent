import uuid
from typing import Any

from claude_agent_sdk import tool

from app.capabilities.context import get_capability_context
from app.repositories.base import JobIn


@tool(
    "application_track",
    "Record or update a job application: company, role, and status (applied, "
    "interviewing, offer, rejected, ...). Use when the user mentions an "
    "application they sent, an interview, an offer, or a rejection they want "
    "logged or updated. Pass application_id (echoed back from a prior call) "
    "when updating an application already tracked in this conversation; leave "
    "it empty to log a new one. Leave notes empty if there's nothing to add.",
    {"company": str, "title": str, "status": str, "notes": str, "application_id": str},
)
async def application_track(args: dict[str, Any]) -> dict[str, Any]:
    # Promoted (SPEC §14 T11.2): no job dedup — every call without a known
    # application_id creates a fresh Job + Application. Real job matching
    # belongs to job_search_match's eventual promotion, not this capability.
    ctx = get_capability_context()
    company = str(args.get("company", "")).strip() or "Unknown company"
    title = str(args.get("title", "")).strip() or "Unknown role"
    status = str(args.get("status", "")).strip() or "applied"
    notes = str(args.get("notes", "")).strip()
    application_id = str(args.get("application_id", "")).strip()

    existing = None
    if application_id:
        try:
            existing = await ctx.applications.get_by_id(uuid.UUID(application_id))
        except ValueError:
            existing = None  # not a valid UUID — fall through to creating new

    if existing is not None:
        await ctx.applications.add_event(
            existing.id, "status_update", {"status": status, "notes": notes}
        )
        await ctx.applications.set_status(existing.id, status)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f'Updated your application to {company} for {title} to '
                    f'status "{status}". Reference: {existing.id}',
                }
            ]
        }

    job = await ctx.jobs.add(JobIn(title=title, company=company))
    application = await ctx.applications.create(ctx.candidate_id, job.id, status)
    await ctx.applications.add_event(
        application.id, "created", {"status": status, "notes": notes}
    )
    return {
        "content": [
            {
                "type": "text",
                "text": f'Logged your application to {company} for {title} '
                f'(status: "{status}"). Reference: {application.id} — mention this '
                "if you want to update its status later.",
            }
        ]
    }
