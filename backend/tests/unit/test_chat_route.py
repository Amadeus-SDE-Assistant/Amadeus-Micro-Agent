from typing import Any

import httpx

from app.agent.service import AgentService
from app.main import create_app
from app.repositories.memory import MemoryConversationRepository
from tests.unit.test_agent_service import FakeClient, assistant_text, make_settings, result_ok


class BrokenConversationRepository(MemoryConversationRepository):
    async def ensure_conversation(self, sdk_session_id: str) -> Any:
        raise RuntimeError("db down")


def app_with_fake(
    fake: FakeClient, tmp_path: Any, conversations: Any | None = None
) -> Any:
    app = create_app()
    # ASGITransport doesn't run lifespan; inject service + repo directly.
    app.state.agent_service = AgentService(
        make_settings(str(tmp_path)), client_factory=lambda s: fake
    )
    app.state.conversations = conversations or MemoryConversationRepository()
    return app


async def post_chat(app: Any, message: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            "/api/chat", json={"conversation_id": "c1", "message": message}
        )


async def test_chat_streams_sse_events(tmp_path: Any) -> None:
    fake = FakeClient(script=[assistant_text("hello there"), result_ok()])
    resp = await post_chat(app_with_fake(fake, tmp_path), "hi")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "event: text" in resp.text
    assert "hello there" in resp.text
    assert "event: done" in resp.text


async def test_agent_failure_arrives_as_error_event_not_dropped_stream(tmp_path: Any) -> None:
    fake = FakeClient(fail=RuntimeError("boom"))
    resp = await post_chat(app_with_fake(fake, tmp_path), "hi")
    assert resp.status_code == 200  # stream completed cleanly
    assert "event: error" in resp.text
    assert "boom" not in resp.text  # readable message, not an internal traceback


async def test_chat_persists_user_and_assistant_messages(tmp_path: Any) -> None:
    fake = FakeClient(script=[assistant_text("streamed reply"), result_ok()])
    repo = MemoryConversationRepository()
    await post_chat(app_with_fake(fake, tmp_path, conversations=repo), "save this")
    messages = await repo.get_messages("c1")
    assert [(m.role, m.content["text"]) for m in messages] == [
        ("user", "save this"),
        ("assistant", "streamed reply"),
    ]


async def test_db_down_before_turn_returns_503(tmp_path: Any) -> None:
    fake = FakeClient(script=[assistant_text("x"), result_ok()])
    resp = await post_chat(
        app_with_fake(fake, tmp_path, conversations=BrokenConversationRepository()), "hi"
    )
    # SPEC §10 reliability row 3: clear failure, no partial writes, no hung stream.
    assert resp.status_code == 503
    assert "database" in resp.json()["detail"].lower()


async def test_chat_validates_body(tmp_path: Any) -> None:
    app = app_with_fake(FakeClient(), tmp_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chat", json={"conversation_id": "c1", "message": ""})
    assert resp.status_code == 422
