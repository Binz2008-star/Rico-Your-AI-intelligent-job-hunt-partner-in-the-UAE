"""The verified job-search contract.

A chat reply may name a job only when that job arrived through a provider
execution this system can describe. Today the search path carries provider
records as bare dictionaries: by the time prose, cards and the shortlist read
them, nothing in the value says which provider produced it, when it was
fetched, or whether it survived the integrity gate. Any of those surfaces can
therefore name a company that no evidence object stands behind.

This module states the missing part once, as three values:

* :class:`SearchExecutionEvidence` — what one provider execution did. It exists
  even when the execution returned nothing, because "the provider answered and
  had no jobs" and "we never asked" are different facts and the user is owed
  the difference.
* :class:`VerifiedJobListing` — one listing that passed the integrity gate,
  reduced to the fields a surface is allowed to show.
* :class:`VerifiedJobSearchBundle` — the execution and its accepted listings,
  together. A bundle is the only thing that authorises naming a job.

The structural rule this exists to enforce: **no bundle, no named job.** No
company, no match score, no job card, no shortlist write, no apply action. A
model may explain or summarise fields that reached it inside a bundle; it may
never originate them.

All three types are frozen and slotted, so an unknown keyword is a TypeError at
construction and a field cannot be added afterwards. That is deliberate: a
contract that can be widened at a call site is not a contract. Values are
plain (str, int, bool, datetime) so the module has no dependency on the chat
layer, the provider clients, or the database — it can be imported by anything
without importing the 23k-line chat module.

What this module does NOT do: fetch, rank, score, format, translate, or decide
what to say. It describes what was retrieved. Building a bundle from a provider
result is :mod:`src.services.verified_job_search`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Tuple


class SearchStatus(str, Enum):
    """How one provider execution ended.

    Four outcomes, and every search must land on exactly one of them. They are
    distinct because they oblige different replies: ``EMPTY`` means the market
    answered and had nothing, while ``PROVIDER_UNAVAILABLE`` means we could not
    ask — telling a user "no jobs found" in the second case is a false claim
    about the market.
    """

    COMPLETED = "completed"
    EMPTY = "empty"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class SearchExecutionEvidence:
    """What one provider execution did.

    ``raw_result_count`` is what the provider returned; ``accepted_result_count``
    is what survived the integrity gate. Keeping both is the point: a search
    that fetched 20 records and accepted 0 is a very different event from one
    that fetched 0, and only the pair distinguishes them after the fact.
    """

    operation_id: str
    provider: str
    requested_role: str
    requested_location: str
    started_at: datetime
    duration_ms: int
    status: SearchStatus
    raw_result_count: int
    accepted_result_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.status, SearchStatus):
            raise TypeError(
                f"status must be a SearchStatus, got {type(self.status).__name__}"
            )
        if self.duration_ms < 0:
            raise ValueError("duration_ms cannot be negative")
        if self.raw_result_count < 0 or self.accepted_result_count < 0:
            raise ValueError("result counts cannot be negative")
        if self.accepted_result_count > self.raw_result_count:
            raise ValueError(
                "accepted_result_count cannot exceed raw_result_count "
                f"({self.accepted_result_count} > {self.raw_result_count})"
            )

    def as_public_dict(self) -> dict:
        """Counts and status only — safe to attach to a chat response.

        Never includes listing content. This is what a surface may show about
        the execution itself.
        """
        return {
            "operation_id": self.operation_id,
            "provider": self.provider,
            "status": self.status.value,
            "requested_role": self.requested_role,
            "requested_location": self.requested_location,
            "started_at": self.started_at.isoformat(),
            "duration_ms": self.duration_ms,
            "raw_result_count": self.raw_result_count,
            "accepted_result_count": self.accepted_result_count,
        }


@dataclass(frozen=True, slots=True)
class VerifiedJobListing:
    """One listing that passed the integrity gate.

    Only the fields a surface is allowed to show. ``apply_verified`` records
    whether the apply destination was established at fetch time rather than
    inferred later — a surface may offer an apply action only when it is True.
    """

    provider: str
    provider_job_id: str
    title: str
    company: str
    location: str
    apply_url: str
    source_url: str
    fetched_at: datetime
    apply_verified: bool

    def __post_init__(self) -> None:
        if not self.provider:
            raise ValueError("provider is required — a listing without a source is not verified")
        if not self.provider_job_id:
            raise ValueError("provider_job_id is required — a listing must be identifiable at its source")
        if not self.title:
            raise ValueError("title is required")
        if self.apply_verified and not self.apply_url:
            raise ValueError("apply_verified cannot be True without an apply_url")


@dataclass(frozen=True, slots=True)
class VerifiedJobSearchBundle:
    """An execution and the listings it accepted.

    A bundle with zero listings is valid and meaningful — it is the evidence
    that the search happened and found nothing trustworthy. What is not valid
    is a named job with no bundle behind it.
    """

    execution: SearchExecutionEvidence
    listings: Tuple[VerifiedJobListing, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.listings, tuple):
            raise TypeError("listings must be a tuple — a bundle is immutable once built")
        if len(self.listings) != self.execution.accepted_result_count:
            raise ValueError(
                "bundle listings must match the execution's accepted_result_count "
                f"({len(self.listings)} != {self.execution.accepted_result_count})"
            )

    @property
    def has_listings(self) -> bool:
        return bool(self.listings)


__all__ = [
    "SearchExecutionEvidence",
    "SearchStatus",
    "VerifiedJobListing",
    "VerifiedJobSearchBundle",
]
