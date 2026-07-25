"""The single read path for "what CV does this user have, and can I use it?".

Every chat surface that wants the user's CV goes through ``resolve_cv_context``.
Before this existed, roughly a dozen call sites each answered the question with
their own ``cv_status == "parsed"`` check, which meant they could disagree about
the same profile — and all of them inherited the same lie, because "parsed" was
being written next to an empty ``cv_structured``.

Read order, fixed here so no caller can reorder it:

    cv_structured  ->  cv_text  ->  metadata_only  ->  unavailable / error

``availability_reason`` is the part callers must not skip. A resolver that
returned only "no content" would let a database outage render as "you have no
CV" — the worst possible answer, because it sends a user to re-upload a file
that is already stored. ``unavailable`` and ``none`` are different facts and are
reported as different facts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from src.services.cv_state import (
    STATE_METADATA_ONLY,
    STATE_NONE,
    derive_cv_state,
    has_cv_content,
    has_cv_on_file,
)

logger = logging.getLogger(__name__)

#: Why content is or is not available. Distinct from the state so a caller can
#: tell "this user has no CV" from "we could not read the store just now".
REASON_STRUCTURED = "structured_available"
REASON_TEXT_ONLY = "text_only"
REASON_NO_CONTENT = "no_readable_content"
REASON_NONE_ON_FILE = "no_cv_on_file"
REASON_UNAVAILABLE = "store_unavailable"


@dataclass(frozen=True)
class CVContext:
    """What a chat surface needs to answer honestly about the user's CV."""

    state: str
    structured: Optional[Dict[str, Any]] = None
    readable_text_fallback: Optional[str] = None
    document_evidence: Dict[str, Any] = field(default_factory=dict)
    availability_reason: str = REASON_NONE_ON_FILE

    @property
    def has_cv(self) -> bool:
        """The user has a CV on file, whatever the state of its content."""
        return has_cv_on_file(self.state)

    @property
    def has_content(self) -> bool:
        """Real content is available to ground an answer on."""
        return has_cv_content(self.state)

    @property
    def is_unavailable(self) -> bool:
        """The store could not be read — NOT the same as having no CV."""
        return self.availability_reason == REASON_UNAVAILABLE

    @property
    def must_not_ask_user_to_retype(self) -> bool:
        """True whenever the product already holds usable content.

        A caller that asks the user to paste their work history while this is
        True is asking for something the product already has.
        """
        return self.has_content


def resolve_cv_context(user_id: str, profile: Any = None) -> CVContext:
    """Resolve the user's CV context. Never raises.

    A failure to read the store returns ``state="none"`` with
    ``availability_reason=REASON_UNAVAILABLE`` — never a confident "no CV".
    """
    try:
        return _resolve(user_id, profile)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("cv_context_resolver_failed user_hash=%s err=%s", hash(str(user_id)), type(exc).__name__)
        return CVContext(state=STATE_NONE, availability_reason=REASON_UNAVAILABLE)


def _resolve(user_id: str, profile: Any) -> CVContext:
    raw = _profile_mapping(profile)
    if raw is None:
        raw = _load_profile_row(user_id)
        if raw is None:
            # Distinguishable from "no CV": the caller must say "unavailable".
            return CVContext(state=STATE_NONE, availability_reason=REASON_UNAVAILABLE)

    structured = raw.get("cv_structured")
    if not isinstance(structured, dict):
        structured = None
    cv_text = raw.get("cv_text")
    cv_text = str(cv_text) if cv_text else None
    filename = raw.get("cv_filename") or None
    legacy_status = raw.get("cv_status") or None

    document_evidence = _document_evidence(user_id, filename)
    has_document = bool(document_evidence.get("document_id") or filename)

    state = derive_cv_state(
        cv_structured=structured,
        cv_text=cv_text,
        has_document=has_document,
        legacy_cv_status=legacy_status,
    )

    if state == STATE_NONE:
        return CVContext(
            state=state,
            document_evidence=document_evidence,
            availability_reason=REASON_NONE_ON_FILE,
        )

    if has_cv_content(state):
        reason = REASON_STRUCTURED if structured and state == "structured" else REASON_TEXT_ONLY
        return CVContext(
            state=state,
            # Structured is returned only when it is what earned the state, so a
            # caller can never read a thin document as if it were substantive.
            structured=structured if state == "structured" else None,
            readable_text_fallback=cv_text,
            document_evidence=document_evidence,
            availability_reason=reason,
        )

    # metadata_only / parse_failed / uploaded: the CV exists, the content does not.
    return CVContext(
        state=state,
        readable_text_fallback=None,
        document_evidence=document_evidence,
        availability_reason=REASON_NO_CONTENT,
    )


def _profile_mapping(profile: Any) -> Optional[Dict[str, Any]]:
    """Read the fields we need off an already-loaded profile, if one was passed.

    Accepts a mapping or an object with attributes so callers can pass whatever
    they already hold. Returns ``None`` when no profile was supplied, which is
    the signal to load one — never a fabricated empty profile.
    """
    if profile is None:
        return None
    if isinstance(profile, dict):
        source: Dict[str, Any] = profile
        inner = source.get("profile")
        merged = dict(inner) if isinstance(inner, dict) else {}
        merged.update({k: v for k, v in source.items() if k != "profile"})
        return merged
    keys = ("cv_structured", "cv_text", "cv_filename", "cv_status")
    if any(hasattr(profile, k) for k in keys):
        return {k: getattr(profile, k, None) for k in keys}
    return None


def _load_profile_row(user_id: str) -> Optional[Dict[str, Any]]:
    """Load the CV-relevant columns. ``None`` means the store could not be read."""
    try:
        from src.repositories.profile_repo import get_profile
        loaded = get_profile(user_id)
    except Exception as exc:
        logger.warning("cv_context_profile_load_failed err=%s", type(exc).__name__)
        return None
    if loaded is None:
        # A confirmed absence of a profile row is a real answer, not an outage.
        return {}
    return _profile_mapping(loaded) or {}


def _document_evidence(user_id: str, filename: Optional[str]) -> Dict[str, Any]:
    """The primary CV document row, for provenance and display.

    Best-effort: the CV state never depends on this succeeding. ``filename`` from
    the profile is the fallback so a legacy profile-only user still gets a name.
    """
    evidence: Dict[str, Any] = {"document_id": None, "filename": filename, "is_primary": None}
    try:
        from src.rico_db import RicoDB
        db = RicoDB()
        if not getattr(db, "available", False):
            return evidence
        for row in db.list_user_documents(user_id) or []:
            if row.get("doc_type") == "cv" and row.get("is_primary"):
                evidence.update({
                    "document_id": str(row.get("id")) if row.get("id") else None,
                    "filename": row.get("filename") or filename,
                    "is_primary": True,
                    # The document's own snapshot at analysis time — provenance
                    # only. Never a substitute for CV content, and never what
                    # decides the state.
                    "years_experience_snapshot": row.get("years_experience"),
                })
                break
    except Exception as exc:
        logger.debug("cv_context_document_evidence_failed err=%s", type(exc).__name__)
    return evidence


def authoritative_years_experience(profile: Any) -> Optional[float]:
    """The ONE authoritative years-of-experience value: the profile's own field.

    ``cv_structured.years_experience_hint`` is extraction evidence and
    ``user_documents.years_experience`` is a per-document snapshot; neither is the
    value the product reads. Keeping that ordering in one function is what stops
    a re-analysis from silently overwriting a number the user corrected — a
    caller wanting to reconcile a differing hint must surface the difference,
    not swap the value.
    """
    raw = _profile_mapping(profile) or {}
    value = raw.get("years_experience")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
