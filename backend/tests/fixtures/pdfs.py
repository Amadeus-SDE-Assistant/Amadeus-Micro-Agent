"""Synthetic PDF fixtures — never real resume data (SPEC §11)."""

from io import BytesIO

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

SYNTHETIC_RESUME_TEXT = [
    "Jordan Doe",
    "jordan.doe@example.com | Example City",
    "",
    "EXPERIENCE",
    "Software Engineer, Acme Corp (2021-03 - 2024-06)",
    "- Built a payments reconciliation service handling 2M events/day",
    "- Led migration from monolith to services, cutting deploy time 80%",
    "",
    "Junior Developer, Beta LLC (2019-07 - 2021-02)",
    "- Maintained internal CRM tools in Python and React",
    "",
    "EDUCATION",
    "B.S. Computer Science, Example University (2015-09 - 2019-05)",
    "",
    "SKILLS",
    "Languages: Python, TypeScript, SQL",
    "Cloud: AWS, Docker, Postgres",
]


def text_layer_resume_pdf() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in SYNTHETIC_RESUME_TEXT:
        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def scanned_like_pdf() -> bytes:
    """A page with no text layer — what a scan looks like to pdfplumber."""
    pdf = FPDF()
    pdf.add_page()
    pdf.rect(10, 10, 190, 277)
    return bytes(pdf.output())


def scanned_resume_pdf_with_ocr_text() -> bytes:
    """A page with the resume text rasterized as an image, not real glyphs —
    pdfplumber's text layer is empty (needs_ocr), but Tesseract can read it
    (T11.3 OCR fallback test fixture).
    """
    image = Image.new("RGB", (1400, 400), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=48)
    draw.text((20, 20), "Jordan Doe", fill="black", font=font)
    draw.text((20, 140), "Software Engineer, Acme Corp", fill="black", font=font)
    draw.text((20, 260), "B.S. Computer Science, Example University", fill="black", font=font)

    buf = BytesIO()
    image.save(buf, format="PNG")

    pdf = FPDF()
    pdf.add_page()
    pdf.image(buf, x=10, y=10, w=190)
    return bytes(pdf.output())
