"""OCR fallback (SPEC §14 T11.3) — engages when extract_text flags needs_ocr."""

import pytest

from app.ingestion.extract import extract_text
from app.ingestion.ocr import OcrUnavailableError, run_ocr
from tests.fixtures.pdfs import scanned_resume_pdf_with_ocr_text


async def test_ocr_reads_text_rasterized_into_a_scanned_pdf() -> None:
    pdf = scanned_resume_pdf_with_ocr_text()
    # Confirm the fixture actually behaves like a scan first (empty text layer).
    extracted = await extract_text(pdf)
    assert extracted.needs_ocr

    result = await run_ocr(pdf)
    assert result.method == "ocr"
    assert "Jordan Doe" in result.text
    assert "Acme Corp" in result.text


async def test_missing_tesseract_raises_ocr_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.ingestion.ocr as ocr_module

    monkeypatch.setattr(ocr_module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(ocr_module, "_COMMON_INSTALL_PATHS", [])

    with pytest.raises(OcrUnavailableError):
        await run_ocr(scanned_resume_pdf_with_ocr_text())
