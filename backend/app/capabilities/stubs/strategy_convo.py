from typing import Any

from claude_agent_sdk import tool

from app.agent.llm import raw_llm
from app.agent.prompts import STRATEGY_CONVO_PROMPT


@tool(
    "strategy_convo",
    "Career strategy conversation: targeting, positioning, sequencing, negotiation. "
    "Use for questions about how to approach the job search.",
    {"query": str},
)
async def strategy_convo(args: dict[str, Any]) -> dict[str, Any]:
    # STUB: raw LLM call with a capability-specific prompt (SPEC §4).
    # Promotion path: graduate to a subagent with its own context window once
    # multi-turn strategy state is needed (SPEC §3 future evolution).
    text = await raw_llm(system=STRATEGY_CONVO_PROMPT, user=str(args["query"]))
    return {"content": [{"type": "text", "text": text}]}
