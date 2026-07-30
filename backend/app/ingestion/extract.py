"""Text-layer extraction via pdfplumber, with scan detection.

OCR is deferral item 1: a near-empty text layer means the file is (probably) a
scan; the pipeline stops cleanly at needs_ocr instead of failing (SPEC §2, §4).
pdfplumber is synchronous, so extraction runs in a worker thread.
"""

from dataclasses import dataclass
from io import BytesIO

import anyio.to_thread
import pdfplumber

# Below this many characters the "text layer" is treated as absent (scanned PDF).
SCAN_THRESHOLD_CHARS = 50


@dataclass
class ExtractionResult:
    text: str
    method: str  # text_layer
    needs_ocr: bool


def _extract_sync(data: bytes) -> str:
    parts: list[str] = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n\n".join(parts).strip()


async def extract_text(data: bytes) -> ExtractionResult:
    text = await anyio.to_thread.run_sync(_extract_sync, data)
    if len(text) < SCAN_THRESHOLD_CHARS:
        return ExtractionResult(text=text, method="text_layer", needs_ocr=True)
    return ExtractionResult(text=text, method="text_layer", needs_ocr=False)
