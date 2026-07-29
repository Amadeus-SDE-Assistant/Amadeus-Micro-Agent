import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_setup import configure_logging, log_extra, request_id_var

logger = logging.getLogger("app")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id_var.set(uuid.uuid4().hex[:12])
        response = await call_next(request)
        logger.info(
            "request",
            extra=log_extra(
                method=request.method,
                path=request.url.path,
                status=response.status_code,
            ),
        )
        return response

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        # DB and agent-subprocess liveness are wired in during P4/P3.2 (SPEC §10:
        # health must report component truth, not a bare 200).
        return {"status": "ok", "components": {"api": "ok"}}

    return app


app = create_app()
