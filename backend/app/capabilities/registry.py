"""Capability registry — the architectural core (SPEC §3).

Every capability registers here as a tool on one in-process MCP server. Adding,
stubbing, or promoting a capability must never touch routing, the agent service,
or the frontend: this list is the single point of change.

Write capabilities additionally declare an intent builder: one plain-language
sentence describing the write, shown on the approval prompt (SPEC §11). A
capability without an intent builder is read-only and passes the gate untouched.
"""

from collections.abc import Callable
from typing import Any

from claude_agent_sdk import SdkMcpTool, create_sdk_mcp_server
from claude_agent_sdk.types import McpSdkServerConfig

from app.capabilities.job_capture import job_capture
from app.capabilities.profile import profile_recall, profile_save
from app.capabilities.resume_store import resume_store
from app.capabilities.stubs.application_track import application_track
from app.capabilities.stubs.emotional_support import emotional_support
from app.capabilities.stubs.job_search_match import job_search_match
from app.capabilities.stubs.strategy_convo import strategy_convo

SERVER_NAME = "jobseeker"

_CAPABILITIES: list[SdkMcpTool[Any]] = [
    resume_store,
    strategy_convo,
    application_track,
    job_search_match,
    emotional_support,
    profile_save,
    profile_recall,
    job_capture,
]


def _resume_store_intent(args: dict[str, Any]) -> str:
    excerpt = str(args.get("resume_text", ""))
    words = len(excerpt.split())
    return (
        f"Decompose the resume text you shared (~{words} words) into structured "
        "credentials and save them to your profile?"
    )


def _application_track_intent(args: dict[str, Any]) -> str:
    company = str(args.get("company", "")).strip() or "this company"
    title = str(args.get("title", "")).strip() or "this role"
    status = str(args.get("status", "")).strip() or "applied"
    if str(args.get("application_id", "")).strip():
        return f'Update your application to {company} for {title} to status "{status}"?'
    return f"Log your application to {company} for {title} (status: {status})?"


def _profile_save_intent(args: dict[str, Any]) -> str:
    facts = args.get("facts")
    if isinstance(facts, dict) and facts:
        pairs = "; ".join(f"{k}: {v}" for k, v in facts.items())
        return f"Save these to your profile — {pairs}?"
    return "Save this to your profile?"


def _job_capture_intent(args: dict[str, Any]) -> str:
    excerpt = str(args.get("posting_text", ""))
    words = len(excerpt.split())
    return f"Save the job posting you shared (~{words} words) so you can check your fit against it?"


_WRITE_INTENTS: dict[str, Callable[[dict[str, Any]], str]] = {
    f"mcp__{SERVER_NAME}__resume_store": _resume_store_intent,
    f"mcp__{SERVER_NAME}__application_track": _application_track_intent,
    f"mcp__{SERVER_NAME}__profile_save": _profile_save_intent,
    f"mcp__{SERVER_NAME}__job_capture": _job_capture_intent,
}


def capability_server() -> McpSdkServerConfig:
    return create_sdk_mcp_server(name=SERVER_NAME, version="0.1.0", tools=_CAPABILITIES)


def capability_tool_names() -> list[str]:
    return [f"mcp__{SERVER_NAME}__{t.name}" for t in _CAPABILITIES]


def allowed_tool_names() -> list[str]:
    """Read-only capabilities only. allowed_tools BYPASSES the permission system,
    so write tools must never appear here — they reach can_use_tool instead
    (verified live: listing resume_store here skipped the approval gate).
    """
    return [n for n in capability_tool_names() if n not in _WRITE_INTENTS]


def write_intent(tool_name: str, args: dict[str, Any]) -> str | None:
    """Descriptive intent for a write tool; None means read-only (no approval)."""
    builder = _WRITE_INTENTS.get(tool_name)
    return builder(args) if builder else None
