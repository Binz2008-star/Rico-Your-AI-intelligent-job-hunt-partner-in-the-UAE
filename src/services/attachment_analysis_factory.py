"""
src/services/attachment_analysis_factory.py
Factory for building RicoAttachmentAnalysis from a document ClassificationResult.

CAREER-OS-04 (universal intake): non-CV uploads should surface a first-class
`attachment_analysis` envelope on the chat response so the UI can render what the
file is and what Rico can safely do with it — without ever silently writing to the
user's profile/settings (file-derived data stays confirm-first).

This is the canonical constructor — the upload route and any handler that wants to
attach an analysis to `agentic_ui.attachment_analysis` should call this rather than
building the dict by hand, so the contract stays consistent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from src.schemas.chat import RicoAttachmentAnalysis, RicoAttachmentPurpose


# Map the document classifier's document_type values to the agentic
# RicoAttachmentPurpose enum. Anything unmapped is treated as unknown_document.
_PURPOSE_MAP: dict[str, RicoAttachmentPurpose] = {
    "cv": RicoAttachmentPurpose.cv_resume,
    "resume": RicoAttachmentPurpose.cv_resume,
    "job_description": RicoAttachmentPurpose.job_post,
    "job_post": RicoAttachmentPurpose.job_post,
    "recruiter_email": RicoAttachmentPurpose.recruiter_message,
    "application_form": RicoAttachmentPurpose.application_form,
    "certificate": RicoAttachmentPurpose.certificate,
    "offer_letter": RicoAttachmentPurpose.offer_letter,
    "contract": RicoAttachmentPurpose.contract_or_legalish,
    "invoice": RicoAttachmentPurpose.contract_or_legalish,
    "company_profile": RicoAttachmentPurpose.company_profile,
    "public_comment": RicoAttachmentPurpose.public_comment,
    "application_confirmation": RicoAttachmentPurpose.application_evidence,
    "image": RicoAttachmentPurpose.unknown_document,
}


def _gen_id() -> str:
    return f"att-{uuid.uuid4().hex[:8]}"


def purpose_for_document_type(document_type: str) -> RicoAttachmentPurpose:
    """Resolve a classifier document_type to a RicoAttachmentPurpose (never raises)."""
    return _PURPOSE_MAP.get((document_type or "").strip().lower(), RicoAttachmentPurpose.unknown_document)


def build_attachment_analysis(classification: Any, filename: str | None = None) -> RicoAttachmentAnalysis:
    """Build a RicoAttachmentAnalysis from a document ClassificationResult.

    Accepts the dataclass `ClassificationResult` (or any object exposing
    `document_type`, `confidence`, `display_label`, `file_format`). Conservative:
    only describes the file; it never carries instructions to mutate profile/settings.
    """
    document_type = getattr(classification, "document_type", "unknown")
    confidence = float(getattr(classification, "confidence", 0.0) or 0.0)
    display_label = getattr(classification, "display_label", None) or document_type.replace("_", " ").title()
    file_format = getattr(classification, "file_format", "unknown")

    purpose = purpose_for_document_type(document_type)
    pct = int(round(confidence * 100))
    summary = f"Detected as {display_label} ({pct}% confidence)."

    warnings: list[str] = []
    if document_type == "image":
        # Honest: this analysis is only built for the image type on the
        # OCR-failure path (successful OCR reclassifies to the text's real
        # type), so no readable text exists and no follow-up actions are
        # offered. Never promise "actions below" or a pending extraction.
        warnings.append(
            "No readable text could be extracted from this image. "
            "Paste the text directly into the chat if you want Rico to work with it."
        )
    elif purpose == RicoAttachmentPurpose.unknown_document:
        # Already states the uncertainty; a separate "low confidence" warning
        # underneath would repeat the same fact, so it deliberately does not
        # also fire below.
        warnings.append("Rico is not sure what this document is — confirm before acting on it.")
    elif confidence < 0.5:
        warnings.append("Low classification confidence.")

    return RicoAttachmentAnalysis(
        id=_gen_id(),
        filename=filename,
        mime_type=None,
        purpose=purpose,
        confidence=round(confidence, 3),
        extracted_summary=summary,
        extracted_fields={"document_type": document_type, "file_format": file_format},
        warnings=warnings,
    )


def build_attachment_analysis_dict(classification: Any, filename: str | None = None) -> dict[str, Any]:
    """Same as build_attachment_analysis() but returns a JSON-ready plain dict."""
    return build_attachment_analysis(classification, filename).model_dump(mode="json")


# ── Canonical latest-attachment session context (Task 3 slice 2) ─────────────
#
# The single source of truth for the `last_uploaded_document` record stored in
# recent-context session storage. Every upload write-site must build the record
# through `build_last_uploaded_context` so the shape is consistent and every
# consumer (the latest-attachment continuation reply, the provenance boundary,
# the "this is my ID" clarification) reads the same fields. Lives in session
# storage only — no schema migration; the durable DB store keeps its existing
# transcript-only columns.

# document_type → the coarse `detected_type` bucket the provenance layer reasons
# about. Anything unmapped is "unknown" (never guessed into a confident bucket).
_DETECTED_SENSITIVE_TYPES: frozenset[str] = frozenset({"identity_document", "passport"})
_DETECTED_JOB_TYPES: frozenset[str] = frozenset({
    "job_description", "job_post", "offer_letter", "contract",
    "recruiter_email", "company_profile",
})
# Below this classifier confidence a detected type stays UNCONFIRMED — it must
# not silently become canonical document identity (mirrors the reply threshold).
LATEST_ATTACHMENT_LOW_CONFIDENCE: float = 0.5


def normalize_detected_type(document_type: str | None) -> str:
    """Map a classifier ``document_type`` to the coarse provenance bucket:
    ``cv`` | ``identity_document`` | ``job_document`` | ``unknown``."""
    dt = (document_type or "").strip().lower()
    if dt in ("cv", "resume"):
        return "cv"
    if dt in _DETECTED_SENSITIVE_TYPES:
        return "identity_document"
    if dt in _DETECTED_JOB_TYPES:
        return "job_document"
    return "unknown"


def build_last_uploaded_context(
    *,
    filename: str | None,
    document_type: str | None,
    display_label: str | None = None,
    confidence: float = 0.0,
    extracted_text: str = "",
    extraction_available: bool | None = None,
    suggested_actions: Any = None,
    source: str = "image",
    source_turn_id: str | None = None,
    confirmed_by_user: bool = False,
) -> dict[str, Any]:
    """Build the canonical ``last_uploaded_document`` record for session storage.

    Carries the provenance/confidence fields the continuation + provenance layers
    consume, plus the legacy fields existing consumers still read (so it is a
    superset — nothing that read the old record breaks). A newer record fully
    replaces the older one at the write-site (atomic latest-attachment swap): the
    caller assigns the returned dict to ``recent_context["last_uploaded_document"]``
    wholesale, never merges into the previous one.

    Truthful by construction: a low-confidence classification stays
    ``confirmed_by_user=False`` / ``requires_confirmation=True`` so it never
    becomes canonical identity without the user's confirmation; an identity
    document is flagged ``is_sensitive`` regardless of confidence.
    """
    detected = normalize_detected_type(document_type)
    is_sensitive = detected == "identity_document"
    try:
        conf = float(confidence or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    text = (extracted_text or "")
    has_text = bool(text.strip()) if extraction_available is None else bool(extraction_available)
    low_conf = conf < LATEST_ATTACHMENT_LOW_CONFIDENCE
    # A low-confidence file, or any unconfirmed sensitive document, still needs
    # the user to confirm what it is before Rico treats the type as canonical.
    requires_confirmation = bool((low_conf or is_sensitive) and not confirmed_by_user)
    return {
        # ── canonical provenance fields ──
        "attachment_id": _gen_id(),
        "filename": filename,
        "detected_type": detected,
        "classification_confidence": round(conf, 3),
        "extraction_available": has_text,
        "confirmed_by_user": bool(confirmed_by_user),
        "requires_confirmation": requires_confirmation,
        "is_sensitive": is_sensitive,
        "source_turn_id": source_turn_id or _gen_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        # ── legacy fields kept for existing consumers (superset, not a break) ──
        "document_type": document_type,
        "display_label": display_label or (document_type or "document").replace("_", " ").title(),
        "confidence": round(conf, 3),
        "source": source,
        "suggested_actions": list(suggested_actions or []),
        "extracted_text": text[:4000],
    }
