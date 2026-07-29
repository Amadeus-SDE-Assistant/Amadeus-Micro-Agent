from app.capabilities.registry import SERVER_NAME, capability_server, capability_tool_names


def test_registry_exposes_strategy_convo() -> None:
    assert capability_tool_names() == ["mcp__jobseeker__strategy_convo"]


def test_capability_server_builds() -> None:
    config = capability_server()
    # SDK MCP server configs are dicts with type "sdk" and the server instance.
    assert config["type"] == "sdk"
    assert config["name"] == SERVER_NAME
