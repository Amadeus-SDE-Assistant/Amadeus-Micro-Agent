"""Document upload + status endpoints — thin handlers (SPEC §8); orchestration
lives in app.ingestion.service.

POST /api/documents — the user's click is the write consent for this path
(agent-initiated ingestion goes through the approval gate instead; SPEC §11).
GET /api/documents/{id} — status polling for the UI.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.ingestion.pipeline import run_pipeline
from app.ingestion.service import IngestionDeps, credentials_for_document, ingest_upload
from app.ingestion.validate import ValidationError, validate_upload
from app.repositories.base import CredentialOut, DocumentOut

router = APIRouter()


class UploadResponse(BaseModel):
    document: DocumentOut
    deduplicated: bool = False


class DocumentStatusResponse(BaseModel):
    document: DocumentOut
    credentials: list[CredentialOut] = []


def get_deps(request: Request) -> IngestionDeps:
    return IngestionDeps(
        blobs=request.app.state.blobs,
        documents=request.app.state.documents,
        credentials=request.app.state.credentials,
        candidate_id=request.app.state.default_candidate_id,
    )


@router.post("/api/documents", status_code=201)
async def upload_document(
    file: UploadFile, request: Request, background: BackgroundTasks
) -> UploadResponse:
    data = await file.read()
    try:
        validate_upload(data, file.content_type, file.filename or "")
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from exc

    deps = get_deps(request)
    result = await ingest_upload(data, file.filename or "resume.pdf", deps)
    if result.blob_uri is not None:
        runner = getattr(request.app.state, "pipeline_runner", run_pipeline)
        background.add_task(
            runner,
            result.document.id,
            deps.candidate_id,
            result.blob_uri,
            blobs=deps.blobs,
            documents=deps.documents,
            credentials=deps.credentials,
        )
    return UploadResponse(document=result.document, deduplicated=result.deduplicated)


@router.get("/api/documents/{document_id}")
async def document_status(document_id: uuid.UUID, request: Request) -> DocumentStatusResponse:
    deps = get_deps(request)
    doc = await deps.documents.get_by_id(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    mine = await credentials_for_document(deps, document_id)
    return DocumentStatusResponse(document=doc, credentials=mine)
