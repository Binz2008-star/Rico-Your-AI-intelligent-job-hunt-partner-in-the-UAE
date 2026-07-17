"""
Phase 1 Reproduction Matrix — CV Upload Pipeline
Run from the worktree root: python tests/phase1_repro/run_repro.py

No PII. All synthetic fixtures generated in-memory.
No database, no HTTP server — exercises pipeline components directly
and traces the upload route's decision logic.
"""
from __future__ import annotations

import io
import json
import sys
import os
import traceback
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# ── Fixture generation ──────────────────────────────────────────────────────

def make_valid_multipage_pdf(pages: int = 3) -> bytes:
    """Create a synthetic text-based multi-page PDF with no PII."""
    import fitz
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i+1} of {pages}")
        page.insert_text((72, 120), f"Senior Safety Officer with {5+i} years experience")
        page.insert_text((72, 160), f"Skills: HSE, ISO 45001, Risk Assessment, Audit")
        page.insert_text((72, 200), f"Certifications: NEBOSH, IOSH")
        page.insert_text((72, 240), f"Languages: English, Arabic")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_empty_pdf() -> bytes:
    """A valid PDF with no text content."""
    import fitz
    doc = fitz.open()
    doc.new_page()
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_scanned_pdf() -> bytes:
    """A PDF with only an image (no text layer) — simulates a scan."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    # Draw a rectangle to simulate an image-only page
    rect = fitz.Rect(50, 50, 550, 800)
    page.draw_rect(rect, color=(0.8, 0.8, 0.8), fill=(0.9, 0.9, 0.9))
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_corrupt_renamed_pdf() -> bytes:
    """Not a PDF at all, just garbage bytes."""
    return b"This is not a PDF file \x00\x01\x02 garbage data " * 100


def make_oversized_pdf(target_mb: int = 26) -> bytes:
    """A PDF larger than 25MB."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    # Insert a large amount of text to inflate the file
    big_text = "A" * (target_mb * 1024 * 1024 // 2)
    page.insert_text((72, 72), big_text[:5000])
    # Add a large stream object to pad the PDF
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    data = buf.getvalue()
    # Pad to target size with null bytes appended after PDF trailer
    # (this makes it oversized but still starts with %PDF)
    if len(data) < target_mb * 1024 * 1024:
        data = data + b"\x00" * (target_mb * 1024 * 1024 - len(data))
    return data


def make_non_cv_pdf() -> bytes:
    """A text-based PDF that is clearly not a CV (an invoice)."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "INVOICE #INV-2026-001")
    page.insert_text((72, 120), "Bill To: ACME Corporation")
    page.insert_text((72, 160), "Amount Due: AED 15,000.00")
    page.insert_text((72, 200), "Payment Terms: Net 30 Days")
    page.insert_text((72, 240), "Item: Consulting Services - 40 hours")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_garbage_pdf() -> bytes:
    """A file that starts with %PDF but has corrupt content that PyMuPDF can't parse."""
    return b"%PDF-1.4\nThis is corrupt PDF content\n%%EOF\n" + b"\x00" * 500


# ── Pipeline trace ───────────────────────────────────────────────────────────

def trace_pipeline(data: bytes, filename: str) -> dict:
    """Run data through each pipeline stage and capture results."""
    result = {
        "input_fixture": filename,
        "size_bytes": len(data),
        "real_signature": data[:8].hex() if len(data) >= 8 else data.hex(),
        "magic_first4": data[:4].decode("ascii", errors="replace"),
    }

    # Stage 1: detect_format
    try:
        from src.services.document_classifier import detect_format
        fmt = detect_format(data, filename)
        result["detect_format"] = fmt
    except Exception as e:
        result["detect_format"] = f"ERROR: {e}"

    # Stage 2: classify_document
    try:
        from src.services.document_classifier import classify_document
        classification = classify_document(data, filename)
        result["classification_doc_type"] = classification.document_type
        result["classification_confidence"] = round(classification.confidence, 3)
        result["classification_file_format"] = classification.file_format
        result["classification_display_label"] = classification.display_label
        result["classification_metadata_chars"] = classification.metadata.get("chars", 0)
    except Exception as e:
        result["classification_doc_type"] = f"ERROR: {e}"
        result["classification_confidence"] = None
        result["classification_file_format"] = None

    # Stage 3: CVParser.parse_bytes
    try:
        from src.cv_parser import CVParser
        parser = CVParser()
        parsed = parser.parse_bytes(data, filename=filename)
        result["parser_text_len"] = len(parsed.text)
        result["parser_extraction_quality"] = parsed.extraction_quality
        result["parser_extracted_chars"] = parsed.extracted_chars
        result["parser_skills"] = parsed.skills
        result["parser_name"] = parsed.name
        result["parser_current_role"] = parsed.current_role
        result["parser_document_type"] = parsed.document_type
        result["parser_emails"] = parsed.emails
        result["parser_phones"] = parsed.phones
        # Check if text is garbage (non-printable ratio)
        text = parsed.text
        if text:
            printable = sum(1 for c in text if c.isprintable() or c in "\n\r\t ")
            result["parser_printable_ratio"] = round(printable / len(text), 3)
        else:
            result["parser_printable_ratio"] = None
        # Page count check for PDFs
        if data[:4] == b"%PDF":
            try:
                import fitz
                doc = fitz.open(stream=data, filetype="pdf")
                result["pdf_page_count"] = doc.page_count
                # Check what the parser actually extracted per page
                page_texts = [page.get_text() for page in doc]
                result["pdf_pages_expected"] = len(page_texts)
                result["pdf_pages_with_text"] = sum(1 for t in page_texts if t.strip())
                result["pdf_total_extracted_chars"] = sum(len(t) for t in page_texts)
                doc.close()
            except Exception as e:
                result["pdf_page_count"] = f"ERROR: {e}"
                result["pdf_pages_expected"] = None
                result["pdf_pages_with_text"] = None
    except Exception as e:
        result["parser_text_len"] = f"ERROR: {e}"
        result["parser_extraction_quality"] = None
        result["parser_extracted_chars"] = None

    # Stage 4: Route decision trace
    # Trace the upload route's logic to determine what status it would return
    doc_type = result.get("classification_doc_type", "unknown")
    file_format = result.get("classification_file_format", "unknown")
    confidence = result.get("classification_confidence", 0) or 0
    extracted_chars = result.get("classification_metadata_chars", 0) or 0
    quality = result.get("parser_extraction_quality", "unknown")

    _CV_PIPELINE_TYPES = {"cv", "cover_letter", "unknown"}
    _NEAR_EMPTY_CHARS = 25
    _NO_TEXT_MIN_BYTES = 1024
    text_bearing_format = file_format in ("pdf", "doc", "docx", "text")

    route = "UNKNOWN"
    if file_format == "executable":
        route = "REJECT_422_executable"
    elif file_format == "image":
        route = "IMAGE_PATH"
    elif doc_type == "identity_document":
        route = "REJECT_identity_document"
    elif text_bearing_format and len(data) >= _NO_TEXT_MIN_BYTES and (
        doc_type == "no_text"
        or (doc_type == "unknown" and confidence <= 0.0 and extracted_chars < _NEAR_EMPTY_CHARS)
    ):
        route = "CLASSIFIED_no_text"
    elif doc_type not in _CV_PIPELINE_TYPES:
        route = "CLASSIFIED_non_cv"
    else:
        # Enters CV extraction pipeline
        if quality == "poor":
            route = "PREVIEW_READY_poor_quality"
        elif quality == "partial":
            route = "PREVIEW_READY_partial"
        elif quality == "good":
            route = "PREVIEW_READY_good"
        else:
            route = "PREVIEW_READY_unknown_quality"

    result["route_decision"] = route

    # Stage 5: Would artifact be created?
    # In the route, artifact is created for authenticated users when status == preview_ready
    would_create_artifact = route.startswith("PREVIEW_READY")
    result["artifact_would_be_created"] = would_create_artifact

    # Stage 6: Would confirm proceed?
    # Confirm requires a valid artifact. If artifact was created, confirm can proceed.
    # The key question: can a poor/garbage parse produce preview_ready → artifact → confirm → user_document + active CV?
    would_confirm_proceed = would_create_artifact
    result["confirm_would_proceed"] = would_confirm_proceed

    # Stage 7: Would active CV be created?
    # In confirm, is_primary = (_resolved_doc_type == "cv")
    # _resolved_doc_type comes from artifact["doc_type"] which comes from the upload route's doc_type
    # doc_type at upload time is the classification result
    resolved_doc_type = doc_type if doc_type in ("cv", "cover_letter", "other") else "other"
    would_create_active_cv = would_confirm_proceed and (resolved_doc_type == "cv")
    result["active_cv_would_be_created"] = would_create_active_cv

    # Stage 8: Would profile be updated?
    result["profile_would_be_updated"] = would_confirm_proceed

    return result


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    fixtures = [
        ("valid_multipage_cv.pdf", make_valid_multipage_pdf(3)),
        ("VALID_MULTIPAGE_CV.PDF", make_valid_multipage_pdf(3)),  # uppercase extension
        ("empty.pdf", make_empty_pdf()),
        ("scanned_image_only.pdf", make_scanned_pdf()),
        ("corrupt_renamed.pdf", make_corrupt_renamed_pdf()),
        ("garbage_pdf.pdf", make_garbage_pdf()),
        ("non_cv_invoice.pdf", make_non_cv_pdf()),
        ("oversized.pdf", make_oversized_pdf(26)),
    ]

    # Also test MIME mismatch: valid PDF content with application/octet-stream
    # (MIME is a browser header, not a file property — detect_format uses magic bytes)
    # We simulate this by just running the valid PDF through with a generic filename
    fixtures.append(("valid_pdf_octet_stream.bin", make_valid_multipage_pdf(3)))

    results = []
    for filename, data in fixtures:
        print(f"\n{'='*60}")
        print(f"Fixture: {filename}")
        print(f"Size: {len(data)} bytes")
        print(f"{'='*60}")
        try:
            r = trace_pipeline(data, filename)
            results.append(r)
            for k, v in r.items():
                print(f"  {k}: {v}")
        except Exception as e:
            print(f"  FATAL ERROR: {e}")
            traceback.print_exc()
            results.append({"input_fixture": filename, "FATAL_ERROR": str(e)})

    # Summary table
    print(f"\n\n{'='*80}")
    print("REPRODUCTION MATRIX SUMMARY")
    print(f"{'='*80}")
    print(f"{'Fixture':<30} {'Size':>10} {'Format':<10} {'Class':<20} {'Qual':<10} {'Route':<30} {'Artifact':<8} {'ActiveCV':<8}")
    print(f"{'-'*30} {'-'*10} {'-'*10} {'-'*20} {'-'*10} {'-'*30} {'-'*8} {'-'*8}")
    for r in results:
        fname = r.get("input_fixture", "?")
        size = r.get("size_bytes", "?")
        fmt = r.get("detect_format", "?")
        cls = r.get("classification_doc_type", "?")
        qual = r.get("parser_extraction_quality", "?")
        route = r.get("route_decision", "?")
        artifact = r.get("artifact_would_be_created", "?")
        active = r.get("active_cv_would_be_created", "?")
        print(f"{str(fname):<30} {str(size):>10} {str(fmt):<10} {str(cls):<20} {str(qual):<10} {str(route):<30} {str(artifact):<8} {str(active):<8}")

    # Critical hypothesis
    print(f"\n\n{'='*80}")
    print("CRITICAL HYPOTHESIS: Can parser failure/garbage produce active CV?")
    print(f"{'='*80}")
    for r in results:
        route = r.get("route_decision", "")
        if route.startswith("PREVIEW_READY"):
            fname = r.get("input_fixture", "?")
            qual = r.get("parser_extraction_quality", "?")
            printable = r.get("parser_printable_ratio", "?")
            text_len = r.get("parser_text_len", "?")
            active = r.get("active_cv_would_be_created", "?")
            print(f"\n  {fname}:")
            print(f"    Route: {route}")
            print(f"    Quality: {qual}")
            print(f"    Text length: {text_len}")
            print(f"    Printable ratio: {printable}")
            print(f"    Active CV would be created: {active}")
            if qual == "poor" or (printable is not None and printable < 0.5):
                print(f"    *** HIGH RISK: Garbage/poor parse can produce active CV ***")

    # Save full results as JSON
    out_path = Path(__file__).resolve().parent / "repro_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nFull results saved to: {out_path}")


if __name__ == "__main__":
    main()
