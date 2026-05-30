"""
src/job_lifecycle.py
Canonical Application Lifecycle vocabulary for user_job_context.

This is the single source of truth for the per-user job funnel statuses and the
mapping from a user-facing action to (status, timestamp column). Both the HTTP
layer (src/api/routers/job_lifecycle.py) and the chat layer
(src/rico_chat_api.py) import from here so the rules stay in one place.

Distinct from src/applications_lifecycle.py (the legacy rico_job_recommendations
pipeline). This module governs the chat-side memory table user_job_context.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

# Ordered funnel. Index position implies forward progress for display only;
# transitions are not strictly enforced here (the chat surface is forgiving).
LIFECYCLE_STATUSES: List[str] = [
    "found",
    "saved",
    "opened_external",
    "prepared",
    "applied",
    "interviewing",
    "offer",
    "rejected",
    "archived",
    "needs_review",
]

_VALID: Set[str] = set(LIFECYCLE_STATUSES)

# Action verb -> (status, timestamp column to stamp with NOW()).
# `None` timestamp column means "set status only, no dedicated stamp".
_ACTION_LIFECYCLE: Dict[str, Tuple[str, Optional[str]]] = {
    "save":         ("saved",           "saved_at"),
    "open_apply":   ("opened_external", "opened_at"),   # clicking the apply link
    "opened":       ("opened_external", "opened_at"),
    "prepare":      ("prepared",        "prepared_at"),
    "prepare_application": ("prepared", "prepared_at"),
    "mark_applied": ("applied",         "applied_at"),
    "archive":      ("archived",        None),
    "needs_review": ("needs_review",    None),
}

# Columns this module is allowed to stamp — guards the SQL builder against
# arbitrary column names ever reaching a query.
_STAMP_COLUMNS: Set[str] = {"saved_at", "opened_at", "prepared_at", "applied_at"}


def is_valid_status(status: str) -> bool:
    return (status or "").strip().lower() in _VALID


def normalize_status(status: str) -> Optional[str]:
    s = (status or "").strip().lower()
    return s if s in _VALID else None


def lifecycle_for_action(action: str) -> Optional[Tuple[str, Optional[str]]]:
    """Return (status, timestamp_column) for an action verb, or None if the
    action does not map to a lifecycle transition."""
    return _ACTION_LIFECYCLE.get((action or "").strip().lower())


def stamp_column_for_status(status: str) -> Optional[str]:
    """The dedicated timestamp column for a status, if any."""
    mapping = {
        "saved":           "saved_at",
        "opened_external": "opened_at",
        "prepared":        "prepared_at",
        "applied":         "applied_at",
    }
    col = mapping.get((status or "").strip().lower())
    return col if col in _STAMP_COLUMNS else None
