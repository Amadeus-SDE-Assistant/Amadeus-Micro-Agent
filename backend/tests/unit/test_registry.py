from app.capabilities.registry import (
    SERVER_NAME,
    capability_server,
    capability_tool_names,
    write_intent,
)


def test_registry_exposes_all_eight_capabilities() -> None:
    assert capability_tool_names() == [
        "mcp__jobseeker__resume_store",
        "mcp__jobseeker__strategy_convo",
        "mcp__jobseeker__application_track",
        "mcp__jobseeker__job_search_match",
        "mcp__jobseeker__emotional_support",
        "mcp__jobseeker__profile_save",
        "mcp__jobseeker__profile_recall",
        "mcp__jobseeker__job_capture",
    ]


def test_write_tools_are_not_pre_allowed() -> None:
    from app.capabilities.registry import allowed_tool_names

    allowed = allowed_tool_names()
    # allowed_tools bypasses can_use_tool — a write tool here skips the approval
    # gate entirely (found live in the C6 demo).
    assert "mcp__jobseeker__resume_store" not in allowed
    assert "mcp__jobseeker__application_track" not in allowed  # T11.2 promotion
    assert "mcp__jobseeker__profile_save" not in allowed  # T12.2 promotion
    assert "mcp__jobseeker__job_capture" not in allowed  # T12.4 promotion
    assert len(allowed) == 4


def test_resume_store_and_application_track_are_write_tools() -> None:
    intent = write_intent("mcp__jobseeker__resume_store", {"resume_text": "a b c"})
    assert intent is not None and "3 words" in intent

    app_intent = write_intent(
        "mcp__jobseeker__application_track",
        {"company": "Acme", "title": "Backend Engineer", "status": "applied"},
    )
    assert app_intent is not None and "Acme" in app_intent and "Backend Engineer" in app_intent

    profile_intent = write_intent(
        "mcp__jobseeker__profile_save", {"facts": {"target_role": "Staff Engineer"}}
    )
    assert profile_intent is not None and "target_role: Staff Engineer" in profile_intent

    job_intent = write_intent("mcp__jobseeker__job_capture", {"posting_text": "one two three four"})
    assert job_intent is not None and "4 words" in job_intent

    for name in (
        "mcp__jobseeker__strategy_convo",
        "mcp__jobseeker__job_search_match",
        "mcp__jobseeker__emotional_support",
        "mcp__jobseeker__profile_recall",
    ):
        assert write_intent(name, {}) is None  # read-only: no approval gate


def test_capability_server_builds() -> None:
    config = capability_server()
    # SDK MCP server configs are dicts with type "sdk" and the server instance.
    assert config["type"] == "sdk"
    assert config["name"] == SERVER_NAME
