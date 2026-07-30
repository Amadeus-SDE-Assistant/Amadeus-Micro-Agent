import asyncio
import uuid

from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

from app.agent.approvals import APPROVED, DENIED, EXPIRED, ApprovalGate
from app.agent.events import AgentEvent, AgentEventType
from app.repositories.memory import MemoryApprovalRepository


def make_gate(timeout: float = 5.0) -> tuple[ApprovalGate, MemoryApprovalRepository]:
    repo = MemoryApprovalRepository()
    return ApprovalGate(repo, timeout_seconds=timeout), repo


async def test_read_only_tool_passes_without_approval() -> None:
    gate, repo = make_gate()
    result = await gate.check("c1", "mcp__jobseeker__strategy_convo", {"query": "x"}, None)
    assert isinstance(result, PermissionResultAllow)
    assert repo.rows == {}  # nothing to audit — no write happened


async def run_gated_check(
    gate: ApprovalGate, decision: str
) -> tuple[object, AgentEvent]:
    """Drive a write-tool check: capture the approval event, resolve it."""
    queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
    gate.bind("c1", queue)
    task = asyncio.create_task(
        gate.check("c1", "mcp__jobseeker__resume_store", {"resume_text": "abc"},
                   "Save your resume credentials?")
    )
    event = await asyncio.wait_for(queue.get(), timeout=2)
    assert event is not None and event.type == AgentEventType.APPROVAL_REQUEST
    assert event.intent == "Save your resume credentials?"
    assert gate.resolve(uuid.UUID(event.approval_id), decision) == "ok"
    return await task, event


async def test_approved_write_allows_and_audits() -> None:
    gate, repo = make_gate()
    result, event = await run_gated_check(gate, APPROVED)
    assert isinstance(result, PermissionResultAllow)
    row = repo.rows[uuid.UUID(event.approval_id)]
    assert row["decision"] == APPROVED
    assert row["intent"] == "Save your resume credentials?"


async def test_denied_write_denies_and_audits() -> None:
    gate, repo = make_gate()
    result, event = await run_gated_check(gate, DENIED)
    assert isinstance(result, PermissionResultDeny)
    assert "declined" in result.message
    assert repo.rows[uuid.UUID(event.approval_id)]["decision"] == DENIED


async def test_unanswered_approval_expires_to_deny() -> None:
    gate, repo = make_gate(timeout=0.05)
    queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
    gate.bind("c1", queue)
    result = await gate.check(
        "c1", "mcp__jobseeker__resume_store", {}, "Save?"
    )
    assert isinstance(result, PermissionResultDeny)
    assert list(repo.rows.values())[0]["decision"] == EXPIRED


async def test_write_without_live_stream_is_denied() -> None:
    gate, repo = make_gate()
    result = await gate.check("no-stream", "mcp__jobseeker__resume_store", {}, "Save?")
    assert isinstance(result, PermissionResultDeny)
    assert list(repo.rows.values())[0]["decision"] == DENIED


async def test_resolve_unknown_and_double_resolve() -> None:
    gate, _ = make_gate()
    assert gate.resolve(uuid.uuid4(), APPROVED) == "unknown"
    _, event = await run_gated_check(gate, APPROVED)
    assert gate.resolve(uuid.UUID(event.approval_id), DENIED) == "unknown"  # already popped
