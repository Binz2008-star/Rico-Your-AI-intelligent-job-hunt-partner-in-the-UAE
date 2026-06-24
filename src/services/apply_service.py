"""Apply-link service — safe error wrapping for Phase-0 trust gate.

This module wraps the low-level apply-link resolution and action handling
so that:

* Internal error codes (e.g. ``no_apply_link_available``) are NEVER
  returned to the chat layer or surfaced to the user.
* Every error path returns a :class:`ApplyLinkResult` with a user-safe
  ``message`` and a ``show_apply_button`` boolean.
* Server-side structured logging captures the internal code for ops.

All callers in ``rico_chat_api.py`` that previously returned raw error
codes must be updated to go through :func:`resolve_apply_action` instead.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from src.services.job_link_trust import (
    resolve_trusted_apply_url,
    safe_no_apply_link_message,
    should_show_apply_button,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ApplyLinkResult:
    """Outcome of an apply-link resolution or action attempt."""

    success: bool
    """True when a trusted apply URL was resolved and the action can proceed."""

    apply_url: Optional[str]
    """Verified, source-backed apply URL.  None when *success* is False."""

    show_apply_button: bool
    """Whether the UI should render a 'View & Apply' button."""

    message: str
    """User-safe chat message.  Never contains internal error codes."""

    internal_code: str = field(default="", compare=False)
    """Internal error code for server-side logging ONLY.  Never sent to user."""


# ---------------------------------------------------------------------------
# Internal safe messages
# ---------------------------------------------------------------------------

# Mapping of internal error codes → user-safe messages.
# Extend this dict when new internal codes are introduced; the fallback
# ``_GENERIC_SAFE_MESSAGE`` is always returned for unknown codes.
_SAFE_MESSAGES: dict[str, str] = {
    "no_apply_link_available": (
        "I don't have a verified apply link for this job yet. "
        "I can save it to your pipeline or help you search the company career page."
    ),
    "apply_url_untrusted": (
        "I couldn't verify the apply link for this job. "
        "I can save it to your pipeline or help you find the official application page."
    ),
    "apply_url_placeholder": (
        "The apply link for this job doesn't look right. "
        "I can save the job to your pipeline while you verify the link directly."
    ),
    "job_not_found": (
        "I couldn't find this job in my records. "
        "Try searching again or let me know the company name."
    ),
    "action_timeout": (
        "The action took too long to complete. Please try again in a moment."
    ),
}

_GENERIC_SAFE_MESSAGE = (
    "Something went wrong with that action. Please try again or let me know how I can help."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_apply_action(
    job: dict[str, Any],
    *,
    origin: Optional[str] = None,
) -> ApplyLinkResult:
    """Resolve the apply action for *job* through the full trust gate.

    Parameters
    ----------
    job:
        Job dict from the DB / ingestion layer.  Must NOT be raw LLM output
        unless ``origin='llm'`` is passed (which causes immediate rejection).
    origin:
        Pass ``'llm'`` when the dict was synthesised by the language model.

    Returns
    -------
    ApplyLinkResult
        Always returns a result; never raises.  Check ``.success`` to decide
        whether to show the apply button or the safe fallback message.
    """
    trusted_url = resolve_trusted_apply_url(job, origin=origin)

    if trusted_url:
        return ApplyLinkResult(
            success=True,
            apply_url=trusted_url,
            show_apply_button=True,
            message="",
        )

    # Determine which internal code applies for server-side logging.
    raw_url = (
        job.get("external_url")
        or job.get("alt_url")
        or job.get("source_url")
    )
    if not raw_url:
        internal_code = "no_apply_link_available"
    elif origin == "llm":
        internal_code = "apply_url_untrusted"
    else:
        from src.services.source_quality import is_placeholder_url  # avoid circular at module level
        internal_code = (
            "apply_url_placeholder" if is_placeholder_url(raw_url) else "apply_url_untrusted"
        )

    logger.warning(
        "apply_service: %s job_id=%s persisted_job_id=%s source_job_id=%s",
        internal_code,
        job.get("job_id"),
        job.get("persisted_job_id"),
        job.get("source_job_id"),
    )

    safe_msg = _SAFE_MESSAGES.get(internal_code) or safe_no_apply_link_message(job)

    return ApplyLinkResult(
        success=False,
        apply_url=None,
        show_apply_button=False,
        message=safe_msg,
        internal_code=internal_code,
    )


def wrap_action_error(
    internal_code: str,
    job: Optional[dict[str, Any]] = None,
) -> str:
    """Return a user-safe message for any internal action error code.

    Use this in ``rico_chat_api.py`` action handlers that currently return
    the raw ``internal_code`` string to the chat layer.

    Parameters
    ----------
    internal_code:
        The raw internal error string, e.g. ``'no_apply_link_available'``.
    job:
        Optional job dict for richer context in the fallback message.

    Returns
    -------
    str
        A user-safe message that never contains the internal code.
    """
    if internal_code in _SAFE_MESSAGES:
        return _SAFE_MESSAGES[internal_code]
    if job:
        return safe_no_apply_link_message(job)
    logger.error(
        "apply_service.wrap_action_error: unknown code '%s' – using generic message",
        internal_code,
    )
    return _GENERIC_SAFE_MESSAGE
