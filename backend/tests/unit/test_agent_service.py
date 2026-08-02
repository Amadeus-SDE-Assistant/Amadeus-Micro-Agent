import asyncio
from collections.abc import AsyncIterator
from typing import Any

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from app.agent.events import AgentEvent, AgentEventType
from app.agent.service import AgentService
from app.config import Settings


def make_settings(tmp_path_str: str, timeout: float = 5.0) -> Settings:
    return Settings(data_dir=tmp_path_str, agent_timeout_seconds=timeout)  # type: ignore[arg-type]


def assistant_text(text: str) -> AssistantMessage:
    return AssistantMessage(content=[TextBlock(text=text)], model="test", parent_tool_use_id=None)


def result_ok() -> ResultMessage:
    return ResultMessage(
        subtype="success",
        duration_ms=10,
        duration_api_ms=8,
        is_error=False,
        num_turns=1,
        session_id="s1",
        total_cost_usd=0.001,
    )


class FakeClient:
    """Scriptable stand-in for ClaudeSDKClient."""

    def __init__(
        self,
        script: list[Any] | None = None,
        fail: Exception | None = None,
        hang_seconds: float = 0.0,
    ) -> None:
        self.script = script or []
        self.fail = fail
        self.hang_seconds = hang_seconds
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def query(self, prompt: str) -> None:
        pass

    async def receive_response(self) -> AsyncIterator[Any]:
        if self.hang_seconds:
            await asyncio.sleep(self.hang_seconds)
        if self.fail is not None:
            raise self.fail
        for item in self.script:
            yield item


async def collect(service: AgentService, cid: str, text: str) -> list[AgentEvent]:
    return [e async for e in service.chat(cid, text)]


async def test_happy_path_streams_text_and_done(tmp_path: Any) -> None:
    fake = FakeClient(script=[assistant_text("hello"), result_ok()])
    service = AgentService(make_settings(str(tmp_path)), client_factory=lambda s, cid: fake)
    events = await collect(service, "c1", "hi")
    assert [e.type for e in events] == [AgentEventType.TEXT, AgentEventType.DONE]
    assert events[0].text == "hello"
    assert events[1].meta is not None and events[1].meta["cost_usd"] == 0.001


async def test_failure_yields_error_event_and_recovers_with_fresh_client(tmp_path: Any) -> None:
    clients = [
        FakeClient(fail=RuntimeError("boom")),
        FakeClient(script=[assistant_text("recovered"), result_ok()]),
    ]
    service = AgentService(
        make_settings(str(tmp_path)), client_factory=lambda s, cid: clients.pop(0)
    )

    first = await collect(service, "c1", "hi")
    assert [e.type for e in first] == [AgentEventType.ERROR]
    assert first[0].text  # readable message, not a traceback

    second = await collect(service, "c1", "again")
    # Fresh client + restart notice (SPEC §10 reliability row 2).
    assert second[0].type == AgentEventType.TEXT and "restarted" in (second[0].text or "")
    assert [e.type for e in second[1:]] == [AgentEventType.TEXT, AgentEventType.DONE]
    assert not clients  # both factory clients consumed


async def test_hang_hits_timeout_and_yields_error(tmp_path: Any) -> None:
    fake = FakeClient(hang_seconds=2.0)
    service = AgentService(
        make_settings(str(tmp_path), timeout=0.2), client_factory=lambda s, cid: fake
    )
    events = await collect(service, "c1", "hi")
    assert [e.type for e in events] == [AgentEventType.ERROR]
    assert "too long" in (events[0].text or "")


def test_default_client_has_no_builtin_tools(tmp_path: Any) -> None:
    # Security regression: the ApprovalGate only knows about the jobseeker
    # capabilities' write intents (registry._WRITE_INTENTS). Any tool it
    # doesn't recognize — including the SDK's built-in Bash/Read/Write/Edit —
    # is treated as read-only and auto-allowed (approvals.py: "intent=None
    # marks the tool as read-only: allow"). Those built-ins must therefore
    # never be reachable in the first place: `tools=[]` disables the SDK's
    # entire built-in toolset, leaving only the jobseeker MCP server.
    # Discovered live 2026-07-30: a single chat message caused real Bash/Read
    # tool calls with zero approval prompt.
    service = AgentService(make_settings(str(tmp_path)))
    options = service._build_options("c1")
    assert options.tools == []


def test_default_client_ignores_filesystem_settings(tmp_path: Any) -> None:
    # Security regression, found live 2026-08-01 (SPEC §16 CHECKPOINT C13).
    # setting_sources=None is documented by the SDK as "all sources are loaded
    # (matches CLI defaults)" — so the machine's own ~/.claude/settings.json was
    # being read into this app's agent. A "defaultMode": "auto" there
    # auto-approves tool calls BEFORE can_use_tool is consulted, which silently
    # voids the ApprovalGate: a job_capture write persisted with no approval
    # prompt and no audit row at all. This app's security model must not depend
    # on the contents of a config file outside the repo. [] is the SDK's
    # documented isolation mode.
    service = AgentService(make_settings(str(tmp_path)))
    options = service._build_options("c1")
    assert options.setting_sources == []
