"""Cooperative cancellation for the job-search provider cascade.

DEC-20260721-001 slice 4 (TASK-20260721-014): when a worker loses ownership of
a search operation mid-flight (a DB partition outlasts the lease and a peer
takes over — see operation_state.ownership_lost), the cascade must stop doing
NEW provider work and discard any already-in-flight response without side
effects.

Deliberately dependency-free: this module does NOT import operation_state.
`job_providers` / `jsearch_client` depend only on this tiny abstraction; the
caller (rico_chat_api) constructs a token bound to
`operation_state.ownership_lost(operation_id, attempt)` and passes it EXPLICITLY
down the cascade. That keeps the provider layer free of ownership globals and
makes the cancellation source injectable/testable.

Guarantee (NOT a claim to abort an already-sent urllib request):
    "No new provider work after cancellation becomes observable; any
     already-in-flight response is discarded without side effects."
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class CancellationToken:
    """Carries the operation identity and a check for whether it was cancelled.

    `is_cancelled` is a plain callable — usually
    `lambda: operation_state.ownership_lost(operation_id, attempt)` — so the
    provider layer never reaches into ownership globals directly."""

    operation_id: str
    attempt: int
    is_cancelled: Callable[[], bool]

    @property
    def cancelled(self) -> bool:
        """True once cancellation is observable. Never raises.

        FAIL-CLOSED: this token exists only because the caller wanted the
        cascade cancellable for a specific (operation_id, attempt). If the
        ownership check itself breaks, we CANNOT prove we still own the
        operation, so a broken check must be treated as cancelled — never as a
        licence to start more provider work. (Token absence stays fail-open and
        is handled by `is_cancelled(None)` below: no token → never cancelled.)"""
        try:
            return bool(self.is_cancelled())
        except Exception:
            return True


def is_cancelled(token: Optional["CancellationToken"]) -> bool:
    """Null-safe helper: an absent token means 'never cancelled' (the default
    for every existing caller that does not pass one)."""
    return token is not None and token.cancelled
