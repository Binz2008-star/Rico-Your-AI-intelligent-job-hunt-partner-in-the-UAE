"""Regression: DOCX decompression-bomb guard covers the classifier path too.

Before this fix the bomb guard lived only in ``cv_parser._parse_docx``, but the
upload document classifier runs FIRST on the raw bytes and had its own,
unguarded ``_extract_docx`` — so a bomb reached ``python-docx``/lxml there and
inflated before the CV parser was ever called (OOM-DoS on a small instance).

These tests build a tiny ``.docx`` (a ZIP) whose central directory declares a
large uncompressed member, and assert the shared guard fires on BOTH consumers.
"""
from __future__ import annotations

import io
import zipfile

import pytest

from src.services.docx_safety import (
    MAX_DOCX_RATIO,
    MAX_DOCX_UNCOMPRESSED,
    is_docx_bomb,
)
from src.services.document_classifier import DocumentClassifier


def _make_docx_bomb() -> bytes:
    """A valid ZIP with an 11 MB highly-compressible member.

    Inflated total (~11 MB) is above the 10 MB ratio floor and the
    compressed→uncompressed ratio (~1000:1) is far above the 200 ceiling, so it
    trips the ratio branch of the guard while the on-disk bytes stay tiny.
    """
    payload = b"\x00" * (11 * 1024 * 1024)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", payload)
    return buf.getvalue()


def _make_normal_docx(text: str = "Senior Data Engineer — 8 years") -> bytes:
    try:
        from docx import Document
    except Exception:  # pragma: no cover - python-docx always present in CI
        pytest.skip("python-docx not installed")
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_bomb_is_detected_from_metadata_only():
    bomb = _make_docx_bomb()
    # The malicious file is tiny on disk despite declaring ~11 MB inflated.
    assert len(bomb) < 1 * 1024 * 1024
    assert is_docx_bomb(bomb) is True


def test_normal_docx_is_not_flagged():
    normal = _make_normal_docx()
    assert is_docx_bomb(normal) is False


def test_non_zip_bytes_fall_through():
    # A mislabelled .docx that is not a real zip must not be treated as a bomb;
    # the caller's normal parse/fallback path handles it.
    assert is_docx_bomb(b"this is plain text, not a zip") is False
    assert is_docx_bomb(b"") is False


def test_classifier_extract_docx_refuses_bomb():
    # This is the path that was unguarded: the classifier runs before the CV
    # parser. It must now return empty text instead of inflating the payload.
    bomb = _make_docx_bomb()
    text = DocumentClassifier()._extract_docx(bomb)
    assert text == ""


def test_classifier_extract_docx_still_reads_normal_docx():
    normal = _make_normal_docx("Marketing Manager Dubai")
    text = DocumentClassifier()._extract_docx(normal)
    assert "Marketing Manager Dubai" in text


def test_thresholds_are_the_shared_source_of_truth():
    # cv_parser re-exports these; guard both consumers stay pinned to one value.
    assert MAX_DOCX_UNCOMPRESSED == 200 * 1024 * 1024
    assert MAX_DOCX_RATIO == 200
