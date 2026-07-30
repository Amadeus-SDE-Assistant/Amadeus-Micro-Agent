"""Upload validation: MIME, size, magic bytes (SPEC §4 pipeline, §10 security)."""

from dataclasses import dataclass

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {"application/pdf"}
PDF_MAGIC = b"%PDF-"


@dataclass
class ValidationError(Exception):
    reason: str


def validate_upload(data: bytes, content_type: str | None, filename: str) -> None:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(f"unsupported content type: {content_type or 'missing'}")
    if not filename.lower().endswith(".pdf"):
        raise ValidationError("only .pdf files are accepted")
    if len(data) == 0:
        raise ValidationError("file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError(f"file exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
    if not data.startswith(PDF_MAGIC):
        raise ValidationError("file content is not a PDF (magic bytes mismatch)")
