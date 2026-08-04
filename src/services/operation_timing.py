"""
src/services/operation_timing.py
Privacy-safe timing observability for chat operations.

Emits structured log events keyed by a sanitized operation reference so a
single request's lifecycle can be traced without exposing user data.

Privacy contract:
- Logs: sanitized operation_id, server request_ref, stage name, duration_ms,
  provider category, outcome category.
- NEVER logs: raw client operation_id, raw query, email, CV/profile text,
  provider payload, result URLs, tokens, or any user-identifiable content.

Stage contract (enforced at runtime):
- request_received
- identity_profile_ready
- intent_resolved
- service_started
- service_finished
- response_returned  (terminal — exactly one per request)

Provider and outcome categories are validated at runtime. Unknown values
are classified as "unknown" rather than rejected, so a misconfigured caller
never breaks the request — but the invalid value is visible in logs.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Stage contract (enforced at runtime) ──────────────────────────────────────
# Lifecycle stages (sequential for a normal request):
#   request_received → identity_profile_ready → intent_resolved
#   → service_started → service_finished → response_returned (terminal)
#
# Conditional stage:
#   preflight_terminal — emitted INSTEAD of service_started/service_finished
#   when the preflight gate returns a terminal response (policy block,
#   entitlement gate, etc.). This is truthful: the service lifecycle never
#   started, so we do not emit service_started/service_finished for this path.
KNOWN_STAGES = frozenset({
    "request_received",
    "identity_profile_ready",
    "intent_resolved",
    "service_started",
    "service_finished",
    "preflight_terminal",
    "response_returned",
})

TERMINAL_STAGES = frozenset({"response_returned"})

# ── Provider category contract ────────────────────────────────────────────────
# NOTE: "ai" and "legacy" are NOT providers — they are service routes.
# Route classification lives on intent_resolved (outcome), not on
# service_started/service_finished (provider).
KNOWN_PROVIDERS = frozenset({
    "jsearch", "jooble", "adzuna", "cache", "internal", "none",
})

# ── Outcome category contract ─────────────────────────────────────────────────
KNOWN_OUTCOMES = frozenset({
    "ok", "timeout", "rate_limited", "quota", "empty", "error",
    "profile", "no_profile", "ai", "legacy", "preflight_terminal",
    "http_exception", "cancelled", "unknown",
})

# ── operation_id sanitization ─────────────────────────────────────────────────
# Strict allowlist: alphanumeric, dash, underscore, dot. Bounded length.
_OP_ID_ALLOWLIST = re.compile(r"^[A-Za-z0-9._-]+$")
_OP_ID_MAX_LEN = 128
_OP_ID_FALLBACK = "unknown"


def sanitize_operation_id(raw: Optional[str]) -> str:
    """Sanitize a client-provided operation_id for logging.

    Strict enforcement: the ENTIRE input must match [A-Za-z0-9._-]+.
    Any value that contains a disallowed character (including control chars,
    newlines, spaces, @, #, etc.) falls back to 'unknown'.

    We do NOT strip invalid characters and retain the rest, because that can
    create identifier collisions (e.g. "op-1@#$" and "op-1!#$" would both
    become "op-1").

    - Bounds length to 128 characters (truncation only for valid prefixes).
    - Falls back to 'unknown' if empty, None, or contains any disallowed char.
    """
    if raw is None:
        return _OP_ID_FALLBACK
    raw_str = str(raw)
    # Reject if ANY control characters or newlines are present.
    if re.search(r"[\x00-\x1f\x7f\r\n\t]", raw_str):
        return _OP_ID_FALLBACK
    cleaned = raw_str.strip()
    if not cleaned:
        return _OP_ID_FALLBACK
    # Strict: the ENTIRE string must match the allowlist. No strip-and-keep.
    if not _OP_ID_ALLOWLIST.match(cleaned):
        return _OP_ID_FALLBACK
    # Bound length (truncation preserves a valid prefix).
    if len(cleaned) > _OP_ID_MAX_LEN:
        cleaned = cleaned[:_OP_ID_MAX_LEN]
    return cleaned


def _safe_provider(provider: Optional[str]) -> Optional[str]:
    """Classify a provider value; unknown values become 'unknown'."""
    if provider is None:
        return None
    p = str(provider).strip().lower()
    if p in KNOWN_PROVIDERS:
        return p
    return "unknown"


def _safe_outcome(outcome: Optional[str]) -> Optional[str]:
    """Classify an outcome value; unknown values become 'unknown'."""
    if outcome is None:
        return None
    o = str(outcome).strip().lower()
    if o in KNOWN_OUTCOMES:
        return o
    return "unknown"


class OperationTimer:
    """Privacy-safe per-operation timing recorder.

    Guarantees exactly one terminal event (response_returned) per request
    via a terminal guard flag. Created at the start of a chat request and
    carried through the pipeline. Each ``record()`` call emits one structured
    log line.

    The timer is intentionally lightweight: no threads, no locks, no I/O
    beyond the single log line per stage. Durations are wall-clock
    milliseconds measured with ``time.monotonic`` for monotonic safety.
    """

    __slots__ = ("_op_id", "_request_ref", "_t0", "_last", "_terminal", "_log")

    def __init__(
        self,
        operation_id: Optional[str],
        request_ref: Optional[str] = None,
        log: Optional[logging.Logger] = None,
    ) -> None:
        self._op_id = sanitize_operation_id(operation_id)
        self._request_ref = sanitize_operation_id(request_ref) if request_ref else None
        self._t0 = time.monotonic()
        self._last = self._t0
        self._terminal = False
        self._log = log or logger

    def record(
        self,
        stage: str,
        *,
        provider: Optional[str] = None,
        outcome: Optional[str] = None,
        http_status: Optional[int] = None,
    ) -> None:
        """Emit a single timing event for ``stage``.

        Enforces:
        - Unknown stages are logged as stage='unknown' (not rejected).
        - Terminal stages are emitted exactly once; subsequent calls are
          silently dropped (no double-emitting terminal events).
        - provider and outcome are classified to known categories.
        """
        # Terminal guard: emit exactly one terminal event.
        if self._terminal:
            return
        if stage in TERMINAL_STAGES:
            self._terminal = True

        # Stage validation: unknown stages are classified, not rejected.
        safe_stage = stage if stage in KNOWN_STAGES else "unknown"

        now = time.monotonic()
        since_last_ms = int((now - self._last) * 1000)
        since_start_ms = int((now - self._t0) * 1000)
        self._last = now

        # Build the structured log line — privacy-safe fields only.
        parts = [
            f"operation_id={self._op_id}",
            f"stage={safe_stage}",
            f"duration_ms={since_last_ms}",
            f"total_ms={since_start_ms}",
        ]
        if self._request_ref:
            parts.append(f"request_ref={self._request_ref}")
        if provider is not None:
            parts.append(f"provider={_safe_provider(provider)}")
        if outcome is not None:
            parts.append(f"outcome={_safe_outcome(outcome)}")
        if http_status is not None:
            parts.append(f"http_status={http_status}")

        self._log.info("operation_timing %s", " ".join(parts))

    @property
    def operation_id(self) -> str:
        return self._op_id

    @property
    def has_terminal(self) -> bool:
        """True if a terminal event has already been emitted."""
        return self._terminal

    def total_ms(self) -> int:
        """Total wall-clock milliseconds since construction."""
        return int((time.monotonic() - self._t0) * 1000)
