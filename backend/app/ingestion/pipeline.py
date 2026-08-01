"""Ingestion pipeline: extract → decompose → store credentials.

Runs as a background task after upload. Every stage updates document.status so the
UI (and audit) can see exactly where a file is; failures land as status=failed with
a reason and zero partial credential writes (SPEC §10 rows 5).

Status flow: uploaded → extracted → decomposed → stored
                     ↘ extracted (via OCR, SPEC §14 T11.3) → decomposed → stored
                     ↘ failed (any stage, with reason — incl. OCR unavailable)
"""

import logging
import time
import uuid

from app.ingestion.decompose import DecompositionError, decompose
from app.ingestion.extract import extract_text
from app.ingestion.ocr import OcrUnavailableError, run_ocr
from app.logging_setup import log_extra
from app.repositories.base import BlobStore, CredentialRepository, DocumentRepository

logger = logging.getLogger("app.ingestion")


async def run_pipeline(
    document_id: uuid.UUID,
    candidate_id: uuid.UUID,
    blob_uri: str,
    *,
    blobs: BlobStore,
    documents: DocumentRepository,
    credentials: CredentialRepository,
) -> None:
    started = time.monotonic()
    try:
        data = await blobs.get(blob_uri)

        extraction = await extract_text(data)
        if extraction.needs_ocr:
            await documents.set_status(document_id, "needs_ocr")
            try:
                ocr_result = await run_ocr(data)
            except OcrUnavailableError as exc:
                await documents.set_status(document_id, "failed", error=str(exc))
                logger.warning(
                    "OCR unavailable; ingestion stopped",
                    extra=log_extra(document=str(document_id)),
                )
                return
            await documents.set_status(
                document_id, "extracted", extraction_method=ocr_result.method
            )
            text = ocr_result.text
        else:
            await documents.set_status(
                document_id, "extracted", extraction_method=extraction.method
            )
            text = extraction.text

        creds = await decompose(text)
        await documents.set_status(document_id, "decomposed")

        # Tag each credential with its source document for traceability.
        for cred in creds:
            cred.body["source_document"] = str(document_id)
        await credentials.add_many(candidate_id, creds)
        await documents.set_status(document_id, "stored")
        logger.info(
            "ingestion complete",
            extra=log_extra(
                document=str(document_id),
                credentials=len(creds),
                ms=int((time.monotonic() - started) * 1000),
            ),
        )
    except DecompositionError as exc:
        await documents.set_status(document_id, "failed", error=str(exc))
        logger.warning("decomposition failed", extra=log_extra(document=str(document_id)))
    except Exception as exc:
        logger.exception("ingestion pipeline crashed")
        try:
            await documents.set_status(document_id, "failed", error=f"internal: {exc}")
        except Exception:
            logger.exception("could not record ingestion failure")
