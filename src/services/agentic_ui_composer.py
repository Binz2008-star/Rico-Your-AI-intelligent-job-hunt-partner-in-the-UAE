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

def _job_matches_actions(
    response_dict: dict[str, Any],
    *,
    offer_scheduled_search: bool = False,
) -> list[dict[str, Any]]:
    """Action cards attached to every job-match response."""
    search_role = (
        response_dict.get("search_query")
        or (response_dict.get("entities") or {}).get("job_title")
        or "these roles"
    )
    actions: list[dict[str, Any]] = [
        {
            "id": "view-jobs",
            "label": "View all jobs",
            "kind": "navigate",
            "href": "/flow",
        },
    ]
    # Only offer save-search when there were actual results
    if response_dict.get("matches"):
        actions.append({
            "id": "save-search",
            "label": "Save search",
            "kind": "chat_continue",
            "impact": "medium",
            "payload": {"message": f"save this search for {search_role}"},
        })
        # Contextual scheduled-search offer (#1249): shown only when the
        # CALLER established it's appropriate for this user's scenario — an
        # authenticated, non-public user who has search intent (results in
        # hand) and no daily schedule yet. Users with a schedule, guests, and
        # every other response type never see it. The payload is a natural
        # command the deterministic scheduled_search_create intent parses
        # (verb + daily cadence + jobs word), never UI wording.
        if offer_scheduled_search:
            actions.append({
                "id": "schedule-daily-search",
                "label": "Get these daily",
                "kind": "chat_continue",
                "impact": "low",
                "payload": {"message": f"search daily for {search_role} jobs"},
            })
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


def _profile_actions() -> list[dict[str, Any]]:
    """Quick-link to the profile page after profile-related responses."""
    return [
        {
            "id": "view-profile",
            "label": "View my profile",
            "kind": "navigate",
            "href": "/profile",
        },
    ]


def _applications_actions() -> list[dict[str, Any]]:
    """Quick-link to applications tracker."""
    return [
        {
            "id": "view-applications",
            "label": "Track applications",
            "kind": "navigate",
            "href": "/applications",
        },
    ]


def _new_search_actions() -> list[dict[str, Any]]:
    """Post-delete helper to start a fresh search."""
    return [
        {
            "id": "new-search",
            "label": "Find new jobs",
            "kind": "chat_continue",
            "payload": {"message": "find me jobs"},
        },
    ]


def _application_status_actions() -> list[dict[str, Any]]:
    """Action cards shown after Rico displays the application status summary."""
    return [
        {
            "id": "view-flow",
            "label": "View Application Flow",
            "kind": "navigate",
            "href": "/flow",
        },
        {
            "id": "add-application",
            "label": "Add application",
            "kind": "chat_continue",
            "payload": {"message": "Add a new job application manually"},
        },
    ]


def _prepare_application_actions() -> list[dict[str, Any]]:
    """Action cards shown after Rico prepares/tailors a job application."""
    return [
        {
            "id": "view-flow",
            "label": "View Application Flow",
            "kind": "navigate",
            "href": "/flow",
        },
        {
            "id": "find-similar",
            "label": "Find similar jobs",
            "kind": "chat_continue",
            "payload": {"message": "find me more jobs like this"},
        },
    ]


# ── Injection map ─────────────────────────────────────────────────────────────

_RESPONSE_TYPE_ACTIONS: dict[str, Any] = {
    # profile flows
    "profile_update":   _profile_actions,
    "profile_summary":  _profile_actions,
    "cv_first_profile": _profile_actions,
    # application flows — application_list is the conversational query response
    # ("what are my applications?"), application_status is the tracker card response
    "application_list":          _application_status_actions,
    "application_status":        _application_status_actions,
    "application_status_update": _applications_actions,
    # prepare/tailor application
    "prepare_application": _prepare_application_actions,
    # saved-jobs deletion confirmation
    "delete_saved_jobs_confirm": _delete_saved_jobs_confirm_actions,
    # post-deletion (empty list, offer a fresh start)
    "delete_saved_jobs_done": _new_search_actions,
    # save-job confirmation → quick link to saved list
    "save_job": lambda: [
        {
            "id": "view-saved-jobs",
            "label": "View saved jobs",
            "kind": "navigate",
            "href": "/flow",
        },
    ],
}


# ── Public compose ────────────────────────────────────────────────────────────

def compose(
    result: Any,
    response_dict: dict[str, Any] | None = None,
    *,
    offer_scheduled_search: bool = False,
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
        actions = _job_matches_actions(
            response_dict or {}, offer_scheduled_search=offer_scheduled_search
        )
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
