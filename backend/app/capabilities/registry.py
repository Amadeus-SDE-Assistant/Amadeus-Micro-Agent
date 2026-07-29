"""Capability registry — the architectural core (SPEC §3).

Every capability registers here as a tool on one in-process MCP server. Adding,
stubbing, or promoting a capability must never touch routing, the agent service,
or the frontend: this list is the single point of change.
"""

from claude_agent_sdk import SdkMcpTool, create_sdk_mcp_server
from claude_agent_sdk.types import McpSdkServerConfig

from app.capabilities.stubs.strategy_convo import strategy_convo

SERVER_NAME = "jobseeker"

_CAPABILITIES: list[SdkMcpTool[object]] = [
    strategy_convo,
    # P6: resume_store (real), application_track, job_search_match, emotional_support
]


def capability_server() -> McpSdkServerConfig:
    return create_sdk_mcp_server(name=SERVER_NAME, version="0.1.0", tools=_CAPABILITIES)


def capability_tool_names() -> list[str]:
    return [f"mcp__{SERVER_NAME}__{t.name}" for t in _CAPABILITIES]
