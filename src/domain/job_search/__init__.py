"""Job-search domain — what a verified job result is.

Public contract (import from here, not from the submodule):

    SearchStatus              how one provider execution ended
    SearchExecutionEvidence   what that execution did, counts included
    VerifiedJobListing        one listing that passed the integrity gate
    VerifiedJobSearchBundle   the execution plus its accepted listings

The rule these exist to enforce: no bundle, no named job. Building a bundle
from a provider result is ``src.services.verified_job_search``.
"""
from src.domain.job_search.contracts import (
    SearchExecutionEvidence,
    SearchStatus,
    VerifiedJobListing,
    VerifiedJobSearchBundle,
)

__all__ = [
    "SearchExecutionEvidence",
    "SearchStatus",
    "VerifiedJobListing",
    "VerifiedJobSearchBundle",
]
