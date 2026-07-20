"""Shared DOCX decompression-bomb guard.

A ``.docx`` is a ZIP container. A few-KB file can legally declare gigabytes of
uncompressed content (DEFLATE reaches ~1000:1), so any code path that hands raw
upload bytes to ``python-docx`` / lxml must first inspect the ZIP central
directory — metadata only, nothing is inflated — and refuse an oversized
declaration before the parser allocates memory.

Two paths consume the same upload bytes: the upload document classifier
(``src/services/document_classifier.py``, which runs FIRST during classification)
and the CV parser (``src/cv_parser.py``). Previously only the CV parser carried
the guard, so a bomb reached ``document_classifier._extract_docx`` and inflated
there before the CV parser was ever called. This module is the single guard both
import, so the check can never diverge again.
"""
from __future__ import annotations

import io
import logging
import zipfile

logger = logging.getLogger(__name__)

# Total inflated-size ceiling summed across all zip members.
MAX_DOCX_UNCOMPRESSED = 200 * 1024 * 1024  # 200 MB
# Compressed→uncompressed ratio ceiling. Only enforced past a 10 MB inflated
# floor so a small, legitimately-compressible document is never rejected on
# ratio alone.
MAX_DOCX_RATIO = 200
_RATIO_FLOOR = 10 * 1024 * 1024  # 10 MB


def is_docx_bomb(data: bytes) -> bool:
    """Return True when *data* is a ZIP whose declared inflated size is unsafe.

    Reads only ``ZipInfo.file_size`` (central-directory metadata) — nothing is
    decompressed, so an oversized declaration costs nothing to detect. Returns
    False for non-zip bytes (e.g. a mislabelled ``.docx``): callers fall through
    to their normal parse + fallback path. Never raises.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        total = sum(info.file_size for info in zf.infolist())
    except (zipfile.BadZipFile, OSError, ValueError):
        # Not a real zip / unreadable central directory — let the caller's
        # normal parse path handle it (bounded elsewhere by the upload cap).
        return False

    ratio = total / max(len(data), 1)
    if total > MAX_DOCX_UNCOMPRESSED or (
        len(data) > 0 and ratio > MAX_DOCX_RATIO and total > _RATIO_FLOOR
    ):
        logger.warning(
            "docx_safety: rejecting DOCX decompression bomb (inflated=%d ratio=%.0f)",
            total,
            ratio,
        )
        return True
    return False
