"""
src/services/career_memory.py

Lightweight career memory layer (CAREER-OS-09).

Stores per-user career action history in the rico_agent_settings.settings JSONB
under the "_cm" key — no DB migration required. The settings table's ON CONFLICT
merge (`settings = settings || EXCLUDED.settings`) makes writes safe.

Key capabilities:
  - Record apply/save/skip/block decisions per job
  - Recall blocked companies and frequently-skipped companies
  - Build a terse memory context string for injection into Rico's chat context
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MEMORY_KEY = "_cm"
_MAX_ENTRIES = 200


# ── Internal DB helpers ──────────────────────────────────────────────────────

def _new_db() -> Any:
    from src.rico_db import RicoDB

    return RicoDB()


def _resolve_store(user_id: str) -> Optional[Tuple[Any, str, dict]]:
    """Resolve an external identity to the canonical Rico user UUID.

    ``rico_agent_settings.user_id`` is a UUID foreign key. Callers of this
    service use external identities such as email addresses, so writing the
    external value directly fails with an invalid UUID error. Resolve through
    ``get_user_bundle`` first and keep the resolved UUID paired with the
    settings loaded from that same user row.
    """
    try:
        db = _new_db()
        if not db.available:
            logger.debug("career_memory: database unavailable")
            return None

        bundle = db.get_user_bundle(user_id)
        if not bundle:
            logger.warning("career_memory: canonical user resolution returned no row")
            return None

        db_user_id = str(bundle.get("id") or "").strip()
        if not db_user_id:
            logger.warning("career_memory: canonical user row is missing id")
            return None

        return db, db_user_id, dict(bundle.get("settings") or {})
    except Exception:
        logger.warning("career_memory: canonical user resolution failed", exc_info=True)
        return None


def _read_settings(user_id: str) -> dict:
    resolved = _resolve_store(user_id)
    return resolved[2] if resolved else {}


def _write_memory(db: Any, db_user_id: str, entries: list) -> bool:
    try:
        db.upsert_settings(db_user_id, {_MEMORY_KEY: entries})
        return True
    except Exception:
        logger.warning("career_memory: memory write failed", exc_info=True)
        return False


# ── Public API ──────────────────────────────────────────────────────────────

def record_action(user_id: str, action: str, job: Dict[str, Any]) -> bool:
    """Record an action for a canonical user. Never raises.

    Returns ``True`` only when the memory update reaches the database. Existing
    callers may continue treating this as fire-and-forget, while logs and tests
    can now distinguish a successful write from a skipped/failed one.
    """
    try:
        resolved = _resolve_store(user_id)
        if not resolved:
            return False

        db, db_user_id, settings = resolved
        entries: list = list(settings.get(_MEMORY_KEY) or [])
        entries.append({
            "ts": int(time.time()),
            "a": action,
            "co": str(job.get("company") or ""),
            "ti": str(job.get("title") or ""),
            "jk": str(job.get("id") or job.get("job_key") or ""),
        })
        return _write_memory(db, db_user_id, entries[-_MAX_ENTRIES:])
    except Exception:
        logger.warning("career_memory: record_action failed", exc_info=True)
        return False


def get_memory(user_id: str) -> List[Dict[str, Any]]:
    """Return the raw career action history for a user."""
    try:
        settings = _read_settings(user_id)
        return list(settings.get(_MEMORY_KEY) or [])
    except Exception:
        return []


def get_blocked_companies(user_id: str) -> List[str]:
    """Return company names the user has explicitly blocked."""
    memory = get_memory(user_id)
    return list({e["co"] for e in memory if e.get("a") == "block" and e.get("co")})


def get_disliked_companies(user_id: str, threshold: int = 2) -> List[str]:
    """Companies the user has skipped >= threshold times — signal of disinterest."""
    from collections import Counter
    memory = get_memory(user_id)
    counts: Counter = Counter(e["co"] for e in memory if e.get("a") == "skip" and e.get("co"))
    return [co for co, n in counts.items() if n >= threshold]


def get_recent_applied(user_id: str, limit: int = 5) -> List[str]:
    """Short labels for recently applied roles."""
    memory = get_memory(user_id)
    seen: list[str] = []
    added: set[str] = set()
    for e in reversed(memory):
        if e.get("a") != "apply":
            continue
        label = f"{e.get('ti', '?')} @ {e.get('co', '?')}"
        if label not in added:
            seen.append(label)
            added.add(label)
        if len(seen) >= limit:
            break
    return seen


def build_memory_context(user_id: str) -> str:
    """Return a compact string ready for injection into Rico's system context.

    Returns "" when there is no useful memory so callers can skip appending it.
    """
    try:
        blocked = get_blocked_companies(user_id)
        disliked = get_disliked_companies(user_id)
        applied = get_recent_applied(user_id)

        parts: list[str] = []
        if blocked:
            parts.append(f"Blocked companies (never apply): {', '.join(blocked[:15])}")
        if disliked:
            skipped_only = [c for c in disliked if c not in set(blocked)]
            if skipped_only:
                parts.append(f"Frequently skipped: {', '.join(skipped_only[:10])}")
        if applied:
            parts.append(f"Recently applied: {'; '.join(applied)}")
        return "\n".join(parts)
    except Exception:
        return ""
