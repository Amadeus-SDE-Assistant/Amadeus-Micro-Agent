"""Raw one-shot LLM call — the body of every stub capability (SPEC §4 stub contract).

Uses the Agent SDK's query() with tools disabled so stubs cost one model call and
authenticate exactly like the main agent (CLI login in dev; API key in deployment).
"""

import asyncio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

from app.config import get_settings


async def raw_llm(system: str, user: str) -> str:
    settings = get_settings()
    options = ClaudeAgentOptions(
        model=settings.agent_model,
        system_prompt=system,
        max_turns=1,
        allowed_tools=[],
    )
    parts: list[str] = []
    async with asyncio.timeout(settings.agent_timeout_seconds):
        async for message in query(prompt=user, options=options):
            if isinstance(message, AssistantMessage):
                parts.extend(b.text for b in message.content if isinstance(b, TextBlock))
    return "".join(parts).strip()
