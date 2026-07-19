"""Document resolver — canonical CV resolution for Rico.

Provides a clean service layer over user_documents so callers never need
to know the resolution precedence or fallback strategy.

Resolution order for resolve_user_cv:
  1. Primary document where doc_type = 'cv'
  2. Latest document where doc_type = 'cv' (newest by created_at DESC)
  3. Legacy profile fallback: cv_filename + cv_status == 'parsed'
  4. None — no CV found

Callers that only need a boolean can use has_cv(user_id, profile).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CV_DOC_TYPES: frozenset[str] = frozenset({"cv"})


# ---------------------------------------------------------------------------
# Raw document access
# ---------------------------------------------------------------------------

def get_user_documents(user_id: str) -> List[Dict[str, Any]]:
    """Return all documents for the user, primary-first then newest."""
    try:
        from src.rico_db import RicoDB
        db = RicoDB()
        if not db.available:
            return []
        return db.list_user_documents(user_id)
    except Exception as exc:
        # Sanitized: exception type only — user_id is an email (PII) and must
        # never reach logs (owner audit 2026-07-19, point 4).
        logger.warning(
            "document_resolver.get_user_documents failed (%s)", type(exc).__name__
        )
        return []


def get_cv_candidates(user_id: str) -> List[Dict[str, Any]]:
    """Return only CV documents, primary-first then newest.

    Does not include cover_letter, identity_document, or other types.
    """
    return [d for d in get_user_documents(user_id) if d.get("doc_type") in _CV_DOC_TYPES]


def get_user_documents_strict(user_id: str) -> List[Dict[str, Any]]:
    """Like get_user_documents but RAISES on store failure.

    get_user_documents swallows store errors into [], which makes "store
    down" indistinguishable from "no documents". Career-context resolution
    must tell them apart: an unreachable store means CV-side values cannot
    be verified (degraded state → omit absolutes), while an empty store
    means the profile is legitimately the only source. An unconfigured
    store (db.available False) returns [] — that is a deployment mode, not
    a failure.
    """
    from src.rico_db import RicoDB
    db = RicoDB()
    if not db.available:
        return []
    return db.list_user_documents(user_id)


def get_cv_candidates_strict(user_id: str) -> List[Dict[str, Any]]:
    """CV documents, primary-first then newest; RAISES on store failure."""
    return [
        d for d in get_user_documents_strict(user_id)
        if d.get("doc_type") in _CV_DOC_TYPES
    ]


def get_primary_cv(user_id: str) -> Optional[Dict[str, Any]]:
    """Return the CV document marked is_primary, or None."""
    for d in get_cv_candidates(user_id):
        if d.get("is_primary"):
            return d
    return None


def get_latest_cv(user_id: str) -> Optional[Dict[str, Any]]:
    """Return the most recently uploaded CV regardless of primary flag, or None."""
    candidates = get_cv_candidates(user_id)
    return candidates[0] if candidates else None


# ---------------------------------------------------------------------------
# Canonical resolver
# ---------------------------------------------------------------------------

def resolve_user_cv(
    user_id: str,
    profile: Any = None,
) -> Optional[Dict[str, Any]]:
    """Return the best available CV for a user.

    Resolution order:
    1. Primary document where doc_type = 'cv'
    2. Latest document where doc_type = 'cv'
    3. Profile cv_filename + cv_status == 'parsed' (legacy / profile-only users)
    4. None — no CV found

    Profile can be a dict, a RicoProfile dataclass, or any object with attribute
    access. Pass None to skip the profile fallback (e.g., when profile is not yet
    loaded).
    """
    primary = get_primary_cv(user_id)
    if primary:
        return primary

    latest = get_latest_cv(user_id)
    if latest:
        return latest

    if profile is not None:
        cv_filename = _profile_get(profile, "cv_filename")
        cv_status = _profile_get(profile, "cv_status")
        if cv_filename and cv_status == "parsed":
            return {
                "filename": cv_filename,
                "doc_type": "cv",
                "is_primary": True,
                "is_legacy": True,
                "label": cv_filename,
            }

    return None


def has_cv(user_id: str, profile: Any = None) -> bool:
    """True when the user has at least one CV in user_documents or profile."""
    return resolve_user_cv(user_id, profile) is not None


def has_only_identity_documents(user_id: str) -> bool:
    """True when the user has files but none are CVs.

    Returns True when all uploaded documents are identity_document type
    (passport, Emirates ID, etc.) and there are no CV or resume documents.
    Returns False when there are no documents at all.
    """
    docs = get_user_documents(user_id)
    if not docs:
        return False
    has_cv_doc = any(d.get("doc_type") in _CV_DOC_TYPES for d in docs)
    has_identity_doc = any(d.get("doc_type") == "identity_document" for d in docs)
    return not has_cv_doc and has_identity_doc


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _profile_get(profile: Any, key: str) -> Any:
    if isinstance(profile, dict):
        return profile.get(key)
    return getattr(profile, key, None)
