import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.agent.approvals import ApprovalGate
from app.agent.service import AgentService
from app.capabilities.context import CapabilityContext, set_capability_context
from app.config import get_settings
from app.db import check_db, create_engine, create_session_factory
from app.logging_setup import configure_logging, log_extra, request_id_var
from app.repositories.blob_fs import FsBlobStore
from app.repositories.postgres import (
    PgApprovalRepository,
    PgConversationRepository,
    PgCredentialRepository,
    PgDocumentRepository,
    ensure_default_candidate,
)
from app.routes.approvals import router as approvals_router
from app.routes.chat import router as chat_router
from app.routes.conversations import router as conversations_router
from app.routes.documents import router as documents_router

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.engine = create_engine(settings)
    app.state.session_factory = create_session_factory(app.state.engine)
    app.state.conversations = PgConversationRepository(app.state.session_factory)
    app.state.documents = PgDocumentRepository(app.state.session_factory)
    app.state.credentials = PgCredentialRepository(app.state.session_factory)
    app.state.blobs = FsBlobStore(settings.data_dir / "blobs")
    app.state.default_candidate_id = await ensure_default_candidate(
        app.state.session_factory
    )
    set_capability_context(
        CapabilityContext(
            credentials=app.state.credentials,
            candidate_id=app.state.default_candidate_id,
        )
    )
    app.state.approval_gate = ApprovalGate(
        PgApprovalRepository(app.state.session_factory),
        timeout_seconds=settings.approval_timeout_seconds,
    )
    app.state.agent_service = AgentService(gate=app.state.approval_gate)
    yield
    await app.state.agent_service.shutdown()
    await app.state.engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(chat_router)
    app.include_router(conversations_router)
    app.include_router(documents_router)
    app.include_router(approvals_router)

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
    async def health(request: Request) -> dict[str, object]:
        # SPEC §10: health reports component truth, not a bare 200. The agent
        # component reports the session pool (an approximation of subprocess
        # liveness — dead clients are dropped from the pool on failure).
        db_ok = await check_db(request.app.state.engine)
        service = request.app.state.agent_service
        components = {
            "api": "ok",
            "db": "ok" if db_ok else "unreachable",
            "agent": f"ok ({service.active_sessions} active sessions)",
        }
        return {"status": "ok" if db_ok else "degraded", "components": components}

    return app


app = create_app()
