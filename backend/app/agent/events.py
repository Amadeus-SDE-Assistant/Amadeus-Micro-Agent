"""Event envelope streamed to clients (SSE) — including errors (SPEC §10: fail loudly)."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class AgentEventType(StrEnum):
    TEXT = "text"
    TOOL_USE = "tool_use"
    DONE = "done"
    ERROR = "error"


class AgentEvent(BaseModel):
    type: AgentEventType
    text: str | None = None
    tool_name: str | None = None
    meta: dict[str, Any] | None = None
