import httpx

from app.main import create_app
from app.repositories.memory import MemoryConversationRepository


def app_with_conversations(repo: MemoryConversationRepository) -> object:
    app = create_app()
    # ASGITransport doesn't run lifespan; inject the repo directly.
    app.state.conversations = repo
    return app


async def get_messages(app: object, conversation_id: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(f"/api/conversations/{conversation_id}/messages")


async def test_returns_prior_messages_in_order() -> None:
    repo = MemoryConversationRepository()
    cid = await repo.ensure_conversation("s1")
    await repo.add_message(cid, "user", {"text": "hello"})
    await repo.add_message(cid, "assistant", {"text": "hi there"})

    resp = await get_messages(app_with_conversations(repo), "s1")

    assert resp.status_code == 200
    assert [(m["role"], m["content"]["text"]) for m in resp.json()["messages"]] == [
        ("user", "hello"),
        ("assistant", "hi there"),
    ]


async def test_unknown_conversation_returns_empty_list_not_404() -> None:
    # T11.1 AC: a conversation with zero messages (e.g. a brand-new client id)
    # still mounts cleanly — this is a valid state, not a 404.
    app = app_with_conversations(MemoryConversationRepository())
    resp = await get_messages(app, "never-seen")
    assert resp.status_code == 200
    assert resp.json()["messages"] == []
