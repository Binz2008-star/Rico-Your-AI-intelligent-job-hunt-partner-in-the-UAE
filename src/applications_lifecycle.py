"""
src/applications_lifecycle.py
Application Lifecycle state machine — pure, dependency-free.

Defines the canonical stage ordering and allowed transitions for a tracked
application (rico_job_recommendations.status). Both the HTTP layer
(src/api/routers/applications.py) and the chat layer (src/rico_chat_api.py)
import from here so transition rules stay in one place.

Vocabulary note: we reuse the existing VALID_STATUSES values from
src/applications.py rather than inventing parallel names. The lifecycle subset
maps to UI labels as:
    applied         → "Applied"
    interview       → "Interviewing"
    offer           → "Offer"
    decision_made   → "Decision made" (accepted/declined captured in the note)
    rejected        → "Rejected"     (terminal)
    withdrawn       → "Withdrawn"     (terminal)
"""
from __future__ import annotations

from typing import Dict, List, Set

# New terminal value introduced by this feature. Kept in sync with
# src.applications.VALID_STATUSES and the frontend ApplicationStatus type.
WITHDRAWN = "withdrawn"

# Ordered pipeline stages (used to compute the "next" stage in the UI).
LIFECYCLE_STAGES: List[str] = ["applied", "interview", "offer", "decision_made"]

# Pre-application states that are all allowed to enter the funnel at "applied".
_PRE_APPLICATION: Set[str] = {
    "saved", "opened", "opened_external", "prepared", "follow_up_due", "found",
}

# Terminal stages have no outgoing transitions.
TERMINAL_STAGES: Set[str] = {"rejected", "decision_made", WITHDRAWN}

# from_stage -> set of allowed to_stages.
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    **{s: {"applied"} for s in _PRE_APPLICATION},
    "applied":   {"interview", "rejected", WITHDRAWN},
    "interview": {"offer", "rejected", WITHDRAWN},
    "offer":     {"decision_made", "rejected", WITHDRAWN},
    "rejected":      set(),
    "decision_made": set(),
    WITHDRAWN:       set(),
}


def is_terminal(stage: str) -> bool:
    """True when the stage has no outgoing transitions."""
    return (stage or "").strip().lower() in TERMINAL_STAGES


def can_advance(from_stage: str, to_stage: str) -> bool:
    """True when moving from `from_stage` to `to_stage` is a legal transition.

    A no-op move to the same stage is rejected (use a note edit instead).
    Unknown `from_stage` values default to pre-application semantics so a
    legacy row can still enter the funnel at "applied".
    """
    f = (from_stage or "").strip().lower()
    t = (to_stage or "").strip().lower()
    if not t or f == t:
        return False
    allowed = ALLOWED_TRANSITIONS.get(f)
    if allowed is None:
        # Unknown current stage → treat as pre-application (can only apply).
        allowed = {"applied"}
    return t in allowed


def next_stage(from_stage: str) -> str | None:
    """The natural forward stage for a one-click 'advance' button, or None.

    Returns the next item in LIFECYCLE_STAGES after the current one. Terminal
    and unknown stages return None (the UI should hide the advance button).
    """
    f = (from_stage or "").strip().lower()
    if f in _PRE_APPLICATION:
        return "applied"
    if f in LIFECYCLE_STAGES:
        idx = LIFECYCLE_STAGES.index(f)
        if idx + 1 < len(LIFECYCLE_STAGES):
            return LIFECYCLE_STAGES[idx + 1]
    return None
