"""job_capture — chat-native job posting capture (SPEC §15 T12.4).

Agent-initiated, same shape as resume_store: pasted job text in, one extraction
call, one descriptive approval for the whole write (SPEC §11). No automated
fetching anywhere — the posting always arrives via the user pasting it.
"""

from typing import Any

from claude_agent_sdk import tool

from app.capabilities.context import get_capability_context
from app.ingestion.job_extract import JobExtractionError, extract_job
from app.repositories.base import JobIn


@tool(
    "job_capture",
    "Save a job posting the user pasted into chat so you can check their fit "
    "against it later: extracts the role, company, and requirements, and "
    "stores it. Use when the user pastes a job posting or job description.",
    {"posting_text": str},
)
async def job_capture(args: dict[str, Any]) -> dict[str, Any]:
    ctx = get_capability_context()
    try:
        extracted = await extract_job(str(args["posting_text"]))
    except JobExtractionError as exc:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"I couldn't find a job posting in that text: {exc}. "
                    "Nothing was saved.",
                }
            ]
        }
    stored = await ctx.jobs.add(
        JobIn(
            title=extracted.title,
            company=extracted.company,
            source="user_pasted",
            jd_text=extracted.jd_text,
            raw=extracted.raw,
        )
    )
    return {
        "content": [
            {
                "type": "text",
                "text": f"Saved {stored.title} at {stored.company}. Reference: "
                f"{stored.id} — mention this if you want to check your fit against it.",
            }
        ]
    }
