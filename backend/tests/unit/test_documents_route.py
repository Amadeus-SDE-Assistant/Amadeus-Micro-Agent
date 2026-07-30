import uuid
from typing import Any

import httpx

from app.main import create_app
from app.repositories.memory import (
    MemoryBlobStore,
    MemoryCredentialRepository,
    MemoryDocumentRepository,
)
from tests.fixtures.pdfs import text_layer_resume_pdf


def make_app() -> Any:
    app = create_app()
    app.state.documents = MemoryDocumentRepository()
    app.state.credentials = MemoryCredentialRepository()
    app.state.blobs = MemoryBlobStore()
    app.state.default_candidate_id = uuid.uuid4()
    app.state.pipeline_calls = []

    async def record_pipeline(*args: Any, **kwargs: Any) -> None:
        app.state.pipeline_calls.append(args)

    app.state.pipeline_runner = record_pipeline
    return app


async def upload(app: Any, data: bytes, filename: str = "resume.pdf") -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            "/api/documents",
            files={"file": (filename, data, "application/pdf")},
        )


async def test_upload_stores_blob_row_and_schedules_pipeline() -> None:
    app = make_app()
    resp = await upload(app, text_layer_resume_pdf())
    assert resp.status_code == 201
    body = resp.json()
    assert body["document"]["status"] == "uploaded"
    assert body["deduplicated"] is False
    assert len(app.state.pipeline_calls) == 1  # pipeline scheduled exactly once


async def test_duplicate_upload_dedupes() -> None:
    app = make_app()
    data = text_layer_resume_pdf()
    first = await upload(app, data)
    second = await upload(app, data)
    assert second.status_code == 201
    assert second.json()["deduplicated"] is True
    assert second.json()["document"]["id"] == first.json()["document"]["id"]
    assert len(app.state.pipeline_calls) == 1  # not scheduled again


async def test_failed_ingestion_can_retry_by_reupload() -> None:
    # P8 review finding: dedupe must not permanently block a failed document.
    app = make_app()
    data = text_layer_resume_pdf()
    first = await upload(app, data)
    doc_id = uuid.UUID(first.json()["document"]["id"])
    await app.state.documents.set_status(doc_id, "failed", error="boom")

    retry = await upload(app, data)
    assert retry.json()["deduplicated"] is False
    assert retry.json()["document"]["id"] == str(doc_id)  # same document, retried
    assert len(app.state.pipeline_calls) == 2  # pipeline scheduled again
    stored = await app.state.documents.get_by_id(doc_id)
    assert stored.status == "uploaded" and stored.error is None


async def test_invalid_upload_rejected_422() -> None:
    app = make_app()
    resp = await upload(app, b"MZ definitely not a pdf")
    assert resp.status_code == 422
    assert "magic" in resp.json()["detail"]
    assert app.state.pipeline_calls == []


async def test_status_endpoint_returns_document_and_credentials() -> None:
    app = make_app()
    resp = await upload(app, text_layer_resume_pdf())
    doc_id = resp.json()["document"]["id"]

    from app.repositories.base import CredentialIn

    await app.state.credentials.add_many(
        app.state.default_candidate_id,
        [CredentialIn(kind="skill", title="Python",
                      body={"source_document": doc_id})],
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        status = await client.get(f"/api/documents/{doc_id}")
        missing = await client.get(f"/api/documents/{uuid.uuid4()}")

    assert status.status_code == 200
    assert status.json()["document"]["id"] == doc_id
    assert [c["title"] for c in status.json()["credentials"]] == ["Python"]
    assert missing.status_code == 404
