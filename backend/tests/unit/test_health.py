import json
import logging

import httpx
import pytest

from app.config import Settings
from app.db import create_engine
from app.logging_setup import JsonFormatter, log_extra, request_id_var
from app.main import create_app


@pytest.fixture
def app():  # type: ignore[no-untyped-def]
    application = create_app()
    # ASGITransport doesn't run lifespan; point the engine at a dead port so the
    # health check exercises its truthful-degraded path (SPEC §10).
    application.state.engine = create_engine(
        Settings(database_url="postgresql+asyncpg://x:x@localhost:59999/x")  # type: ignore[call-arg]
    )
    return application


async def test_health_reports_db_truthfully(app) -> None:  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    # DB is unreachable in this fixture — health must say so, not lie with "ok".
    assert body["status"] == "degraded"
    assert body["components"]["db"] == "unreachable"
    assert body["components"]["api"] == "ok"


def test_log_lines_are_json_with_request_id() -> None:
    token = request_id_var.set("req-abc123")
    try:
        record = logging.LogRecord(
            name="app", level=logging.INFO, pathname=__file__, lineno=1,
            msg="request", args=(), exc_info=None,
        )
        record.extra_fields = log_extra(status=200)["extra_fields"]
        line = JsonFormatter().format(record)
    finally:
        request_id_var.reset(token)
    payload = json.loads(line)
    assert payload["request_id"] == "req-abc123"
    assert payload["status"] == 200
    assert {"ts", "level", "msg"} <= payload.keys()
