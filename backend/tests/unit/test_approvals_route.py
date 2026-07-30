import asyncio
import uuid
from typing import Any

import httpx

from app.agent.approvals import ApprovalGate
from app.agent.events import AgentEvent
from app.main import create_app
from app.repositories.memory import MemoryApprovalRepository


async def make_app_with_pending() -> tuple[Any, uuid.UUID, asyncio.Task[Any]]:
    app = create_app()
    gate = ApprovalGate(MemoryApprovalRepository(), timeout_seconds=5)
    app.state.approval_gate = gate
    queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
    gate.bind("c1", queue)
    task = asyncio.create_task(
        gate.check("c1", "mcp__jobseeker__resume_store", {}, "Save this?")
    )
    event = await asyncio.wait_for(queue.get(), timeout=2)
    assert event is not None and event.approval_id is not None
    return app, uuid.UUID(event.approval_id), task


async def post_decision(app: Any, approval_id: uuid.UUID, decision: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(f"/api/approvals/{approval_id}", json={"decision": decision})


async def test_resolve_pending_approval() -> None:
    app, approval_id, task = await make_app_with_pending()
    resp = await post_decision(app, approval_id, "approved")
    assert resp.status_code == 200
    result = await asyncio.wait_for(task, timeout=2)
    assert type(result).__name__ == "PermissionResultAllow"


async def test_unknown_approval_404() -> None:
    app = create_app()
    app.state.approval_gate = ApprovalGate(MemoryApprovalRepository())
    resp = await post_decision(app, uuid.uuid4(), "denied")
    assert resp.status_code == 404


async def test_invalid_decision_422() -> None:
    app, approval_id, task = await make_app_with_pending()
    resp = await post_decision(app, approval_id, "maybe")
    assert resp.status_code == 422
    # Clean up the pending future so the task doesn't leak.
    app.state.approval_gate.resolve(approval_id, "denied")
    await task
