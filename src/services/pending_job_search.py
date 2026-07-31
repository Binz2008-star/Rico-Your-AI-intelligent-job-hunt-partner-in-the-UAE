"""Typed PendingJobSearch contract and repository.

Stores pending job-search confirmations in
``rico_agent_settings.settings['_pjs']`` so the state survives server
restarts, multi-worker deployments, and ``RICO_MEMORY_BACKEND=postgres``
(where ``RicoMemoryStore.set_context`` is a no-op).

Architecture invariant
---------------------
``rico_agent_settings`` is a per-user JSONB row. The top-level key ``_pjs``
carries exactly one pending operation per user.  Atomic consume uses a
transaction-scoped row lock so that concurrent confirmations cannot both
win.

Dialogue state vs Execution ownership
-------------------------------------
PendingJobSearch answers *"What is Rico waiting for?"*.
``operation_state.py`` answers *"Who owns this execution?"*.
They are separate concerns and must not be collapsed.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

_PJS_KEY = "_pjs"
_DEFAULT_TTL_SECONDS = 900  # 15 minutes, matching legacy behaviour


@dataclass(frozen=True)
class PendingJobSearch:
    """Immutable pending job-search confirmation.

    Every field is set at construction and never mutated.  Serialises safely
    to JSON for storage in ``rico_agent_settings.settings`` JSONB.
    """

    token: str
    role: str
    location: str
    reason: str
    created_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not self.token or not self.token.strip():
            raise ValueError("token must be a non-empty string")
        if not self.role or not self.role.strip():
            raise ValueError("role must be a non-empty string")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_expired

    def to_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "role": self.role,
            "location": self.location,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PendingJobSearch:
        raw_token = data.get("token") or ""
        raw_role = data.get("role") or ""
        raw_loc = data.get("location") or ""
        raw_reason = data.get("reason") or ""
        raw_created = data.get("created_at") or ""
        raw_expires = data.get("expires_at") or ""
        if not raw_token.strip():
            raise ValueError("malformed PendingJobSearch: missing token")
        if not raw_role.strip():
            raise ValueError("malformed PendingJobSearch: missing role")
        return cls(
            token=str(raw_token).strip(),
            role=str(raw_role).strip(),
            location=str(raw_loc).strip(),
            reason=str(raw_reason).strip(),
            created_at=_parse_dt(raw_created),
            expires_at=_parse_dt(raw_expires),
        )


def _parse_dt(raw: str | datetime) -> datetime:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw
    if not raw:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(str(raw))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def new_pending(
    *,
    role: str,
    location: str = "",
    reason: str = "promise",
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> PendingJobSearch:
    """Factory: mint a fresh ``PendingJobSearch`` with an auto-generated token."""
    now = datetime.now(timezone.utc)
    return PendingJobSearch(
        token=str(uuid.uuid4()),
        role=role.strip(),
        location=location.strip(),
        reason=reason.strip(),
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )


class PendingJobSearchUnavailable(Exception):
    """The store is unavailable (DB down, identity resolution failure, etc.)."""


class PendingJobSearchConsumed(Exception):
    """The pending search was already consumed by another caller."""


# ── Typed lookup outcome ──────────────────────────────────────────────────────
# Distinguishes DB-unavailable from genuine-no-pending so callers never
# misclassify an outage as "nothing to do".


class LookupStatus:
    FOUND = "found"
    NONE = "none"
    UNAVAILABLE = "unavailable"
    MALFORMED = "malformed"
    EXPIRED = "expired"


class PendingSearchLookup:
    """Typed result of a pending-job-search lookup.

    Attributes:
        status: One of ``LookupStatus.*``.
        pjs: The deserialised ``PendingJobSearch`` when status is FOUND or EXPIRED.
    """

    __slots__ = ("status", "pjs")

    def __init__(self, status: str, pjs: PendingJobSearch | None = None) -> None:
        self.status = status
        self.pjs = pjs


# ── Structured offer marker ───────────────────────────────────────────────────
# Private transient marker that travels with response dicts during assembly
# only.  Never reaches API clients, persisted history, logs, or model context.

_PJS_OFFER_FIELD = "_pending_job_search_offer"


def make_offer(
    role: str,
    location: str = "",
    reason: str = "promise",
) -> dict[str, str]:
    """Build a private offer marker dict for the pending-job-search protocol.

    The marker is consumed (removed) before the response leaves the API layer.
    """
    return {
        "role": role,
        "location": location,
        "reason": reason,
    }


def is_offer_present(result: dict) -> bool:
    """True when the response dict carries an armed offer marker."""
    return _PJS_OFFER_FIELD in result


def remove_offer(result: dict) -> None:
    """Safely strip the private offer marker from a response dict."""
    result.pop(_PJS_OFFER_FIELD, None)


# ── Reply classification ──────────────────────────────────────────────────────

import re as _re


# English confirmation signals — strict subset so "yes" for a different
# pending action is never misclassified as job-search confirmation.
_CONFIRM_WORDS: frozenset[str] = frozenset({
    "yes", "yeah", "yep", "yup", "ok", "okay", "sure", "do it", "go ahead",
    "confirm", "confirmed", "proceed",
})
# Arabic confirmation signals
_AR_CONFIRM_WORDS: frozenset[str] = frozenset({
    "نعم", "أيوه", "ايوه", "اوك", "حسنا", "ماشي", "تمام", "طيب", "يلا",
    "اكيد", "طبعا", "موافق", "تفضل",
})
# Continuation phrases — these also count as CONFIRM in the context of a
# pending job search.  Matched via regex so multi-word phrases that are not
# job titles ("keep going", "continue please") are caught correctly.
_CONTINUATION_PATTERNS = (
    r"keep\s+going|"
    r"carry\s+on|"
    r"go\s+ahead|"
    r"(?:yes|ok|okay|sure|alright|just)\s+(?:continue|proceed|go\s+on|carry\s+on|go\s+ahead|keep\s+going)|"
    r"(?:continue|proceed|carry\s+on|go\s+ahead)\s+please|"
    r"please\s+(?:continue|proceed|carry\s+on|go\s+ahead)|"
    r"lets\s+continue|let's\s+continue|"
    r"sounds\s+good\s+continue|"
    r"continue(?:,\s*please)?$|"
    r"proceed$"
)
_CONTINUATION_RE = _re.compile(_CONTINUATION_PATTERNS, _re.IGNORECASE)
# Arabic continuation
_AR_CONTINUATION_WORDS: frozenset[str] = frozenset({
    "كمل", "استمر", "واصل", "نفذ", "راجعها", "وسع",
})
_AR_CONTINUATION_PREFIXES: frozenset[str] = frozenset({
    "ماشي كمل", "تمام كمل", "اوك كمل", "اوكي كمل", "يلا كمل",
    "نعم كمل", "حسنا كمل", "طيب كمل", "نعم استمر", "ماشي استمر",
    "تمام استمر", "اوك استمر", "يلا استمر",
})
# Cancel / decline signals
_CANCEL_WORDS: frozenset[str] = frozenset({
    "no", "nope", "nah", "cancel", "never mind", "skip", "stop", "forget it",
    "لا", "لأ", "الغاء", "إلغاء", "لا شكرا", "لا شكراً",
})
# Explicit new-request signals — when the user asks for something different
_NEW_REQUEST_WORDS: frozenset[str] = frozenset({
    "search", "find", "look for", "ابحث", "دور", "بحث", "شويف",
})
# Role-change signals inside a confirmation-like message
_CHANGE_ROLE_RE = _re.compile(
    r"(?:yes|ok|sure|نعم|تمام|حسنا|طيب|اوك)[,\s]+(?:search|find|ابحث|دور|شويف)\s+(.+)$",
    _re.IGNORECASE,
)
_AR_CHANGE_ROLE_RE = _re.compile(
    r"(?:نعم|تمام|حسنا|طيب|اوك|ايوه)\s+(?:ابحث|دور|بحث|شويف)\s+(.+)",
    _re.IGNORECASE,
)
# Location-only change: "نعم في أبوظبي" or "yes in Abu Dhabi"
_CHANGE_LOCATION_EN_RE = _re.compile(
    r"^(?:yes|ok|okay|sure|yeah)\s+in\s+(.+)$",
    _re.IGNORECASE,
)
_CHANGE_LOCATION_AR_RE = _re.compile(
    r"^(?:نعم|تمام|حسنا|طيب|اوك|ايوه|ماشي)\s+في\s+(.+)$",
    _re.IGNORECASE,
)
_LOCATION_RE = _re.compile(
    r"\b(?:في|بـ|ب|بال|فى|بى|in)\s*([\u0600-\u06FF\w]+)",
    _re.IGNORECASE,
)


class ReplyCategory:
    CONFIRM = "confirm"
    CANCEL = "cancel"
    CHANGE = "change"
    NEW_REQUEST = "new_request"
    OTHER = "other"


# Minimal normalisation for Arabic — reuse the same _normalize_arabic
# pattern already established in the codebase.
def _normalize_ar(text: str) -> str:
    text = _re.sub(r"[\u064B-\u065F\u0670]", "", text)  # diacritics
    text = _re.sub(r"[آأإٱ]", "ا", text)
    text = _re.sub(r"ى", "ي", text)
    text = _re.sub(r"ة", "ه", text)
    # Normalise tanween-alef
    text = text.replace("اً", "ا").replace("ًا", "ا")
    return text


def _clean_text(message: str) -> str:
    """Strip trailing punctuation and normalise whitespace."""
    text = (message or "").strip()
    text = _re.sub(r"[\s؟?.!،,‌‍;:…]+", " ", text).strip().lower()
    # Also normalise Arabic in the cleaned text
    text = _normalize_ar(text)
    return text


def classify_reply(message: str) -> tuple[str, Optional[str], Optional[str]]:
    """:return: (category, extracted_role, extracted_location).

    ``extracted_role`` is populated only for CHANGE replies.
    ``extracted_location`` is populated from inline location signals.
    """
    text = _clean_text(message)
    if not text:
        return (ReplyCategory.OTHER, None, None)

    # 1. Extract inline location (from raw message for Arabic script matching)
    _loc: Optional[str] = None
    raw = message or ""
    loc_m = _LOCATION_RE.search(raw)
    if loc_m:
        candidate = loc_m.group(1).strip()
        if candidate and len(candidate) > 1:
            _loc = candidate

    # 2. Arabic role-change pattern: "نعم ابحث عن مهندس"
    ar_role = _AR_CHANGE_ROLE_RE.search(text)
    if ar_role:
        return (ReplyCategory.CHANGE, ar_role.group(1).strip(), _loc)

    # 3. English/Generic role-change pattern: "yes, search Product Manager"
    en_role = _CHANGE_ROLE_RE.search(text)
    if en_role:
        return (ReplyCategory.CHANGE, en_role.group(1).strip(), _loc)

    # 4. Location-only change: "نعم في أبوظبي" or "yes in Abu Dhabi"
    loc_change_en = _CHANGE_LOCATION_EN_RE.match(text)
    if loc_change_en:
        extracted = loc_change_en.group(1).strip()
        return (ReplyCategory.CHANGE, None, extracted if len(extracted) > 1 else _loc)

    loc_change_ar = _CHANGE_LOCATION_AR_RE.match(text)
    if loc_change_ar:
        extracted = loc_change_ar.group(1).strip()
        return (ReplyCategory.CHANGE, None, extracted if len(extracted) > 1 else _loc)

    # 5. Pure cancel
    if text in _CANCEL_WORDS:
        return (ReplyCategory.CANCEL, None, _loc)

    # 6. Pure confirm — only exact word matches, never a sentence
    if text in _CONFIRM_WORDS or text in _AR_CONFIRM_WORDS:
        return (ReplyCategory.CONFIRM, None, _loc)

    # 7. Continuation phrases ("keep going", "continue", "كمل")
    if _CONTINUATION_RE.match(text):
        return (ReplyCategory.CONFIRM, None, _loc)
    if text in _AR_CONTINUATION_WORDS:
        return (ReplyCategory.CONFIRM, None, _loc)
    # Check Arabic continuation prefixes
    for prefix in _AR_CONTINUATION_PREFIXES:
        if text.startswith(prefix):
            return (ReplyCategory.CONFIRM, None, _loc)

    # 8. New explicit request — "search for X", "ابحث عن مهندس"
    first_word = text.split()[0] if text.split() else ""
    if first_word in _NEW_REQUEST_WORDS and len(text.split()) > 1:
        return (ReplyCategory.NEW_REQUEST, None, _loc)

    return (ReplyCategory.OTHER, None, _loc)


# ── Repository ─────────────────────────────────────────────────────────────────

def _resolve_db_user_id(db, user_id: str) -> str | None:
    """Resolve an external identity to the canonical database user UUID.

    Returns ``None`` when resolution fails (ambiguous, unavailable, not found).
    """
    try:
        bundle = db.get_user_bundle(user_id)
    except Exception:
        return None
    if bundle is None:
        return None
    raw = bundle.get("id")
    if raw is None:
        return None
    return str(raw)


class PendingJobSearchRepo:
    """Postgres-backed pending job-search store.

    Every public method resolves ``user_id`` to a canonical database UUID
    before touching ``rico_agent_settings``, so an external identifier
    (email, telegram handle) never accidentally reads or writes the wrong
    row.
    """

    def __init__(self, db) -> None:
        self._db = db

    # ── store ──────────────────────────────────────────────────────────────

    def store(self, user_id: str, pending: PendingJobSearch) -> bool:
        """Persist a pending search.  Returns True on success."""
        db_uuid = _resolve_db_user_id(self._db, user_id)
        if db_uuid is None:
            return False
        try:
            self._db.upsert_settings(db_uuid, {_PJS_KEY: pending.to_dict()})
            return True
        except Exception:
            return False

    # ── get ─────────────────────────────────────────────────────────────────

    def get(self, user_id: str) -> Optional[PendingJobSearch]:
        """Read the current pending search, or None.

        Expired entries are treated as missing (lazy expiry).
        """
        raw = self._read_raw(user_id)
        if raw is None:
            return None
        try:
            pjs = PendingJobSearch.from_dict(raw)
        except (ValueError, TypeError, KeyError):
            return None
        if pjs.is_expired:
            return None
        return pjs

    # ── consume (ATOMIC) ────────────────────────────────────────────────────

    def consume(self, user_id: str, token: str) -> Optional[PendingJobSearch]:
        """Atomically read, validate, and remove the pending search.

        One database transaction with a row lock guarantees that two
        concurrent callers produce exactly one winner.
        """
        db_uuid = _resolve_db_user_id(self._db, user_id)
        if db_uuid is None:
            return None
        try:
            conn = self._db.connect()
        except Exception:
            return None
        try:
            with conn.cursor() as cur:
                # 1. Row-level lock on the settings row
                cur.execute(
                    "SELECT settings FROM rico_agent_settings "
                    "WHERE user_id = %s FOR UPDATE",
                    (db_uuid,),
                )
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    return None
                settings = row["settings"] if isinstance(row, dict) else row[0]
                if not settings or not isinstance(settings, dict):
                    conn.rollback()
                    return None
                raw = settings.get(_PJS_KEY)
                if raw is None:
                    conn.rollback()
                    return None
                # 2. Deserialise
                try:
                    pjs = PendingJobSearch.from_dict(raw)
                except (ValueError, TypeError, KeyError):
                    conn.rollback()
                    return None
                # 3. Validate token and expiry
                if pjs.token != token:
                    conn.rollback()
                    return None
                if pjs.is_expired:
                    conn.rollback()
                    return None
                # 4. Remove the key — atomic clear
                new_settings = dict(settings)
                new_settings.pop(_PJS_KEY, None)
                cur.execute(
                    "UPDATE rico_agent_settings SET settings = %s, updated_at = now() "
                    "WHERE user_id = %s",
                    (json.dumps(new_settings), db_uuid),
                )
            conn.commit()
            return pjs
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ── discard_token (ATOMIC, token-qualified) ──────────────────────────────

    def discard_token(self, user_id: str, token: str) -> bool:
        """Atomically remove the ``_pjs`` key ONLY when its token matches.

        Unlike ``consume``, this removes the key even when the entry is
        expired, so stale state can be cleaned up without executing it.
        Returns True when the key was removed; False on token mismatch,
        missing state, or DB failure.  The row lock prevents a concurrent
        store of a replacement token from being clobbered.
        """
        db_uuid = _resolve_db_user_id(self._db, user_id)
        if db_uuid is None:
            return False
        try:
            conn = self._db.connect()
        except Exception:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT settings FROM rico_agent_settings "
                    "WHERE user_id = %s FOR UPDATE",
                    (db_uuid,),
                )
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    return False
                settings = row["settings"] if isinstance(row, dict) else row[0]
                if not settings or not isinstance(settings, dict):
                    conn.rollback()
                    return False
                raw = settings.get(_PJS_KEY)
                if raw is None:
                    conn.rollback()
                    return False
                try:
                    pjs = PendingJobSearch.from_dict(raw)
                except (ValueError, TypeError, KeyError):
                    conn.rollback()
                    return False
                if pjs.token != token:
                    conn.rollback()
                    return False
                new_settings = dict(settings)
                new_settings.pop(_PJS_KEY, None)
                cur.execute(
                    "UPDATE rico_agent_settings SET settings = %s, updated_at = now() "
                    "WHERE user_id = %s",
                    (json.dumps(new_settings), db_uuid),
                )
            conn.commit()
            return True
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ── cancel ──────────────────────────────────────────────────────────────

    def cancel(self, user_id: str) -> bool:
        """Clear the pending search without executing it."""
        db_uuid = _resolve_db_user_id(self._db, user_id)
        if db_uuid is None:
            return False
        try:
            conn = self._db.connect()
        except Exception:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT settings FROM rico_agent_settings "
                    "WHERE user_id = %s FOR UPDATE",
                    (db_uuid,),
                )
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    return False
                settings = row["settings"] if isinstance(row, dict) else row[0]
                if not settings or not isinstance(settings, dict):
                    conn.rollback()
                    return False
                if _PJS_KEY not in settings:
                    conn.rollback()
                    return False
                new_settings = dict(settings)
                new_settings.pop(_PJS_KEY, None)
                cur.execute(
                    "UPDATE rico_agent_settings SET settings = %s, updated_at = now() "
                    "WHERE user_id = %s",
                    (json.dumps(new_settings), db_uuid),
                )
            conn.commit()
            return True
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ── supersede ────────────────────────────────────────────────────────────

    def supersede(self, user_id: str, old_token: str, replacement: PendingJobSearch) -> bool:
        """Atomically cancel an existing token and store a replacement."""
        db_uuid = _resolve_db_user_id(self._db, user_id)
        if db_uuid is None:
            return False
        try:
            conn = self._db.connect()
        except Exception:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT settings FROM rico_agent_settings "
                    "WHERE user_id = %s FOR UPDATE",
                    (db_uuid,),
                )
                row = cur.fetchone()
                if row is None:
                    conn.rollback()
                    return False
                settings = row["settings"] if isinstance(row, dict) else row[0]
                if not settings or not isinstance(settings, dict):
                    conn.rollback()
                    return False
                raw = settings.get(_PJS_KEY)
                if raw is not None:
                    try:
                        existing = PendingJobSearch.from_dict(raw)
                    except (ValueError, TypeError, KeyError):
                        conn.rollback()
                        return False
                    if existing.token != old_token:
                        conn.rollback()
                        return False
                new_settings = dict(settings)
                new_settings[_PJS_KEY] = replacement.to_dict()
                cur.execute(
                    "UPDATE rico_agent_settings SET settings = %s, updated_at = now() "
                    "WHERE user_id = %s",
                    (json.dumps(new_settings), db_uuid),
                )
            conn.commit()
            return True
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ── lookup (typed) ────────────────────────────────────────────────────────

    def lookup(self, user_id: str) -> PendingSearchLookup:
        """Typed lookup that distinguishes DB-unavailable from genuine absence.

        Returns one of:

        * ``FOUND`` — valid pending search exists (``pjs`` populated).
        * ``NONE`` — no pending row, no user row, no settings, or no ``_pjs``
          key.  A missing user row is NOT an outage — it is a genuine absence
          of pending state.
        * ``UNAVAILABLE`` — DB unreachable or ``get_user_bundle`` threw an
          exception.
        * ``MALFORMED`` — the stored value exists but cannot be deserialised.
        * ``EXPIRED`` — found but past its TTL (``pjs`` populated for logging).
        """
        # Do NOT use ``_resolve_db_user_id`` here: that helper conflates
        # user-not-found with DB-unavailable.  We call ``get_user_bundle``
        # directly so we can separate the two.
        try:
            bundle = self._db.get_user_bundle(user_id)
        except Exception:
            return PendingSearchLookup(LookupStatus.UNAVAILABLE)
        if bundle is None:
            return PendingSearchLookup(LookupStatus.NONE)
        raw_id = bundle.get("id")
        if raw_id is None:
            return PendingSearchLookup(LookupStatus.NONE)
        settings = bundle.get("settings")
        if not settings or not isinstance(settings, dict):
            return PendingSearchLookup(LookupStatus.NONE)
        raw = settings.get(_PJS_KEY)
        if raw is None:
            return PendingSearchLookup(LookupStatus.NONE)
        if not isinstance(raw, dict):
            return PendingSearchLookup(LookupStatus.MALFORMED)
        try:
            pjs = PendingJobSearch.from_dict(raw)
        except (ValueError, TypeError, KeyError):
            return PendingSearchLookup(LookupStatus.MALFORMED)
        if pjs.is_expired:
            return PendingSearchLookup(LookupStatus.EXPIRED, pjs)
        return PendingSearchLookup(LookupStatus.FOUND, pjs)

    # ── internal helpers ────────────────────────────────────────────────────

    def _read_raw(self, user_id: str) -> Optional[dict[str, Any]]:
        """Read the raw _pjs dict from the settings JSONB, or None."""
        db_uuid = _resolve_db_user_id(self._db, user_id)
        if db_uuid is None:
            return None
        try:
            bundle = self._db.get_user_bundle(db_uuid)
        except Exception:
            return None
        if bundle is None:
            return None
        settings = bundle.get("settings")
        if not settings or not isinstance(settings, dict):
            return None
        raw = settings.get(_PJS_KEY)
        if not raw or not isinstance(raw, dict):
            return None
        return raw
