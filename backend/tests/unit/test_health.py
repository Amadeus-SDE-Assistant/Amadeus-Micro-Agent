import json
import logging

import httpx
import pytest

from app.logging_setup import JsonFormatter, log_extra, request_id_var
from app.main import create_app


@pytest.fixture
def app():  # type: ignore[no-untyped-def]
    return create_app()


async def test_health_returns_component_status(app) -> None:  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "components" in body  # SPEC §10: health reports components, not a bare 200


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
