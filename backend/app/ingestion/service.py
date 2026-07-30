"""Ingestion orchestration — keeps business logic out of route handlers (SPEC §8).

Also owns the dedupe policy: an identical file never double-ingests (SPEC §10
row 4), EXCEPT when its previous ingestion failed — a failed document may be
retried by re-uploading the same file (P8 review finding).
"""

import hashlib
import uuid
from dataclasses import dataclass

from app.repositories.base import (
    BlobStore,
    CredentialOut,
    CredentialRepository,
    DocumentOut,
    DocumentRepository,
)


@dataclass
class IngestionDeps:
    blobs: BlobStore
    documents: DocumentRepository
    credentials: CredentialRepository
    candidate_id: uuid.UUID


@dataclass
class UploadResult:
    document: DocumentOut
    deduplicated: bool
    blob_uri: str | None  # None when deduplicated (no pipeline run needed)


async def ingest_upload(data: bytes, filename: str, deps: IngestionDeps) -> UploadResult:
    sha256 = hashlib.sha256(data).hexdigest()
    existing = await deps.documents.get_by_sha256(sha256)
    if existing is not None:
        if existing.status != "failed":
            return UploadResult(document=existing, deduplicated=True, blob_uri=None)
        # Failed ingestion: same file is allowed to retry from its stored blob.
        await deps.documents.set_status(existing.id, "uploaded", error=None)
        retried = existing.model_copy(update={"status": "uploaded", "error": None})
        return UploadResult(document=retried, deduplicated=False, blob_uri=existing.uri)

    uri = await deps.blobs.put(data, filename)
    document = await deps.documents.add(deps.candidate_id, "resume", uri, sha256)
    return UploadResult(document=document, deduplicated=False, blob_uri=uri)


async def credentials_for_document(
    deps: IngestionDeps, document_id: uuid.UUID
) -> list[CredentialOut]:
    all_creds = await deps.credentials.list_for(deps.candidate_id)
    return [c for c in all_creds if c.body.get("source_document") == str(document_id)]
