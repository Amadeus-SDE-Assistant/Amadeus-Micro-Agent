"""ApprovalGate — the can_use_tool hook (SPEC §11).

Write-capability calls pause the agent turn: the gate records a pending approval
(audit row first), pushes a descriptive approval_request event onto the active
conversation's stream, and blocks until the user resolves it via
POST /api/approvals/{id} — or until the approval times out, which counts as a
denial ("expired"). Read-only capabilities pass through untouched.

Descriptive, not literal: the event carries `intent` (one plain-language sentence);
the raw args live in the audit row and the event meta for on-demand expansion.
"""

import asyncio
import logging
import uuid
from typing import Any

from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

from app.agent.events import AgentEvent, AgentEventType
from app.logging_setup import log_extra
from app.repositories.base import ApprovalRepository

logger = logging.getLogger("app.approvals")

APPROVED = "approved"
DENIED = "denied"
EXPIRED = "expired"


class ApprovalGate:
    def __init__(self, repo: ApprovalRepository, timeout_seconds: float = 90.0) -> None:
        self._repo = repo
        self._timeout = timeout_seconds
        self._pending: dict[uuid.UUID, asyncio.Future[str]] = {}
        self._queues: dict[str, asyncio.Queue[AgentEvent | None]] = {}

    def bind(self, conversation_id: str, queue: asyncio.Queue[AgentEvent | None]) -> None:
        self._queues[conversation_id] = queue

    def unbind(self, conversation_id: str) -> None:
        self._queues.pop(conversation_id, None)

    async def check(
        self,
        conversation_id: str,
        tool_name: str,
        args: dict[str, Any],
        intent: str | None,
    ) -> PermissionResultAllow | PermissionResultDeny:
        """Gate one tool call. intent=None marks the tool as read-only: allow."""
        if intent is None:
            return PermissionResultAllow()

        approval_id = await self._repo.create(
            tool_name, intent, args, sdk_session_id=conversation_id
        )
        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._pending[approval_id] = future

        queue = self._queues.get(conversation_id)
        if queue is None:
            # No live stream to ask on — refuse rather than write silently (SPEC §11).
            await self._repo.decide(approval_id, DENIED)
            del self._pending[approval_id]
            return PermissionResultDeny(
                message="No active conversation to request approval on; the write "
                "was not performed."
            )
        await queue.put(
            AgentEvent(
                type=AgentEventType.APPROVAL_REQUEST,
                approval_id=str(approval_id),
                intent=intent,
                tool_name=tool_name,
                meta={"args": args},
            )
        )

        try:
            decision = await asyncio.wait_for(future, timeout=self._timeout)
        except TimeoutError:
            decision = EXPIRED
        finally:
            self._pending.pop(approval_id, None)

        await self._repo.decide(approval_id, decision)
        logger.info(
            "approval resolved",
            extra=log_extra(tool=tool_name, decision=decision, approval=str(approval_id)),
        )
        if decision == APPROVED:
            return PermissionResultAllow()
        message = (
            "The user did not respond in time, so the action was cancelled."
            if decision == EXPIRED
            else "The user declined this action."
        )
        return PermissionResultDeny(message=message)

    def resolve(self, approval_id: uuid.UUID, decision: str) -> str:
        """Route entry point. Returns 'ok', 'unknown', or 'already_decided'."""
        future = self._pending.get(approval_id)
        if future is None:
            return "unknown"
        if future.done():
            return "already_decided"
        future.set_result(decision)
        return "ok"
