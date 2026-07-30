from typing import Any

from claude_agent_sdk import tool

from app.agent.llm import raw_llm
from app.agent.prompts import APPLICATION_TRACK_PROMPT


@tool(
    "application_track",
    "Record or reason about the user's job applications: statuses, follow-ups, "
    "pipeline overview. Use when the user mentions applications they sent, "
    "interviews, offers, or rejections they want tracked or reviewed.",
    {"query": str},
)
async def application_track(args: dict[str, Any]) -> dict[str, Any]:
    # STUB: raw LLM call (SPEC §4). Promotion path: persist to the application /
    # application_event tables via a repository and make this a write capability
    # behind the approval gate.
    text = await raw_llm(system=APPLICATION_TRACK_PROMPT, user=str(args["query"]))
    return {"content": [{"type": "text", "text": text}]}
