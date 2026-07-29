"""AgentService: one ClaudeSDKClient session per conversation.

Reliability contract (SPEC §10): every turn has a timeout; any failure surfaces as an
ERROR event (never an escaped exception or hung stream); a dead client is dropped so
the next turn gets a fresh session plus a restart notice.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from app.agent.events import AgentEvent, AgentEventType
from app.agent.prompts import AGENT_SYSTEM_PROMPT
from app.capabilities.registry import capability_server, capability_tool_names
from app.config import Settings, get_settings
from app.logging_setup import log_extra, session_id_var

logger = logging.getLogger("app.agent")


class AgentClient(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def query(self, prompt: str) -> None: ...
    def receive_response(self) -> AsyncIterator[Any]: ...


def _default_client_factory(settings: Settings) -> AgentClient:
    options = ClaudeAgentOptions(
        model=settings.agent_model,
        system_prompt=AGENT_SYSTEM_PROMPT,
        mcp_servers={"jobseeker": capability_server()},
        allowed_tools=capability_tool_names(),
        max_turns=8,
        cwd=str(settings.data_dir),
    )
    return ClaudeSDKClient(options)


class AgentService:
    def __init__(
        self,
        settings: Settings | None = None,
        client_factory: Callable[[Settings], AgentClient] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._factory = client_factory or _default_client_factory
        self._clients: dict[str, AgentClient] = {}
        self._restarted: set[str] = set()
        self._settings.data_dir.mkdir(parents=True, exist_ok=True)

    async def chat(self, conversation_id: str, text: str) -> AsyncIterator[AgentEvent]:
        session_id_var.set(conversation_id)
        restarted = conversation_id in self._restarted
        self._restarted.discard(conversation_id)
        try:
            client = await self._get_client(conversation_id)
            async with asyncio.timeout(self._settings.agent_timeout_seconds):
                if restarted:
                    yield AgentEvent(
                        type=AgentEventType.TEXT,
                        text="(A previous error ended the session; the conversation "
                        "was restarted and earlier context may be missing.)\n",
                    )
                await client.query(text)
                async for message in client.receive_response():
                    for event in self._to_events(message):
                        yield event
        except TimeoutError:
            await self._drop_client(conversation_id)
            logger.error("agent turn timed out", extra=log_extra(conversation=conversation_id))
            yield AgentEvent(
                type=AgentEventType.ERROR,
                text="The agent took too long to respond and the turn was cancelled. "
                "Please try again.",
            )
        except Exception:
            await self._drop_client(conversation_id)
            logger.exception("agent turn failed", extra=log_extra(conversation=conversation_id))
            yield AgentEvent(
                type=AgentEventType.ERROR,
                text="Something went wrong talking to the agent. Your message was not "
                "lost — please try again.",
            )

    def _to_events(self, message: Any) -> list[AgentEvent]:
        events: list[AgentEvent] = []
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    events.append(AgentEvent(type=AgentEventType.TEXT, text=block.text))
                elif isinstance(block, ToolUseBlock):
                    events.append(
                        AgentEvent(type=AgentEventType.TOOL_USE, tool_name=block.name)
                    )
                    logger.info("tool invoked", extra=log_extra(tool=block.name))
        elif isinstance(message, ResultMessage):
            events.append(
                AgentEvent(
                    type=AgentEventType.DONE,
                    meta={
                        "duration_ms": message.duration_ms,
                        "cost_usd": message.total_cost_usd,
                        "num_turns": message.num_turns,
                    },
                )
            )
        return events

    async def _get_client(self, conversation_id: str) -> AgentClient:
        client = self._clients.get(conversation_id)
        if client is None:
            client = self._factory(self._settings)
            await client.connect()
            self._clients[conversation_id] = client
        return client

    async def _drop_client(self, conversation_id: str) -> None:
        client = self._clients.pop(conversation_id, None)
        self._restarted.add(conversation_id)
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                logger.warning("disconnect after failure also failed", exc_info=True)

    async def shutdown(self) -> None:
        for cid in list(self._clients):
            await self._drop_client(cid)
        self._restarted.clear()
