"""User journey snapshot derivation and daily planning.

Derives each user's current position in the job hunt purely from aggregate
application counts and generates proactive daily action plans.

Canonical status mapping (from ``src/applications.py::VALID_STATUSES``):

| canonical status | stage | count argument | contribution |
|------------------|-------|----------------|--------------|
| ``saved`` | Leads / pre-application | ``saved_count`` | searching |
| ``prepared`` | Leads / pre-application | ``prepared_count`` | searching |
| ``opened`` | passive click tracking | excluded | none |
| ``opened_external`` | passive click tracking | excluded | none |
| ``applied`` | Applied | ``applied_count`` | applying |
| ``follow_up_due`` | Applied | ``follow_up_due_count`` | applying |
| ``interview`` | Interview | ``interviewing_count`` | interviewing |
| ``offer`` | Outcome / Offer | ``offer_count`` | offer |

Statuses ``rejected`` and ``decision_made`` are terminal outcomes and do not
advance the aggregate snapshot. ``opened`` / ``opened_external`` are passive
tracking events and are intentionally excluded.

Precedence (furthest-along signal wins): ``offer > interviewing > applying >
searching > discovery``.

This module does not define or enforce lifecycle transitions. It derives a
read-only aggregate snapshot from the current application statuses.

Pure, deterministic, read-only: no I/O, no DB, no clock, no side effects.
Identical inputs always return an equal result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

STATES = (
    "discovery",
    "searching",
    "applying",
    "interviewing",
    "offer",
)


# ── Validation helpers ───────────────────────────────────────────────────────

def _require_user_id(user_id: str) -> None:
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id must be a non-empty string")


def _require_non_negative(**counts: int) -> None:
    for name, value in counts.items():
        # bool is a subclass of int — reject it explicitly to avoid True==1 slips.
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{name} must be an int, got {type(value).__name__}")
        if value < 0:
            raise ValueError(f"{name} must be non-negative, got {value}")


def _derive_label(
    saved_count: int,
    prepared_count: int,
    applied_count: int,
    follow_up_due_count: int,
    interviewing_count: int,
    offer_count: int,
) -> str:
    """Map canonical aggregate counts to a journey snapshot label.

    Precedence (furthest-along signal wins): offer > interviewing > applying >
    searching > discovery.
    """
    if offer_count > 0:
        return "offer"
    if interviewing_count > 0:
        return "interviewing"
    if applied_count > 0 or follow_up_due_count > 0:
        return "applying"
    if saved_count > 0 or prepared_count > 0:
        return "searching"
    return "discovery"


# ── Journey snapshot ─────────────────────────────────────────────────────────

@dataclass
class JourneyState:
    user_id: str
    state: str = "discovery"
    saved_count: int = 0
    prepared_count: int = 0
    applied_count: int = 0
    follow_up_due_count: int = 0
    interviewing_count: int = 0
    offer_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "state": self.state,
            "saved_count": self.saved_count,
            "prepared_count": self.prepared_count,
            "applied_count": self.applied_count,
            "follow_up_due_count": self.follow_up_due_count,
            "interviewing_count": self.interviewing_count,
            "offer_count": self.offer_count,
        }


def derive_state(
    user_id: str,
    saved_count: int = 0,
    prepared_count: int = 0,
    applied_count: int = 0,
    follow_up_due_count: int = 0,
    interviewing_count: int = 0,
    offer_count: int = 0,
) -> JourneyState:
    """Derive the user's journey snapshot from canonical aggregate counts.

    Pure and deterministic — no I/O and no clock, so identical inputs always
    return an equal ``JourneyState``. The caller supplies the counts from the
    application/recommendation tables.

    Raises ``ValueError`` on an empty ``user_id`` or any negative count.
    """
    _require_user_id(user_id)
    _require_non_negative(
        saved_count=saved_count,
        prepared_count=prepared_count,
        applied_count=applied_count,
        follow_up_due_count=follow_up_due_count,
        interviewing_count=interviewing_count,
        offer_count=offer_count,
    )
    state = _derive_label(
        saved_count,
        prepared_count,
        applied_count,
        follow_up_due_count,
        interviewing_count,
        offer_count,
    )
    return JourneyState(
        user_id=user_id,
        state=state,
        saved_count=saved_count,
        prepared_count=prepared_count,
        applied_count=applied_count,
        follow_up_due_count=follow_up_due_count,
        interviewing_count=interviewing_count,
        offer_count=offer_count,
    )


# ── Daily action plan ────────────────────────────────────────────────────────

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
    state: JourneyState,
    new_matches_count: int = 0,
    drafts_ready_count: int = 0,
) -> DailyActionPlan:
    """Generate a proactive daily action plan for the user who owns ``state``.

    Identity comes solely from ``state.user_id`` — there is no separate
    ``user_id`` argument, so a plan can never be constructed for one user from
    another user's state.

    Follow-up ownership is part of the snapshot via ``state.follow_up_due_count``;
    this removes the duplicate ``followups_due_count`` argument and prevents
    state/count inconsistency.

    Fail-fast (``ValueError``) on: empty ``state.user_id``; an unknown journey
    state; a negative count; or a ``state`` whose label is inconsistent with its
    own counts (rather than silently falling back).
    """
    _require_user_id(state.user_id)
    if state.state not in STATES:
        raise ValueError(f"unknown journey state: {state.state!r} (valid: {list(STATES)})")
    _require_non_negative(
        saved_count=state.saved_count,
        prepared_count=state.prepared_count,
        applied_count=state.applied_count,
        follow_up_due_count=state.follow_up_due_count,
        interviewing_count=state.interviewing_count,
        offer_count=state.offer_count,
        new_matches_count=new_matches_count,
        drafts_ready_count=drafts_ready_count,
    )
    expected = _derive_label(
        state.saved_count,
        state.prepared_count,
        state.applied_count,
        state.follow_up_due_count,
        state.interviewing_count,
        state.offer_count,
    )
    if expected != state.state:
        raise ValueError(
            f"inconsistent journey state {state.state!r} for counts "
            f"(saved={state.saved_count}, prepared={state.prepared_count}, "
            f"applied={state.applied_count}, follow_up_due={state.follow_up_due_count}, "
            f"interviewing={state.interviewing_count}, offer={state.offer_count}); "
            f"expected {expected!r}"
        )

    plan = DailyActionPlan(user_id=state.user_id, state=state.state)

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
        if state.saved_count > 0 and state.applied_count == 0 and state.follow_up_due_count == 0:
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
        if state.follow_up_due_count > 0:
            plan.actions.append({
                "action": "follow_up",
                "message": f"Follow up on {state.follow_up_due_count} applications (14+ days since applying).",
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
        if state.follow_up_due_count > 0:
            plan.actions.append({
                "action": "follow_up",
                "message": f"Follow up on {state.follow_up_due_count} pending applications.",
                "priority": "medium",
            })
    elif state.state == "offer":
        plan.actions.append({
            "action": "review_offer",
            "message": "You have an offer to review — Rico can help you weigh it against your goals.",
            "priority": "high",
        })

    if not plan.actions:
        plan.actions.append({
            "action": "check_in",
            "message": "No urgent actions today. Rico will keep scanning for new opportunities.",
            "priority": "low",
        })

    return plan
