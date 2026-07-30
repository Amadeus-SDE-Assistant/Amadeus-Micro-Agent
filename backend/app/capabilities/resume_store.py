"""resume_store — the one REAL capability in v1 (SPEC §4).

Agent-initiated ingestion: takes resume text pasted in chat, decomposes it into
typed credentials, and persists them. The whole write set sits behind ONE batched,
descriptive approval — the ApprovalGate intercepts this tool's call before the
body runs (SPEC §11).
"""

from collections import Counter
from typing import Any

from claude_agent_sdk import tool

from app.capabilities.context import get_capability_context
from app.ingestion.decompose import DecompositionError, decompose


@tool(
    "resume_store",
    "Store the user's resume: decompose pasted resume text into structured "
    "credentials (experience, education, skills, projects, certifications) and "
    "save them to the user's profile. Use when the user shares resume content or "
    "asks to save their experience.",
    {"resume_text": str},
)
async def resume_store(args: dict[str, Any]) -> dict[str, Any]:
    ctx = get_capability_context()
    try:
        credentials = await decompose(str(args["resume_text"]))
    except DecompositionError as exc:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"I couldn't decompose that into credentials: {exc}. "
                    "Nothing was saved.",
                }
            ]
        }
    for cred in credentials:
        cred.body["source_document"] = "chat"
    await ctx.credentials.add_many(ctx.candidate_id, credentials)
    counts = Counter(c.kind for c in credentials)
    summary = ", ".join(f"{n} {kind}" for kind, n in sorted(counts.items()))
    return {
        "content": [
            {"type": "text", "text": f"Stored {len(credentials)} credentials ({summary})."}
        ]
    }
