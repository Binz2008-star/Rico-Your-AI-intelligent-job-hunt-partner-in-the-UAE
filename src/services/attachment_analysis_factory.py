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
        warnings.append("Image uploaded — text extraction pending. Use the actions below to read or describe it.")
    elif purpose == RicoAttachmentPurpose.unknown_document:
        warnings.append("Rico is not sure what this document is — confirm before acting on it.")
    if confidence < 0.5:
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
