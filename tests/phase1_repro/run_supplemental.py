"""
Phase 1 Supplemental: Test no_text guard boundary at 1024 bytes
and trace what the parser actually extracts from the valid CV.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

def make_large_scanned_pdf() -> bytes:
    """A scanned/image-only PDF >= 1024 bytes with no text layer."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    # Draw multiple shapes to inflate the PDF past 1024 bytes
    for i in range(20):
        rect = fitz.Rect(50 + i*10, 50 + i*10, 200 + i*10, 200 + i*10)
        page.draw_rect(rect, color=(0.5, 0.5, 0.5), fill=(0.8, 0.8, 0.8))
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()

def make_large_empty_pdf() -> bytes:
    """A valid PDF with no text but >= 1024 bytes (multiple empty pages)."""
    import fitz
    doc = fitz.open()
    for i in range(5):
        doc.new_page()
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()

def trace_pipeline(data: bytes, filename: str) -> dict:
    result = {
        "input_fixture": filename,
        "size_bytes": len(data),
    }
    from src.services.document_classifier import detect_format, classify_document
    from src.cv_parser import CVParser

    fmt = detect_format(data, filename)
    result["detect_format"] = fmt

    classification = classify_document(data, filename)
    result["doc_type"] = classification.document_type
    result["confidence"] = round(classification.confidence, 3)
    result["file_format"] = classification.file_format
    result["metadata_chars"] = classification.metadata.get("chars", 0)

    parser = CVParser()
    parsed = parser.parse_bytes(data, filename=filename)
    result["parser_text_len"] = len(parsed.text)
    result["quality"] = parsed.extraction_quality
    result["skills"] = parsed.skills
    result["text_preview"] = parsed.text[:200] if parsed.text else "(empty)"

    # Route decision
    _NEAR_EMPTY_CHARS = 25
    _NO_TEXT_MIN_BYTES = 1024
    text_bearing_format = classification.file_format in ("pdf", "doc", "docx", "text")
    no_text_guard = (
        text_bearing_format
        and len(data) >= _NO_TEXT_MIN_BYTES
        and (
            classification.document_type == "no_text"
            or (classification.document_type == "unknown" and classification.confidence <= 0.0
                and int(classification.metadata.get("chars", 0) or 0) < _NEAR_EMPTY_CHARS)
        )
    )
    result["no_text_guard_triggers"] = no_text_guard
    result["route"] = "CLASSIFIED_no_text" if no_text_guard else (
        "PREVIEW_READY" if classification.document_type in ("cv", "cover_letter", "unknown") else "CLASSIFIED_non_cv"
    )
    return result

def main():
    fixtures = [
        ("large_scanned_pdf.pdf", make_large_scanned_pdf()),
        ("large_empty_pdf.pdf", make_large_empty_pdf()),
    ]

    for filename, data in fixtures:
        print(f"\n{'='*60}")
        print(f"Fixture: {filename} ({len(data)} bytes)")
        print(f"{'='*60}")
        r = trace_pipeline(data, filename)
        for k, v in r.items():
            print(f"  {k}: {v}")

    # Also print the actual extracted text from the valid CV
    print(f"\n{'='*60}")
    print("Valid CV text extraction detail:")
    print(f"{'='*60}")
    import fitz
    from src.cv_parser import CVParser

    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i+1} of 3")
        page.insert_text((72, 120), f"Senior Safety Officer with {5+i} years experience")
        page.insert_text((72, 160), f"Skills: HSE, ISO 45001, Risk Assessment, Audit")
        page.insert_text((72, 200), f"Certifications: NEBOSH, IOSH")
        page.insert_text((72, 240), f"Languages: English, Arabic")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    pdf_data = buf.getvalue()

    # Extract with PyMuPDF directly
    doc2 = fitz.open(stream=pdf_data, filetype="pdf")
    for i, page in enumerate(doc2):
        text = page.get_text()
        print(f"  Page {i+1} raw text ({len(text)} chars): {repr(text[:200])}")
    doc2.close()

    # Parse with CVParser
    parser = CVParser()
    parsed = parser.parse_bytes(pdf_data, filename="valid_cv.pdf")
    print(f"\n  Parser text ({len(parsed.text)} chars): {repr(parsed.text[:300])}")
    print(f"  Skills: {parsed.skills}")
    print(f"  Quality: {parsed.extraction_quality}")

if __name__ == "__main__":
    main()
