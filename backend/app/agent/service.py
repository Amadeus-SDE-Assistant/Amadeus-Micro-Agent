"""AgentService: one ClaudeSDKClient session per conversation.

Reliability contract (SPEC §10): every event gap has a timeout; any failure
surfaces as an ERROR event (never an escaped exception or hung stream); a dead
client is dropped so the next turn gets a fresh session plus a restart notice.

Turn architecture: SDK messages and approval requests are merged onto one queue —
while the ApprovalGate blocks the SDK turn waiting for a human decision, the
approval_request event still reaches the stream (SPEC §11).
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from app.agent.approvals import ApprovalGate
from app.agent.events import AgentEvent, AgentEventType
from app.agent.prompts import AGENT_SYSTEM_PROMPT
from app.capabilities.registry import (
    allowed_tool_names,
    capability_server,
    write_intent,
)
from app.config import Settings, get_settings
from app.logging_setup import log_extra, session_id_var

logger = logging.getLogger("app.agent")


class AgentClient(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def query(self, prompt: str) -> None: ...
    def receive_response(self) -> AsyncIterator[Any]: ...


ClientFactory = Callable[[Settings, str], AgentClient]


class AgentService:
    def __init__(
        self,
        settings: Settings | None = None,
        client_factory: ClientFactory | None = None,
        gate: ApprovalGate | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._factory = client_factory or self._default_client_factory
        self._gate = gate
        self._clients: dict[str, AgentClient] = {}
        self._restarted: set[str] = set()
        self._settings.data_dir.mkdir(parents=True, exist_ok=True)

    def _default_client_factory(self, settings: Settings, conversation_id: str) -> AgentClient:
        async def can_use_tool(
            tool_name: str, input_data: dict[str, Any], context: Any
        ) -> Any:
            if self._gate is None:
                return PermissionResultAllow()
            return await self._gate.check(
                conversation_id, tool_name, input_data, write_intent(tool_name, input_data)
            )

        options = ClaudeAgentOptions(
            model=settings.agent_model,
            system_prompt=AGENT_SYSTEM_PROMPT,
            mcp_servers={"jobseeker": capability_server()},
            # Write capabilities are deliberately NOT pre-allowed: allowed_tools
            # bypasses can_use_tool, which would skip the approval gate.
            allowed_tools=allowed_tool_names(),
            max_turns=8,
            max_budget_usd=settings.agent_max_budget_usd,
            cwd=str(settings.data_dir),
            can_use_tool=can_use_tool,
        )
        return ClaudeSDKClient(options)

    async def chat(self, conversation_id: str, text: str) -> AsyncIterator[AgentEvent]:
        session_id_var.set(conversation_id)
        restarted = conversation_id in self._restarted
        self._restarted.discard(conversation_id)

        queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
        if self._gate is not None:
            self._gate.bind(conversation_id, queue)
        pump: asyncio.Task[None] | None = None
        try:
            client = await self._get_client(conversation_id)
            if restarted:
                yield AgentEvent(
                    type=AgentEventType.TEXT,
                    text="(A previous error ended the session; the conversation "
                    "was restarted and earlier context may be missing.)\n",
                )

            async def run_turn() -> None:
                try:
                    await client.query(text)
                    async for message in client.receive_response():
                        for event in self._to_events(message):
                            await queue.put(event)
                except Exception:
                    logger.exception(
                        "agent turn failed", extra=log_extra(conversation=conversation_id)
                    )
                    await queue.put(
                        AgentEvent(
                            type=AgentEventType.ERROR,
                            text="Something went wrong talking to the agent. Your "
                            "message was not lost — please try again.",
                        )
                    )
                finally:
                    await queue.put(None)

            pump = asyncio.create_task(run_turn())
            turn_failed = False
            while True:
                # Per-gap timeout: approval waits are bounded by the gate's own
                # (shorter) timeout, so a silent gap this long means a real hang.
                event = await asyncio.wait_for(
                    queue.get(), timeout=self._settings.agent_timeout_seconds
                )
                if event is None:
                    break
                if event.type == AgentEventType.ERROR:
                    turn_failed = True
                yield event
            if turn_failed:
                await self._drop_client(conversation_id)
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
        finally:
            if pump is not None and not pump.done():
                pump.cancel()
            if self._gate is not None:
                self._gate.unbind(conversation_id)

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
            client = self._factory(self._settings, conversation_id)
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

    @property
    def active_sessions(self) -> int:
        return len(self._clients)

    async def shutdown(self) -> None:
        for cid in list(self._clients):
            await self._drop_client(cid)
        self._restarted.clear()
