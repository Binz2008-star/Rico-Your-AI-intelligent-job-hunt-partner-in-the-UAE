"""The document inventory contract.

Three surfaces answer "which documents does this user have, and which CV is
the active one" today, and they answer it from raw row dictionaries with
their own inline rules. This module states the rules once, over values that
have already been loaded, so a caller can adopt it without changing how it
reads the database.

What the contract decides:

* what a ``doc_type`` string means (:class:`DocumentKind`) — an unrecognised
  type is ``OTHER``, never a CV;
* which CV is the active one (:attr:`DocumentInventory.active_cv`) — the
  primary stored CV, else the newest stored CV, else a profile-grounded
  legacy CV;
* what the storage limits count (:attr:`DocumentInventory.quota_counts`) —
  stored rows only, because a legacy record is a projection of the profile
  and occupies no storage;
* whether the user has a CV at all, and whether their files are identity
  documents only.

What the contract deliberately does NOT decide: whether a legacy profile CV
record exists in the first place. That judgement needs the CV extraction
state, it is where the surfaces currently disagree, and it belongs to the CV
slice rather than this one. Callers pass in the records they already build;
see the divergence tests in ``tests/unit/test_document_inventory_contract.py``.

Ordering rule: ``records`` is kept exactly as the caller supplied it, so
adopting the contract can never reshuffle what a user sees. Ordering is used
only inside the active-CV decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Optional, Sequence


class DocumentKind(str, Enum):
    """What a stored document is.

    A ``str`` enum so a kind can be compared with, and serialised as, the
    ``doc_type`` values already in the database and on the wire.
    """

    CV = "cv"
    COVER_LETTER = "cover_letter"
    IDENTITY_DOCUMENT = "identity_document"
    OTHER = "other"

    @classmethod
    def parse(cls, raw: Any) -> "DocumentKind":
        """Normalise a stored ``doc_type`` into a kind. Never raises.

        Anything unrecognised — including ``None``, an empty string, or a
        type a future upload path invents — is :attr:`OTHER`. Unknown input
        must never be promoted into :attr:`CV`: a wrong CV answer is what
        makes the product claim a CV it cannot read.
        """
        if isinstance(raw, DocumentKind):
            return raw
        text = str(raw or "").strip().lower()
        for kind in cls:
            if kind.value == text:
                return kind
        return cls.OTHER


class DocumentOrigin(str, Enum):
    """Where a record came from.

    ``STORED``          a row in the documents table — real, deletable, counted.
    ``PROFILE_LEGACY``  synthesised from the profile's CV grounding for users
                        who predate multi-document storage. Not a row: it
                        cannot be renamed, and it occupies no quota.
    """

    STORED = "stored"
    PROFILE_LEGACY = "profile_legacy"


@dataclass(frozen=True)
class DocumentRecord:
    """One document as the product reasons about it."""

    document_id: str
    kind: DocumentKind
    origin: DocumentOrigin = DocumentOrigin.STORED
    filename: Optional[str] = None
    label: Optional[str] = None
    is_primary: bool = False
    created_at: Optional[str] = None

    @property
    def is_stored(self) -> bool:
        return self.origin is DocumentOrigin.STORED

    @property
    def is_cv(self) -> bool:
        return self.kind is DocumentKind.CV

    @property
    def counts_against_quota(self) -> bool:
        """Only stored rows occupy storage; a legacy projection does not."""
        return self.is_stored

    @property
    def display_name(self) -> str:
        """A non-empty name to show. Falls back through label, then the id."""
        return self.label or self.filename or self.document_id


@dataclass(frozen=True)
class QuotaCounts:
    """What the storage limits are counted against."""

    cv: int = 0
    other: int = 0

    @property
    def total(self) -> int:
        return self.cv + self.other


@dataclass(frozen=True)
class DocumentInventory:
    """A user's documents plus the decisions taken over them."""

    records: tuple[DocumentRecord, ...] = ()

    # ── membership ────────────────────────────────────────────────────────

    @property
    def cv_records(self) -> tuple[DocumentRecord, ...]:
        return tuple(r for r in self.records if r.is_cv)

    @property
    def stored_records(self) -> tuple[DocumentRecord, ...]:
        return tuple(r for r in self.records if r.is_stored)

    # ── decisions ─────────────────────────────────────────────────────────

    @property
    def active_cv(self) -> Optional[DocumentRecord]:
        """The CV the product should treat as the user's CV, or ``None``.

        Precedence: the primary stored CV, then the newest stored CV, then a
        legacy profile CV. A stored CV always wins over the profile
        projection, because the projection is a copy of grounding that a real
        upload has already superseded.
        """
        stored_cvs = [r for r in self.cv_records if r.is_stored]
        for record in stored_cvs:
            if record.is_primary:
                return record
        if stored_cvs:
            return _newest(stored_cvs)
        legacy_cvs = [r for r in self.cv_records if not r.is_stored]
        return legacy_cvs[0] if legacy_cvs else None

    @property
    def primary_stored_cv(self) -> Optional[DocumentRecord]:
        """The stored CV explicitly marked primary, or ``None``."""
        for record in self.cv_records:
            if record.is_stored and record.is_primary:
                return record
        return None

    @property
    def has_cv(self) -> bool:
        return self.active_cv is not None

    @property
    def has_only_identity_documents(self) -> bool:
        """True when the user has files, none is a CV, and one is an ID.

        False for an empty inventory: having nothing is not the same problem
        as having uploaded a passport instead of a CV, and the two lead to
        different things being said to the user.
        """
        if not self.records:
            return False
        if self.cv_records:
            return False
        return any(r.kind is DocumentKind.IDENTITY_DOCUMENT for r in self.records)

    @property
    def quota_counts(self) -> QuotaCounts:
        """Stored-row counts, split the way the storage limits are expressed."""
        cv = sum(1 for r in self.records if r.counts_against_quota and r.is_cv)
        other = sum(1 for r in self.records if r.counts_against_quota and not r.is_cv)
        return QuotaCounts(cv=cv, other=other)


def build_inventory(records: Iterable[DocumentRecord]) -> DocumentInventory:
    """Build an inventory, preserving the caller's order."""
    return DocumentInventory(records=tuple(records))


# ── internals ─────────────────────────────────────────────────────────────

def _newest(records: Sequence[DocumentRecord]) -> DocumentRecord:
    """The most recently created record; caller order breaks ties.

    A record whose ``created_at`` is missing or unreadable sorts last rather
    than being dropped — an unparseable timestamp must not hide a document.
    """
    best = records[0]
    best_at = _parsed_timestamp(best.created_at)
    for record in records[1:]:
        at = _parsed_timestamp(record.created_at)
        if at is None:
            continue
        if best_at is None or at > best_at:
            best, best_at = record, at
    return best


def _parsed_timestamp(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    # Naive and aware timestamps can both appear (isoformat of a column
    # without a zone). Compare on one scale instead of raising.
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
