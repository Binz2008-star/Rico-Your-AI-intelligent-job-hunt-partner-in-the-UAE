"""User journey state machine for autonomous career-hunt tracking.

Tracks each user's position in the job-hunt lifecycle and generates
proactive daily action plans based on their current state.

States:
    discovery → searching → applying → interviewing → negotiating → offer

Transitions are driven by user actions (save, apply, interview prep, etc.)
and are persisted in the user's memory store. This module is read-only
with respect to the existing application/recommendation tables — it
derives state from existing data rather than maintaining a separate store.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_UTC = timezone.utc

STATES = (
    "discovery",
    "searching",
    "applying",
    "interviewing",
    "negotiating",
    "offer",
)

_STATE_ORDER = {s: i for i, s in enumerate(STATES)}

_VALID_TRANSITIONS: Dict[str, frozenset[str]] = {
    "discovery": frozenset({"discovery", "searching"}),
    "searching": frozenset({"searching", "applying", "discovery"}),
    "applying": frozenset({"applying", "interviewing", "searching"}),
    "interviewing": frozenset({"interviewing", "negotiating", "applying"}),
    "negotiating": frozenset({"negotiating", "offer", "interviewing"}),
    "offer": frozenset({"offer", "searching"}),
}


@dataclass
class JourneyState:
    user_id: str
    state: str = "discovery"
    entered_at: str = ""
    saved_count: int = 0
    applied_count: int = 0
    interviewing_count: int = 0
    last_action_date: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "state": self.state,
            "entered_at": self.entered_at,
            "saved_count": self.saved_count,
            "applied_count": self.applied_count,
            "interviewing_count": self.interviewing_count,
            "last_action_date": self.last_action_date,
        }


def derive_state(
    user_id: str,
    saved_count: int = 0,
    applied_count: int = 0,
    interviewing_count: int = 0,
) -> JourneyState:
    """Derive the user's journey state from their action counts.

    This is a pure function — no I/O. The caller supplies the counts
    from the recommendation/application tables.
    """
    if interviewing_count > 0:
        state = "interviewing"
    elif applied_count > 0:
        state = "applying"
    elif saved_count > 0:
        state = "searching"
    else:
        state = "discovery"

    return JourneyState(
        user_id=user_id,
        state=state,
        entered_at=datetime.now(_UTC).isoformat(),
        saved_count=saved_count,
        applied_count=applied_count,
        interviewing_count=interviewing_count,
        last_action_date=datetime.now(_UTC).isoformat(),
    )


def is_valid_transition(from_state: str, to_state: str) -> bool:
    """Check whether a state transition is allowed."""
    if from_state not in _VALID_TRANSITIONS:
        return False
    return to_state in _VALID_TRANSITIONS[from_state]


@dataclass
class DailyActionPlan:
    user_id: str
    state: str
    actions: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "state": self.state,
            "actions": self.actions,
        }


def generate_daily_plan(
    user_id: str,
    state: JourneyState,
    new_matches_count: int = 0,
    followups_due_count: int = 0,
    drafts_ready_count: int = 0,
) -> DailyActionPlan:
    """Generate a proactive daily action plan for the user.

    Returns a structured plan with recommended actions based on the
    user's current journey state and available data.
    """
    plan = DailyActionPlan(user_id=user_id, state=state.state)

    if state.state == "discovery":
        plan.actions.append({
            "action": "search",
            "message": "Let's find jobs matching your profile. Tell me your target role.",
            "priority": "high",
        })
    elif state.state == "searching":
        if new_matches_count > 0:
            plan.actions.append({
                "action": "review_matches",
                "message": f"Review {new_matches_count} new job matches Rico found for you.",
                "priority": "high",
            })
        if state.saved_count > 0 and state.applied_count == 0:
            plan.actions.append({
                "action": "apply",
                "message": f"You have {state.saved_count} saved jobs — time to start applying.",
                "priority": "high",
            })
    elif state.state == "applying":
        if new_matches_count > 0:
            plan.actions.append({
                "action": "review_matches",
                "message": f"Review {new_matches_count} new matches while you continue applying.",
                "priority": "medium",
            })
        if followups_due_count > 0:
            plan.actions.append({
                "action": "follow_up",
                "message": f"Follow up on {followups_due_count} applications (14+ days since applying).",
                "priority": "high",
            })
        if drafts_ready_count > 0:
            plan.actions.append({
                "action": "review_drafts",
                "message": f"Review {drafts_ready_count} cover letter drafts Rico prepared for you.",
                "priority": "medium",
            })
    elif state.state == "interviewing":
        plan.actions.append({
            "action": "interview_prep",
            "message": "Prepare for upcoming interviews — Rico can generate role-specific questions.",
            "priority": "high",
        })
        if followups_due_count > 0:
            plan.actions.append({
                "action": "follow_up",
                "message": f"Follow up on {followups_due_count} pending applications.",
                "priority": "medium",
            })

    if not plan.actions:
        plan.actions.append({
            "action": "check_in",
            "message": "No urgent actions today. Rico will keep scanning for new opportunities.",
            "priority": "low",
        })

    return plan
