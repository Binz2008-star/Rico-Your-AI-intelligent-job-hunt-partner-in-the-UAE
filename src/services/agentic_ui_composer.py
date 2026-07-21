"""
src/services/agentic_ui_composer.py

Maps RuntimeResult + response context → serialized agentic UI dict.

Single authoritative place for all Chat-as-Interface UI artifact mappings.
Called from _finalize() in rico_chat_api.py so no other code path needs to
know about the agentic_ui schema.

Two sources of agentic UI artifacts (merged, runtime wins on conflicts):
  1. RuntimeResult.data   — explicit agent-layer artifacts (permission
                            requests, proposed changes, progress steps,
                            attachment analysis, actions)
  2. response_dict.type   — response-type–based action cards that make the
                            chat the primary interface (PR-C)

Action payload contract (P1 fix, 2026-07-19): every ``chat_continue`` action
MUST carry ``payload["message"]`` — the exact chat text the click sends. The
frontend (ChatActionCard) refuses to send anything else; in particular a
button LABEL is presentation only and must never become chat input (the old
``prompt`` key silently fell back to the label, which the intent router then
parsed as a job role). UI-level flows (e.g. refine) use ``open_drawer``.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── Response-type action card factories ───────────────────────────────────────

def _job_matches_actions(response_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Action cards attached to every job-match response.

    Phase 2 of #1262: navigation buttons are retired — Rico now says where
    things live inside the message itself (a markdown link in
    _build_role_search_message), so the old "View all jobs" card is gone.
    """
    search_role = (
        response_dict.get("search_query")
        or (response_dict.get("entities") or {}).get("job_title")
        or "these roles"
    )
    actions: list[dict[str, Any]] = []
    # Phase 3 of #1262: the save-search card is retired — Rico offers it in
    # words ("just say: 'save this search'") and the phrase routes through the
    # deterministic save_search_create intent. (The card's payload phrase was
    # also being swallowed by the save_job regex — fixed with the same intent.)
    # Refine is a STRUCTURED UI action, never natural language: the frontend
    # opens a refinement panel and the LLM only ever sees the final composed
    # search query the user submits. A chat_continue here would put UI wording
    # into the intent router (P1: the label itself was being parsed as a role).
    actions.append({
        "id": "refine-search",
        "label": "Refine search",
        "kind": "open_drawer",
        "payload": {"drawer": "refine_search", "search_query": search_role},
    })
    return actions


def _delete_saved_jobs_confirm_actions() -> list[dict[str, Any]]:
    """Yes / No confirmation buttons for the delete-saved-jobs 2-turn flow."""
    return [
        {
            "id": "confirm-delete-jobs",
            "label": "Yes, delete all",
            "kind": "chat_continue",
            "impact": "high",
            "requires_confirmation": True,
            "payload": {"message": "yes delete all my saved jobs"},
        },
        {
            "id": "cancel-delete-jobs",
            "label": "No, keep them",
            "kind": "chat_continue",
            "payload": {"message": "no cancel"},
        },
    ]


# Phase 3 of #1262: the remaining chat_continue suggestion cards
# (add-application, find-similar, new-search) are retired — those asks are
# ordinary sentences the user can type ("find me more jobs like this",
# "find me jobs"), and Rico's messages point the way in words.


# ── Injection map ─────────────────────────────────────────────────────────────

# Phases 2–3 of #1262: navigation and suggestion card families are retired —
# Rico speaks pointers and offers inside the persisted message. The one
# remaining family is the destructive-delete confirmation, which stays until
# its strict conversational confirm ships (phase 4 — safety).
_RESPONSE_TYPE_ACTIONS: dict[str, Any] = {
    # saved-jobs deletion confirmation
    "delete_saved_jobs_confirm": _delete_saved_jobs_confirm_actions,
}


# ── Public compose ────────────────────────────────────────────────────────────

def compose(
    result: Any,
    response_dict: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return a serialized agentic UI dict or None.

    Merges two sources:
      - Explicit artifacts from ``result`` (RuntimeResult.data)
      - Auto-generated action cards derived from ``response_dict["type"]``

    Explicit runtime artifacts always win over auto-generated cards on the
    same key (e.g. if the agent attaches its own actions[], those are used
    instead of the type-based defaults).

    Returns a plain dict (``model_dump(exclude_none=True)``) so callers never
    need to know about the Pydantic model.
    """
    components: dict[str, Any] = {}

    # ── 1. Runtime result artifacts ───────────────────────────────────────────
    if result is not None:
        data = getattr(result, "data", {}) or {}
        for key in ("permission_request", "actions", "proposed_changes",
                    "attachment_analysis", "progress"):
            if val := data.get(key):
                components[key] = val

    # ── 2. Response-type–based action cards ───────────────────────────────────
    rtype = (response_dict or {}).get("type", "")

    if rtype == "job_matches" and "actions" not in components:
        actions = _job_matches_actions(response_dict or {})
        if actions:
            components["actions"] = actions
    elif rtype in _RESPONSE_TYPE_ACTIONS and "actions" not in components:
        factory = _RESPONSE_TYPE_ACTIONS[rtype]
        actions = factory()
        if actions:
            components["actions"] = actions

    if not components:
        return None

    try:
        from src.schemas.chat import RicoAgenticUi
        return RicoAgenticUi(**components).model_dump(exclude_none=True)
    except Exception:
        logger.debug("agentic_ui_composer: failed to build RicoAgenticUi", exc_info=True)
        return None
