"""Document upload + status endpoints.

POST /api/documents — validate, dedupe by sha256, store blob + row, then run the
ingestion pipeline in the background. The user's click is the write consent for
this path (agent-initiated ingestion goes through the approval gate in P6).
GET /api/documents/{id} — status polling for the UI, including stored credentials.
"""

import hashlib
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.ingestion.pipeline import run_pipeline
from app.ingestion.validate import ValidationError, validate_upload
from app.repositories.base import (
    BlobStore,
    CredentialOut,
    CredentialRepository,
    DocumentOut,
    DocumentRepository,
)

logger = logging.getLogger("app.documents")

router = APIRouter()


class UploadResponse(BaseModel):
    document: DocumentOut
    deduplicated: bool = False


class DocumentStatusResponse(BaseModel):
    document: DocumentOut
    credentials: list[CredentialOut] = []


@router.post("/api/documents", status_code=201)
async def upload_document(
    file: UploadFile, request: Request, background: BackgroundTasks
) -> UploadResponse:
    data = await file.read()
    try:
        validate_upload(data, file.content_type, file.filename or "")
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from exc

    documents: DocumentRepository = request.app.state.documents
    blobs: BlobStore = request.app.state.blobs
    credentials: CredentialRepository = request.app.state.credentials
    candidate_id: uuid.UUID = request.app.state.default_candidate_id

    sha256 = hashlib.sha256(data).hexdigest()
    existing = await documents.get_by_sha256(sha256)
    if existing is not None:
        # SPEC §10 reliability row 4: same file never double-ingests.
        return UploadResponse(document=existing, deduplicated=True)

    uri = await blobs.put(data, file.filename or "resume.pdf")
    document = await documents.add(candidate_id, "resume", uri, sha256)
    runner = getattr(request.app.state, "pipeline_runner", run_pipeline)
    background.add_task(
        runner,
        document.id,
        candidate_id,
        uri,
        blobs=blobs,
        documents=documents,
        credentials=credentials,
    )
    return UploadResponse(document=document)


@router.get("/api/documents/{document_id}")
async def document_status(document_id: uuid.UUID, request: Request) -> DocumentStatusResponse:
    documents: DocumentRepository = request.app.state.documents
    credentials: CredentialRepository = request.app.state.credentials
    candidate_id: uuid.UUID = request.app.state.default_candidate_id

    # Lookup is by sha in the repo protocol; add a direct-id fetch via listing.
    all_creds = await credentials.list_for(candidate_id)
    doc = await documents.get_by_id(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    mine = [c for c in all_creds if c.body.get("source_document") == str(document_id)]
    return DocumentStatusResponse(document=doc, credentials=mine)
