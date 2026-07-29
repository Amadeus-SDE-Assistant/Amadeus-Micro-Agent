"""Structured JSON logging (SPEC §10 observability).

Every log line is one JSON object. `request_id` and `session_id` are carried in
contextvars so any log call inside a request/agent turn is automatically tagged.
Resume content (PII) must never be logged — log IDs and counts instead (SPEC §10).
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if (rid := request_id_var.get()) is not None:
            payload["request_id"] = rid
        if (sid := session_id_var.get()) is not None:
            payload["session_id"] = sid
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def log_extra(**fields: Any) -> dict[str, dict[str, Any]]:
    """Usage: logger.info("tool invoked", extra=log_extra(tool="resume_store", ms=123))"""
    return {"extra_fields": fields}
