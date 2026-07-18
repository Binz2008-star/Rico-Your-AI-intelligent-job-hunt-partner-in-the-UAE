"""src/repositories/job_observations_repo.py

Append-only posting-history archive (migration 046).

Every FRESH provider fetch (never a cache hit) records one row per returned
job so longitudinal posting data — first seen, re-posts, delistings — accrues
from day one.

Privacy contract (owner-approved wording): **no direct user identifiers or
raw query text**. Query context is stored only as a keyed, non-reversible
HMAC-SHA256 for longitudinal grouping — query text can embed profile-derived
terms and the query space is small enough for dictionary attacks against an
unkeyed hash. The key (``RICO_ARCHIVE_HMAC_KEY``) is dedicated to the archive
(never JWT_SECRET or any shared secret) and is never stored in the database.
Absent key ⇒ archive writes are SKIPPED entirely (fail-closed, one structured
warning without query text, search unaffected) — never a fallback to an
unkeyed hash, which would silently reintroduce the privacy gap.

Write path contract:
  * ``record_observations`` NEVER raises and adds no meaningful latency —
    failures (DB down, migration 046 not yet applied) degrade to a no-op.
  * When the table is absent (pgcode 42P01) recording disables itself for the
    rest of the process so the fetch hot path never pays for repeated failed
    inserts. Applying migration 046 + the next deploy/restart enables it.
  * Rows are append-only observations; this module intentionally has no
    update or delete functions.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from src.db import get_db_connection, is_db_available

logger = logging.getLogger(__name__)

# Bump ONLY together with a change to _normalize_part()/compute_fingerprint();
# historical rows keep their version so identities stay comparable per-version.
FINGERPRINT_VERSION = 1

_MAX_BATCH = 50

# Process-local: set when the table does not exist yet (migration 046 not
# applied). Keeps the fetch hot path free of repeated doomed inserts.
_table_missing = False

# Dedicated archive key — never JWT_SECRET or any shared secret.
_HMAC_KEY_ENV = "RICO_ARCHIVE_HMAC_KEY"
_warned_no_key = False

_INSERT_SQL = """
    INSERT INTO job_observations (
        provider, query_context_hmac, provider_job_id,
        fingerprint, fingerprint_version,
        title, company, location, country,
        claimed_posted_at, salary_string, employment_type,
        description_hash, description_len, apply_domain
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _query_context_hmac(query_context: str) -> Optional[str]:
    """Keyed, non-reversible grouping token for the producing query.

    Returns None when the dedicated key is absent — callers must then skip
    the archive write entirely. NEVER fall back to an unkeyed hash here: the
    query space is guessable, so an unkeyed hash is dictionary-attackable.
    """
    key = os.getenv(_HMAC_KEY_ENV, "").strip()
    if not key:
        return None
    if not query_context:
        return ""
    normalized = _normalize_part(query_context)
    return hmac.new(key.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def _normalize_part(value: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace (Unicode-safe for AR)."""
    cleaned = re.sub(r"[^\w\s]", " ", (value or "").lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


def compute_fingerprint(title: str, company: str, location: str) -> str:
    """Versioned canonical job identity across providers and feed refreshes.

    v1: sha256 over normalized ``company|title|city`` where city is the first
    comma-separated segment of the location (JSearch emits "Dubai, Dubai, AE",
    Jooble emits "Dubai" — both must land on the same identity).
    """
    city = (location or "").split(",")[0]
    base = "|".join((
        f"v{FINGERPRINT_VERSION}",
        _normalize_part(company),
        _normalize_part(title),
        _normalize_part(city),
    ))
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _parse_claimed_posted(raw: Any) -> Optional[datetime]:
    """Parse the provider's claimed posting timestamp; None when unusable."""
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _apply_domain(item: Dict[str, Any]) -> str:
    url = str(item.get("apply_link") or item.get("link") or "").strip()
    if not url:
        return ""
    try:
        return (urlparse(url).netloc or "")[:256]
    except ValueError:
        return ""


def _row_for(
    item: Dict[str, Any],
    provider: str,
    query_hmac: str,
    country: str,
) -> Optional[tuple]:
    title = str(item.get("title") or "").strip()
    if not title:
        return None
    company = str(item.get("company") or "").strip()
    location = str(item.get("location") or "").strip()
    description = str(item.get("description") or "")
    return (
        provider[:32],
        query_hmac,
        str(item.get("job_id") or "")[:512],
        compute_fingerprint(title, company, location),
        FINGERPRINT_VERSION,
        title[:512],
        company[:512],
        location[:512],
        (country or "ae").lower()[:8],
        _parse_claimed_posted(item.get("posted_at")),
        str(item.get("salary_string") or "")[:256],
        str(item.get("employment_type") or "")[:64],
        hashlib.sha256(description.encode("utf-8")).hexdigest() if description else "",
        len(description),
        _apply_domain(item),
    )


def record_observations(
    items: List[Dict[str, Any]],
    *,
    provider: str,
    query_context: str = "",
    country: str = "ae",
) -> int:
    """Best-effort append of one observation row per job. Never raises.

    Returns the number of rows written (0 on any skip/failure).
    """
    global _table_missing, _warned_no_key
    if _table_missing or not items or not is_db_available():
        return 0

    query_hmac = _query_context_hmac(query_context)
    if query_hmac is None:
        # Fail-closed: no dedicated key, no archive write — and no silent
        # fallback to an unkeyed hash. Search is never affected.
        if not _warned_no_key:
            _warned_no_key = True
            logger.warning(
                "job_observations: %s not set — archive writes skipped "
                "(fail-closed; search unaffected)", _HMAC_KEY_ENV,
            )
        return 0

    rows = [
        row
        for item in items[:_MAX_BATCH]
        if isinstance(item, dict) and (row := _row_for(item, provider, query_hmac, country))
    ]
    if not rows:
        return 0

    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return 0
        with conn.cursor() as cur:
            cur.executemany(_INSERT_SQL, rows)
        conn.commit()
        # Query text is never logged (it can embed profile-derived terms —
        # see tests/test_1076_log_privacy.py); it is stored, not logged.
        logger.debug(
            "job_observations: recorded %d rows provider=%s", len(rows), provider,
        )
        return len(rows)
    except Exception as exc:
        if getattr(exc, "pgcode", None) == "42P01":  # undefined_table
            _table_missing = True
            logger.info(
                "job_observations: table absent (migration 046 not applied) — "
                "archive disabled for this process"
            )
        else:
            logger.debug(
                "job_observations: write skipped err=%s", type(exc).__name__,
            )
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
