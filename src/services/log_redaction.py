"""Shared log-redaction helpers (#1076).

Operational logs must never contain raw profile or contact values. The
sensitive-field denylist (values that must NEVER appear in a log record):

- direct identifiers: name, email, phone, telegram_username, telegram_chat_id
- career context: target_roles, preferred_cities, salary_expectation_aed,
  current_role, skills, visa_status, notice_period, languages, education,
  deal_breakers, green_flags, red_flags, saved-search queries
- content: cv_text / extracted document text, cv_file_url, chat messages,
  prompts, AI-provider payloads, tokens and secrets
- session bearers: public-session / guest IDs and any raw external user id
  (web user ids are emails; Telegram user ids are chat ids)

Allowed in logs: operation name, field-NAME lists, counts/lengths, durations,
success/failure, internal opaque DB row ids (UUIDs), and the output of
``user_fingerprint()``. See docs/SECURITY.md ("Logging rules").
"""
from __future__ import annotations

import hashlib
from typing import Any, Mapping


def user_fingerprint(user_id: Any) -> str:
    """Stable, non-reversible correlation key for a user id in logs.

    Never log the raw user id: for web users it is an email address, for
    Telegram users a chat id, and for guests a public-session bearer id.
    """
    if user_id is None:
        return "u:none"
    raw = str(user_id)
    if not raw:
        return "u:empty"
    return "u:" + hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:12]


def safe_field_names(mapping: Mapping[str, Any] | None) -> list[str]:
    """Sorted field NAMES of a mapping — never the values."""
    if not mapping:
        return []
    return sorted(str(k) for k in mapping.keys())


def safe_len(value: Any) -> int:
    """Length of a value for logs, 0 when it has no length."""
    if value is None:
        return 0
    try:
        return len(value)
    except TypeError:
        return 0


def safe_error(exc: BaseException) -> str:
    """Exception TYPE name only, for log records on sensitive paths.

    Driver/provider exception messages can re-emit bound values (SQL params,
    invalid-input echoes, addresses), so the message text must not reach logs.
    """
    return type(exc).__name__
