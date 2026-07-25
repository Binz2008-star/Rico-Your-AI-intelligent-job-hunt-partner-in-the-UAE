"""The one place that decides what state a user's CV is in.

``cv_status = "parsed"`` conflated two different facts: "a file arrived" and
"its content is usable". Production profiles carry it beside an empty
``cv_structured``, which is how a user could be told their CV was analysed while
nothing readable had been stored. This module replaces that single ambiguous
word with states derived from content that is actually present.

    structured      — cv_structured holds a valid, substantive document
    text_extracted  — cv_text is readable, but structure is missing or thin
    metadata_only   — a document/filename exists, with no readable text or
                      valid structure behind it
    parse_failed    — extraction was attempted and explicitly failed
    uploaded        — a file has arrived, before extraction/confirmation ran
    none            — nothing on file at all

Two rules that are not negotiable:

* ``parsed`` is accepted for READING only, as a legacy signal, and is never
  written by any path. It is treated as evidence that a CV exists — never as
  evidence that its content is available, which is precisely what it wrongly
  asserted.
* ``metadata_only`` still means the user HAS a CV. The product must say the
  content is not available right now; it must never say "you have no CV" and
  must never claim the CV was analysed.

There is deliberately no migration and no backfill: every state is derived from
the content in the row at read time, so a legacy row needs no rewriting to be
read correctly.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

STATE_STRUCTURED = "structured"
STATE_TEXT_EXTRACTED = "text_extracted"
STATE_METADATA_ONLY = "metadata_only"
STATE_PARSE_FAILED = "parse_failed"
STATE_UPLOADED = "uploaded"
STATE_NONE = "none"

#: The legacy value. Read-only — never written.
LEGACY_STATUS_PARSED = "parsed"

#: Legacy statuses that mean "extraction was attempted and failed".
_LEGACY_FAILED = frozenset({"parse_failed", "failed", "extraction_failed"})

#: Legacy statuses that mean "a file arrived, extraction not finished".
_LEGACY_UPLOADED = frozenset({"uploaded", "received_pending_extraction", "pending"})

#: States in which the user demonstrably has a CV on file, whatever its content.
_STATES_WITH_CV = frozenset({
    STATE_STRUCTURED, STATE_TEXT_EXTRACTED, STATE_METADATA_ONLY,
    STATE_PARSE_FAILED, STATE_UPLOADED,
})

#: States in which real CV content is available to ground an answer on.
_STATES_WITH_CONTENT = frozenset({STATE_STRUCTURED, STATE_TEXT_EXTRACTED})

#: States in which extraction has SETTLED — the document is a finished artifact,
#: whether or not usable content came out of it. Excludes ``uploaded`` (still in
#: flight) and ``parse_failed`` (finished, but produced nothing to stand behind).
_STATES_SETTLED = frozenset({STATE_STRUCTURED, STATE_TEXT_EXTRACTED, STATE_METADATA_ONLY})


def derive_cv_state(
    *,
    cv_structured: Optional[Dict[str, Any]] = None,
    cv_text: Optional[str] = None,
    has_document: bool = False,
    legacy_cv_status: Optional[str] = None,
) -> str:
    """Derive the CV state from stored content. Content wins over any stored label.

    ``legacy_cv_status`` is consulted only where content cannot decide: it can
    distinguish "a file is on its way" and "extraction failed" from a bare
    ``metadata_only``, and a legacy ``parsed`` contributes only the fact that a
    CV exists. It can never promote a row to ``structured`` or
    ``text_extracted`` — those require the content itself.
    """
    from src.services.cv_structured import is_substantive

    if is_substantive(cv_structured):
        return STATE_STRUCTURED

    if _is_readable(cv_text):
        return STATE_TEXT_EXTRACTED

    status = (legacy_cv_status or "").strip().lower()

    if status in _LEGACY_FAILED:
        return STATE_PARSE_FAILED

    # An explicit "extraction has not finished" status wins over the generic
    # metadata_only below, and must be checked BEFORE it: a file that is still
    # in flight has a filename too, so testing `has_document` first would report
    # a pending upload as a settled document with no content — which is how an
    # in-flight upload gets presented to the user as their CV.
    if status in _LEGACY_UPLOADED:
        return STATE_UPLOADED

    # A legacy `parsed` with no readable content is exactly the production state
    # this module exists to describe honestly: the file is real, the content is
    # not available. It reports metadata_only, never text_extracted.
    if has_document or status == LEGACY_STATUS_PARSED:
        return STATE_METADATA_ONLY

    return STATE_NONE


def _is_readable(cv_text: Optional[str]) -> bool:
    """Whether stored text passes the shared parse-quality contract.

    Uses ``src.cv_parse_quality`` rather than a local length check so this
    module and the upload/confirm gates can never disagree about the same text.
    """
    if not cv_text or not str(cv_text).strip():
        return False
    try:
        from src.cv_parse_quality import validate_artifact_quality
        return bool(validate_artifact_quality(str(cv_text)).is_readable)
    except Exception:
        # Never let a quality-check failure claim readable content.
        return False


def has_cv_on_file(state: str) -> bool:
    """True when the user has a CV, regardless of whether its content is usable.

    The predicate that replaces ``cv_status == "parsed"`` at call sites asking
    "does this user have a CV?". ``metadata_only`` and ``parse_failed`` answer
    YES: the file exists, and telling the user otherwise is the failure mode
    that sends them to re-upload a CV they already provided.
    """
    return state in _STATES_WITH_CV


def has_cv_content(state: str) -> bool:
    """True only when real content is available to ground an answer on.

    The predicate for call sites asking "can I actually read this CV?".
    """
    return state in _STATES_WITH_CONTENT


def has_settled_cv(state: str) -> bool:
    """True when extraction has finished and left a document worth resolving.

    For call sites that must present a specific CV — not merely know one exists.
    Excludes ``uploaded``, so a file still being processed is never shown as the
    user's CV, and ``parse_failed``, which finished with nothing to stand behind.
    """
    return state in _STATES_SETTLED
