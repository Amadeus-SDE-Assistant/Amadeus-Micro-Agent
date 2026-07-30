from typing import Any

from claude_agent_sdk import tool

from app.agent.llm import raw_llm
from app.agent.prompts import EMOTIONAL_SUPPORT_PROMPT


@tool(
    "emotional_support",
    "Support the user through the emotional side of job seeking: rejection, "
    "burnout, imposter feelings, motivation. Use when the user expresses "
    "frustration, discouragement, or stress rather than asking a task question.",
    {"query": str},
)
async def emotional_support(args: dict[str, Any]) -> dict[str, Any]:
    # STUB: raw LLM call (SPEC §4). Proves the container handles non-task
    # capabilities; promotion path: persona tuning + long-term memory of the
    # user's journey.
    text = await raw_llm(system=EMOTIONAL_SUPPORT_PROMPT, user=str(args["query"]))
    return {"content": [{"type": "text", "text": text}]}
