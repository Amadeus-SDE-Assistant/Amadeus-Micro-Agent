from typing import Any

from claude_agent_sdk import tool

from app.agent.llm import raw_llm
from app.agent.prompts import JOB_SEARCH_MATCH_PROMPT


@tool(
    "job_search_match",
    "Help the user find and match against job opportunities: role archetypes, "
    "target companies, search strategy, fit against their background. Use when "
    "the user asks what jobs to look for or how well they'd match a role.",
    {"query": str},
)
async def job_search_match(args: dict[str, Any]) -> dict[str, Any]:
    # STUB: raw LLM call (SPEC §4). Promotion path: real job-board/data source +
    # pgvector similarity between credential and job embeddings (deferral item 4).
    text = await raw_llm(system=JOB_SEARCH_MATCH_PROMPT, user=str(args["query"]))
    return {"content": [{"type": "text", "text": text}]}
