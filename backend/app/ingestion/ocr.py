"""OCR fallback via Tesseract (SPEC §14 T11.3, deferral item 1 from SPEC §2).

Engages only when extract_text() flags needs_ocr. Rasterizes each page with
pdfplumber's own image renderer (already backed by pypdfium2, no new PDF
dependency) and runs pytesseract over the resulting image. Tesseract is a
system binary, not a Python package — pytesseract just shells out to it — so
a missing install must fail loudly (SPEC §10), never crash the background
pipeline task with an opaque exception.
"""

import shutil
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import anyio.to_thread
import pdfplumber
import pytesseract

# Windows winget install location (UB-Mannheim.TesseractOCR) isn't always on
# PATH for a process started before the install — check it explicitly.
_COMMON_INSTALL_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


class OcrUnavailableError(Exception):
    """Tesseract isn't installed or discoverable."""


@dataclass
class OcrResult:
    text: str
    method: str  # "ocr"


def _locate_tesseract() -> str:
    on_path = shutil.which("tesseract")
    if on_path:
        return on_path
    for candidate in _COMMON_INSTALL_PATHS:
        if Path(candidate).exists():
            return candidate
    raise OcrUnavailableError(
        "Tesseract isn't installed or on PATH. Install it (e.g. `winget install "
        "--id UB-Mannheim.TesseractOCR -e`) to enable OCR for scanned resumes."
    )


def _run_ocr_sync(data: bytes) -> str:
    pytesseract.pytesseract.tesseract_cmd = _locate_tesseract()
    parts: list[str] = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        for page in pdf.pages:
            image = page.to_image(resolution=200).original
            parts.append(str(pytesseract.image_to_string(image)))
    return "\n\n".join(p.strip() for p in parts).strip()


async def run_ocr(data: bytes) -> OcrResult:
    text = await anyio.to_thread.run_sync(_run_ocr_sync, data)
    return OcrResult(text=text, method="ocr")
