"""src/repositories/job_observations_repo.py

Append-only posting-history archive (migration 046).

Every FRESH provider fetch (never a cache hit) records one row per returned
job so longitudinal posting data — first seen, re-posts, delistings — accrues
from day one. The table describes the job market, not users: no user_id, no
session identity, no request context beyond the query string.

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
import logging
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

_INSERT_SQL = """
    INSERT INTO job_observations (
        provider, query_context, provider_job_id,
        fingerprint, fingerprint_version,
        title, company, location, country,
        claimed_posted_at, salary_string, employment_type,
        description_hash, description_len, apply_domain
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


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
    query_context: str,
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
        (query_context or "")[:256],
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
    global _table_missing
    if _table_missing or not items or not is_db_available():
        return 0

    rows = [
        row
        for item in items[:_MAX_BATCH]
        if isinstance(item, dict) and (row := _row_for(item, provider, query_context, country))
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
        logger.debug(
            "job_observations: recorded %d rows provider=%s query=%r",
            len(rows), provider, query_context,
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
    global _table_missing
    _table_missing = False
