import json

import pytest

from app.ingestion.decompose import DecompositionError, parse_credentials
from app.ingestion.extract import extract_text
from app.ingestion.validate import MAX_UPLOAD_BYTES, ValidationError, validate_upload
from tests.fixtures.pdfs import scanned_like_pdf, text_layer_resume_pdf

PDF = b"%PDF-1.4 fake body"


class TestValidation:
    def test_accepts_valid_pdf(self) -> None:
        validate_upload(PDF, "application/pdf", "resume.pdf")

    @pytest.mark.parametrize(
        ("data", "content_type", "filename", "fragment"),
        [
            pytest.param(PDF, "text/plain", "resume.pdf", "content type", id="wrong-mime"),
            pytest.param(PDF, None, "resume.pdf", "content type", id="missing-mime"),
            pytest.param(PDF, "application/pdf", "resume.docx", ".pdf", id="wrong-ext"),
            pytest.param(b"", "application/pdf", "resume.pdf", "empty", id="empty"),
            pytest.param(
                b"x" * (MAX_UPLOAD_BYTES + 1), "application/pdf", "r.pdf", "limit",
                id="oversized",
            ),
            pytest.param(
                b"MZ not a pdf", "application/pdf", "resume.pdf", "magic", id="bad-magic"
            ),
        ],
    )
    def test_rejects(
        self, data: bytes, content_type: str | None, filename: str, fragment: str
    ) -> None:
        with pytest.raises(ValidationError) as exc:
            validate_upload(data, content_type, filename)
        assert fragment in exc.value.reason


class TestExtraction:
    async def test_text_layer_pdf_extracts(self) -> None:
        result = await extract_text(text_layer_resume_pdf())
        assert not result.needs_ocr
        assert result.method == "text_layer"
        assert "Acme Corp" in result.text
        assert "Example University" in result.text

    async def test_scanned_pdf_detected(self) -> None:
        result = await extract_text(scanned_like_pdf())
        assert result.needs_ocr  # near-empty text layer → pipeline runs OCR (T11.3)


class TestDecomposeParsing:
    VALID = [
        {"kind": "experience", "title": "Software Engineer", "org": "Acme",
         "start_date": "2021-03", "end_date": "2024-06",
         "body": {"bullets": ["built things"]}},
        {"kind": "skill", "title": "Languages", "body": {"bullets": ["Python"]}},
    ]

    def test_parses_valid_json(self) -> None:
        creds = parse_credentials(json.dumps(self.VALID))
        assert [c.kind for c in creds] == ["experience", "skill"]

    def test_parses_fenced_json(self) -> None:
        fenced = "```json\n" + json.dumps(self.VALID) + "\n```"
        assert len(parse_credentials(fenced)) == 2

    @pytest.mark.parametrize(
        "raw",
        [
            "not json at all",
            json.dumps([{"kind": "hobby", "title": "x"}]),  # invalid kind
            json.dumps([]),  # empty
            json.dumps([{"title": "missing kind"}]),  # schema violation
        ],
    )
    def test_rejects_bad_output(self, raw: str) -> None:
        with pytest.raises(DecompositionError):
            parse_credentials(raw)
