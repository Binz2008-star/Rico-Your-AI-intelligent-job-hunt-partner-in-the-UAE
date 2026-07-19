"""src/repositories/analytics_events_repo.py

First-party behavioral analytics event store (migration 047).

Foundation only: this module owns the write path, the event allowlist, the
privacy guarantees, idempotency, and retention policy. NOTHING is
instrumented yet — wiring emitters into routes is a separate change.

Privacy contract (mirrors the job_observations pattern, owner-approved):
  * Free-form text and common identifiers are blocked by structural
    enforcement: the per-event allowlist admits only booleans, bounded
    numbers, and short enum-like tokens (``_TOKEN_RE``). Free-form strings
    (emails with '@', phones with '+', names with spaces) cannot pass.
    However, the token validator still accepts identifier-shaped strings
    and digit-only values, so token-shaped or numeric identifiers could
    pass — caller discipline remains required.
  * The actor is stored only as keyed non-reversible HMAC-SHA256 under the
    dedicated ``RICO_ANALYTICS_HMAC_KEY`` (its own secret — never
    JWT_SECRET, never the archive key, never stored in the DB). Absent key
    ⇒ ALL event writes are skipped (fail-closed, one structured warning,
    product flows unaffected); never an unkeyed-hash fallback.

Idempotency: every row carries a unique ``dedupe_key``; duplicate deliveries
(retries, double-clicks) collapse via ``ON CONFLICT DO NOTHING``. Callers
with a natural idempotency token pass ``client_event_id``; otherwise the key
derives from (actor, event, canonical properties, minute bucket).

Retention: ``RETENTION_DAYS`` (180) enforced by ``purge_expired()`` — the
scheduled invocation is wired in a LATER change.

``record_event`` NEVER raises and adds no meaningful latency: DB down,
migration 047 unapplied (pgcode 42P01 latches the store off per process),
or a missing key all degrade to a silent no-op for the product flow.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.db import get_db_connection, is_db_available

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
RETENTION_DAYS = 180

# Dedicated analytics key — never JWT_SECRET, never RICO_ARCHIVE_HMAC_KEY.
_HMAC_KEY_ENV = "RICO_ANALYTICS_HMAC_KEY"

# Enum-like tokens only: lowercase alphanumerics plus _.:- , max 64 chars.
# This is the structural no-PII guarantee — emails ('@'), phone numbers
# ('+', spaces), names (uppercase/spaces), and free text cannot pass.
_TOKEN_RE = re.compile(r"^[a-z0-9_.:-]{1,64}$")

_MAX_INT = 1_000_000


def _v_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _v_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= _MAX_INT


def _v_token(value: Any) -> bool:
    return isinstance(value, str) and bool(_TOKEN_RE.match(value))


def _v_hex64(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


# Strict allowlist: event name → {property: validator}. Unknown events are
# DROPPED (warn once per name); unknown/invalid properties are STRIPPED.
# Growing this map is a reviewed change — never accept caller-defined events.
# Current count: 8 events.
EVENT_ALLOWLIST: Dict[str, Dict[str, Any]] = {
    "session_start": {"surface": _v_token},
    "signup_completed": {"attribution_source": _v_token},
    # NOTE: deliberately NO query-text property — search text can embed
    # profile-derived terms. Counts/provenance only.
    "search_performed": {
        "surface": _v_token,
        "provider": _v_token,
        "results_count": _v_int,
        "fresh": _v_bool,
    },
    "job_list_viewed": {"surface": _v_token, "page": _v_int, "results_count": _v_int},
    "job_action": {
        "action": _v_token,
        "surface": _v_token,
        "rank": _v_int,
        "boosted": _v_bool,
        # Market-side job identity (matches job_observations.fingerprint) —
        # carries no user data.
        "job_fingerprint": _v_hex64,
    },
    "profile_completed": {"completion_pct": _v_int},
    "cv_upload_completed": {"parse_quality": _v_token},
    # Future taste-loop feedback affordance (foundation reserves the name).
    "reason_chip_feedback": {"verdict": _v_token},
}

_AUDIENCES = frozenset({"user", "guest"})

_INSERT_SQL = """
    INSERT INTO analytics_events (
        occurred_at, schema_version, event_name, actor_hash,
        audience, surface, language, dedupe_key, properties
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (dedupe_key) DO NOTHING
"""

# Process-local latches (same pattern as job_observations_repo).
_table_missing = False
_warned_no_key = False
_warned_unknown_events: set[str] = set()


def _actor_hash(user_id: Optional[str]) -> Optional[str]:
    """Keyed non-reversible actor token; None ⇒ the store must skip writes.

    Returns '' for anonymous rows (no user_id). NEVER falls back to an
    unkeyed hash — identities are guessable, so an unkeyed hash would be
    dictionary-attackable.

    Guest dedupe limitation: all anonymous actors share actor_hash='', so
    identical guest events in the same minute can collapse across different
    users. This is accepted as a best-effort limitation for anonymous
    sessions; authenticated users have per-user hashes and full dedupe.
    """
    key = os.getenv(_HMAC_KEY_ENV, "").strip()
    if not key:
        return None
    if not user_id:
        return ""
    return hmac.new(key.encode("utf-8"), user_id.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()


def _clean_properties(event_name: str, properties: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Strip unknown keys and invalid values; only allowlisted survive."""
    allowed = EVENT_ALLOWLIST[event_name]
    cleaned: Dict[str, Any] = {}
    for prop_key, value in (properties or {}).items():
        validator = allowed.get(prop_key)
        if validator is None:
            logger.debug("analytics: stripped unknown property %s.%s", event_name, prop_key)
            continue
        if not validator(value):
            logger.debug("analytics: dropped invalid value for %s.%s", event_name, prop_key)
            continue
        cleaned[prop_key] = value
    return cleaned


def _dedupe_key(
    actor_hash: str,
    event_name: str,
    properties: Dict[str, Any],
    client_event_id: Optional[str],
    occurred_at: datetime,
) -> str:
    if client_event_id:
        base = "|".join(("cid", actor_hash, event_name, client_event_id.strip()[:128]))
    else:
        minute_bucket = occurred_at.replace(second=0, microsecond=0).isoformat()
        canonical = json.dumps(properties, sort_keys=True, separators=(",", ":"))
        base = "|".join(("auto", actor_hash, event_name, canonical, minute_bucket))
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def record_event(
    event_name: str,
    *,
    user_id: Optional[str] = None,
    audience: str = "user",
    surface: str = "",
    language: str = "",
    properties: Optional[Dict[str, Any]] = None,
    client_event_id: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
) -> bool:
    """Best-effort insert of one allowlisted event. Never raises.

    Returns True when a row was written; False on dedupe, validation
    rejection, or any skip/failure.
    """
    global _table_missing, _warned_no_key

    if _table_missing or not is_db_available():
        return False

    if event_name not in EVENT_ALLOWLIST:
        if event_name not in _warned_unknown_events:
            _warned_unknown_events.add(event_name)
            logger.warning("analytics: unknown event %r rejected (allowlist only)", event_name)
        return False

    actor = _actor_hash(user_id)
    if actor is None:
        if not _warned_no_key:
            _warned_no_key = True
            logger.warning(
                "analytics: %s not set — event writes skipped "
                "(fail-closed; product flows unaffected)", _HMAC_KEY_ENV,
            )
        return False

    when = occurred_at or datetime.now(timezone.utc)
    cleaned = _clean_properties(event_name, properties)
    row = (
        when,
        SCHEMA_VERSION,
        event_name,
        actor,
        audience if audience in _AUDIENCES else "user",
        surface[:32] if _v_token(surface) or surface == "" else "",
        language[:8] if _v_token(language) or language == "" else "",
        _dedupe_key(actor, event_name, cleaned, client_event_id, when),
        json.dumps(cleaned, sort_keys=True),
    )

    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return False
        with conn.cursor() as cur:
            cur.execute(_INSERT_SQL, row)
            inserted = cur.rowcount == 1
        conn.commit()
        return inserted
    except Exception as exc:
        if getattr(exc, "pgcode", None) == "42P01":  # undefined_table
            _table_missing = True
            logger.info(
                "analytics: table absent (migration 047 not applied) — "
                "event store disabled for this process"
            )
        else:
            logger.debug("analytics: write skipped err=%s", type(exc).__name__)
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def purge_expired(retention_days: int = RETENTION_DAYS) -> int:
    """Delete rows older than the retention window. Never raises.

    Returns the number of rows removed (0 on any skip/failure). The
    scheduled invocation is wired in a later change — this is the policy's
    single implementation point.

    Bounds: retention_days must be between 1 and 3650 (10 years).
    Invalid, zero, negative, non-numeric, or >3650 values return 0
    without touching the database (fail-closed).
    """
    # Validate bounds before any DB interaction
    try:
        retention_days_int = int(retention_days)
    except (ValueError, TypeError):
        return 0

    if retention_days_int < 1 or retention_days_int > 3650:
        return 0

    if not is_db_available():
        return 0
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return 0
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM analytics_events WHERE occurred_at < NOW() - (%s * INTERVAL '1 day')",
                (retention_days_int,),
            )
            removed = cur.rowcount
        conn.commit()
        if removed:
            logger.info("analytics: retention purge removed %d rows", removed)
        return removed
    except Exception as exc:
        logger.debug("analytics: purge skipped err=%s", type(exc).__name__)
        return 0
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _reset_state_for_tests() -> None:
    global _table_missing, _warned_no_key
    _table_missing = False
    _warned_no_key = False
    _warned_unknown_events.clear()
