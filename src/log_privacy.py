"""#1076 — shared log-privacy helpers: fingerprints, safe metadata, redaction.

Operational logs have a broader audience and retention model than the user
database, so they must never carry profile values, contact identifiers,
message text, document text, or any bearer credential. This module is the ONE
sanctioned way to reference users, tokens, dictionaries, and exceptions from
log statements on those paths — ad-hoc slicing (``value[:80]``) is not
redaction and is rejected by the static guard in
``tests/test_1076_log_privacy.py``.

Rules enforced here:

* **Correlation** — never log an email, phone, Telegram id, or public-session
  bearer id as the correlation key. ``user_ref()`` gives a stable,
  non-reversible, server-keyed fingerprint instead. Internal opaque numeric /
  UUID ids (``rico_users.id``) remain fine to log directly.
* **Payloads** — log field NAMES and counts (``safe_fields``), never values.
* **Exceptions** — driver/provider exception strings can re-emit bound values
  (e.g. a psycopg2 IntegrityError DETAIL contains the conflicting row).
  ``safe_exc()`` yields ``ClassName[pgcode]`` only.
* **Tokens** — reset / verification / checkout / unsubscribe / OAuth-state
  tokens never appear in logs at any level; ``token_ref()`` exists for the
  rare case correlation is operationally necessary.
* **Production fail-closed** — ``enforce_production_log_safety()`` refuses to
  start production with any token-logging/debug-PII flag enabled.
* **Sentry** — ``sentry_before_send`` scrubs events (headers, cookies, query
  strings, extras, breadcrumbs, exception strings) so the exporter cannot
  widen the blast radius of a value that slipped into an exception message.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from typing import Any, Mapping

# Flags that must never be enabled in production: each one authorizes writing
# a raw credential or raw PII into operational logs.
FORBIDDEN_PRODUCTION_LOG_FLAGS = (
    "RESET_TOKEN_LOG",
    "LOG_RAW_PII",
    "DEBUG_LOG_PII",
)

# Key-name denylist for structured scrubbing (Sentry events, mappings).
SENSITIVE_KEYS = re.compile(
    r"(authorization|cookie|set-cookie|token|secret|password|passwd|api[_-]?key|"
    r"signature|bearer|email|phone|telegram|salary|cv_text|resume|session_id|"
    r"x-cron-secret)",
    re.IGNORECASE,
)

# Value patterns scrubbed out of free text (exception messages, breadcrumbs).
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{8,}")
_TOKEN_PARAM_RE = re.compile(r"(?i)(token|signature|key|secret|state)=[^\s&\"']{6,}")
_LONG_SECRET_RE = re.compile(r"\b[A-Za-z0-9_-]{24,}\b")

_REDACTED = "[redacted]"


def _fingerprint_key() -> bytes:
    # Server-keyed so fingerprints are not offline-reversible dictionaries.
    # LOG_FINGERPRINT_KEY is optional; JWT_SECRET keeps the key server-side
    # without introducing a new mandatory env var; the static fallback still
    # prevents accidental raw values even in bare test environments.
    key = os.getenv("LOG_FINGERPRINT_KEY") or os.getenv("JWT_SECRET") or "rico-log-fp"
    return key.encode()


def _hmac_ref(value: str, prefix: str) -> str:
    digest = hmac.new(_fingerprint_key(), value.encode(), hashlib.sha256).hexdigest()
    return f"{prefix}:{digest[:12]}"


def user_ref(user_id: Any) -> str:
    """Non-reversible correlation ref for ANY external user identifier
    (email, public:<sid>, phone-derived id …)."""
    if user_id is None:
        return "u:none"
    return _hmac_ref(str(user_id), "u")


def token_ref(token: Any) -> str:
    """Fingerprint for a bearer-ish token when correlation is truly needed."""
    if not token:
        return "t:none"
    return _hmac_ref(str(token), "t")


def safe_fields(mapping: Mapping[str, Any] | None) -> str:
    """Field NAMES + count — never values."""
    if not mapping:
        return "fields=0[]"
    names = sorted(str(k) for k in mapping)
    return f"fields={len(names)}{names}"


def safe_exc(exc: BaseException) -> str:
    """Log-safe exception label: class name + driver code, never str(exc)
    (which can carry bound values, e.g. psycopg2 IntegrityError DETAIL)."""
    pgcode = getattr(exc, "pgcode", None)
    return f"{type(exc).__name__}[{pgcode}]" if pgcode else type(exc).__name__


def scrub_text(text: str) -> str:
    """Redact obvious credential / contact material inside free text."""
    text = _BEARER_RE.sub(_REDACTED, text)
    text = _TOKEN_PARAM_RE.sub(lambda m: f"{m.group(1)}={_REDACTED}", text)
    text = _EMAIL_RE.sub(_REDACTED, text)
    text = _LONG_SECRET_RE.sub(_REDACTED, text)
    return text


def _scrub_value(key: Any, value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _scrub_value(k, v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub_value(key, v) for v in value]
    if SENSITIVE_KEYS.search(str(key)):
        return _REDACTED
    if isinstance(value, str):
        return scrub_text(value)
    return value


def scrub_mapping(mapping: Mapping[str, Any] | None) -> dict:
    return {k: _scrub_value(k, v) for k, v in (mapping or {}).items()}


def sentry_before_send(event: dict, hint: Any = None) -> dict:
    """Sentry ``before_send`` hook: scrub request data, extras, breadcrumbs,
    and exception strings so exported events cannot carry credentials, contact
    values, or document text."""
    try:
        request = event.get("request")
        if isinstance(request, dict):
            for section in ("headers", "cookies", "data", "env"):
                if isinstance(request.get(section), Mapping):
                    request[section] = scrub_mapping(request[section])
                elif isinstance(request.get(section), str):
                    request[section] = scrub_text(request[section])
            if isinstance(request.get("query_string"), str):
                request["query_string"] = scrub_text(request["query_string"])

        for section in ("extra", "contexts", "tags", "user"):
            if isinstance(event.get(section), Mapping):
                event[section] = scrub_mapping(event[section])

        crumbs = event.get("breadcrumbs")
        crumb_list = crumbs.get("values") if isinstance(crumbs, dict) else crumbs
        for crumb in crumb_list or []:
            if isinstance(crumb, dict):
                if isinstance(crumb.get("message"), str):
                    crumb["message"] = scrub_text(crumb["message"])
                if isinstance(crumb.get("data"), Mapping):
                    crumb["data"] = scrub_mapping(crumb["data"])

        for exc in (event.get("exception") or {}).get("values") or []:
            if isinstance(exc, dict) and isinstance(exc.get("value"), str):
                exc["value"] = scrub_text(exc["value"])

        if isinstance(event.get("message"), str):
            event["message"] = scrub_text(event["message"])
        logentry = event.get("logentry")
        if isinstance(logentry, dict):
            if isinstance(logentry.get("message"), str):
                logentry["message"] = scrub_text(logentry["message"])
            if isinstance(logentry.get("params"), (list, tuple)):
                logentry["params"] = [
                    scrub_text(p) if isinstance(p, str) else p
                    for p in logentry["params"]
                ]
    except Exception:
        # Scrubbing must never break event delivery; on any surprise, drop
        # the risky sections outright rather than sending them raw.
        for section in ("request", "extra", "breadcrumbs", "contexts", "user"):
            event.pop(section, None)
    return event


def enforce_production_log_safety() -> None:
    """Refuse to start production with a token-logging/debug-PII flag on.

    A "debug override" that writes account-takeover tokens into live logs is
    not an acceptable production path (#1076 / #1095).
    """
    env = (
        os.getenv("RICO_ENV")
        or os.getenv("APP_ENV")
        or os.getenv("ENV")
        or os.getenv("ENVIRONMENT")
        or ""
    ).lower()
    if env not in ("production", "prod"):
        return
    enabled = [
        flag
        for flag in FORBIDDEN_PRODUCTION_LOG_FLAGS
        if os.getenv(flag, "").strip().lower() in ("1", "true", "yes", "on")
    ]
    if enabled:
        raise RuntimeError(
            "refusing to start: token-logging/debug-PII flag(s) enabled in "
            f"production: {', '.join(sorted(enabled))} (#1076)"
        )
