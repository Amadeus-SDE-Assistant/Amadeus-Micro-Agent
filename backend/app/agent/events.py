"""Event envelope streamed to clients (SSE) — including errors (SPEC §10: fail loudly)."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class AgentEventType(StrEnum):
    TEXT = "text"
    TOOL_USE = "tool_use"
    APPROVAL_REQUEST = "approval_request"
    DONE = "done"
    ERROR = "error"


class AgentEvent(BaseModel):
    type: AgentEventType
    text: str | None = None
    tool_name: str | None = None
    # approval_request events: id to resolve via POST /api/approvals/{id},
    # intent = the descriptive one-liner (SPEC §11), args available on expand.
    approval_id: str | None = None
    intent: str | None = None
    meta: dict[str, Any] | None = None
