"""The search path may not name a job without provenance behind it.

Fail-first record. Before the verified-search contract existed, the first test
below failed on ``main``: ``_target_role_search_response`` returned a
``job_matches`` response carrying titles and companies, and nothing in that
response said which provider produced them, when, or how many raw records were
rejected to get there. The job structure was real; the provenance was absent.

These tests pin the four permitted outcomes for that one adopted consumer:

    verified results   -> job_matches, with evidence, every match backed by a
                          VerifiedJobListing
    empty              -> no matches, evidence present, status "empty"
    provider unavailable -> no matches, evidence present, status
                          "provider_unavailable"; never "no jobs found"
    clarification      -> names no job at all

Synthetic data only. No provider, no database, no network.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.job_search import (
    SearchExecutionEvidence,
    SearchStatus,
    VerifiedJobListing,
    VerifiedJobSearchBundle,
)
from src.services.verified_job_search import build_bundle


def _record(**overrides):
    """A provider record that passes the integrity gate."""
    base = {
        "title": "Compliance Manager",
        "company": "Meridian Bank",
        "location": "Dubai, UAE",
        "apply_url": "https://example.com/jobs/compliance-manager-1",
        "source_url": "https://example.com/jobs/compliance-manager-1",
        "description": "Compliance Manager role in Dubai. Regulatory compliance and AML oversight.",
        "source": "jsearch",
        "job_id": "prov-1",
    }
    base.update(overrides)
    return base


def _started():
    return datetime(2026, 7, 26, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# The defect this PR closes
# ---------------------------------------------------------------------------


def test_named_job_requires_a_bundle_behind_it():
    """A listing may be named only if a VerifiedJobListing stands behind it.

    This is the assertion that had nothing to bind to on main: there was no
    bundle, so a caller could hold a title and a company with no execution
    record at all.
    """
    bundle, accepted, _ = build_bundle(
        [_record()],
        operation_id="op-1",
        provider="jsearch",
        requested_role="Compliance Manager",
        requested_location="Dubai",
        started_at=_started(),
        duration_ms=120,
        status=SearchStatus.COMPLETED,
    )

    assert bundle.has_listings, "a trustworthy record must survive into the bundle"
    assert len(accepted) == len(bundle.listings), "records and listings must be index-aligned"

    listing = bundle.listings[0]
    assert listing.provider, "a named job must say which provider produced it"
    assert listing.provider_job_id, "a named job must be identifiable at its source"
    assert listing.fetched_at.tzinfo is not None, "fetched_at must be an absolute instant"
    assert bundle.execution.raw_result_count == 1
    assert bundle.execution.accepted_result_count == 1


# ---------------------------------------------------------------------------
# The four permitted outcomes
# ---------------------------------------------------------------------------


def test_outcome_empty_is_evidence_not_silence():
    """The provider answered and had nothing. That is a fact, and it is recorded."""
    bundle, accepted, _ = build_bundle(
        [],
        operation_id="op-2",
        provider="jsearch",
        requested_role="Compliance Manager",
        requested_location="Dubai",
        started_at=_started(),
        duration_ms=90,
        status=SearchStatus.COMPLETED,
    )

    assert accepted == []
    assert bundle.listings == ()
    assert bundle.execution.status is SearchStatus.EMPTY, (
        "a completed search that accepted nothing is EMPTY, not COMPLETED"
    )
    assert bundle.execution.raw_result_count == 0


def test_outcome_provider_unavailable_is_not_reported_as_no_jobs():
    """We could not ask. That must never be phrased as 'no jobs found'."""
    bundle, _, _ = build_bundle(
        [],
        operation_id="op-3",
        provider="none",
        requested_role="Compliance Manager",
        requested_location="Dubai",
        started_at=_started(),
        duration_ms=15,
        status=SearchStatus.PROVIDER_UNAVAILABLE,
    )

    assert bundle.execution.status is SearchStatus.PROVIDER_UNAVAILABLE
    assert not bundle.has_listings


def test_outcome_cancelled_keeps_its_own_status():
    bundle, _, _ = build_bundle(
        [],
        operation_id="op-4",
        provider="jsearch",
        requested_role="Compliance Manager",
        requested_location="Dubai",
        started_at=_started(),
        duration_ms=5,
        status=SearchStatus.CANCELLED,
    )

    assert bundle.execution.status is SearchStatus.CANCELLED


# ---------------------------------------------------------------------------
# The gate runs here, once, before anything is nameable
# ---------------------------------------------------------------------------


def test_integrity_rejected_records_never_reach_the_caller():
    """A record the gate rejects is absent from both the bundle and the records."""
    good = _record()
    # Non-UAE location: rejected by the gate, which runs with uae_only=True.
    bad = _record(
        title="Compliance Manager",
        company="Offshore Ltd",
        location="London, United Kingdom",
        apply_url="https://example.com/jobs/london-1",
        job_id="prov-2",
    )

    bundle, accepted, rejections = build_bundle(
        [good, bad],
        operation_id="op-5",
        provider="jsearch",
        requested_role="Compliance Manager",
        requested_location="Dubai",
        started_at=_started(),
        duration_ms=140,
        status=SearchStatus.COMPLETED,
    )

    assert bundle.execution.raw_result_count == 2
    assert bundle.execution.accepted_result_count == len(bundle.listings)
    assert all("United Kingdom" not in listing.location for listing in bundle.listings)
    assert all("United Kingdom" not in (r.get("location") or "") for r in accepted)
    if bundle.execution.accepted_result_count < 2:
        assert rejections, "a dropped record must be counted, not silently lost"


def test_gate_failure_fails_closed(monkeypatch):
    """If the integrity gate cannot run, nothing is nameable."""
    import src.job_integrity as job_integrity

    def _boom(*args, **kwargs):
        raise RuntimeError("gate unavailable")

    monkeypatch.setattr(job_integrity, "filter_listings", _boom)

    bundle, accepted, rejections = build_bundle(
        [_record()],
        operation_id="op-6",
        provider="jsearch",
        requested_role="Compliance Manager",
        requested_location="Dubai",
        started_at=_started(),
        duration_ms=100,
        status=SearchStatus.COMPLETED,
    )

    assert accepted == [], "a broken gate must not pass provider output through"
    assert not bundle.has_listings
    assert rejections.get("integrity_gate_unavailable") == 1


# ---------------------------------------------------------------------------
# The contract refuses to be widened
# ---------------------------------------------------------------------------


def test_contract_forbids_extra_fields():
    evidence = SearchExecutionEvidence(
        operation_id="op-7",
        provider="jsearch",
        requested_role="Compliance Manager",
        requested_location="Dubai",
        started_at=_started(),
        duration_ms=10,
        status=SearchStatus.EMPTY,
        raw_result_count=0,
        accepted_result_count=0,
    )

    with pytest.raises(TypeError):
        SearchExecutionEvidence(  # type: ignore[call-arg]
            operation_id="op-8",
            provider="jsearch",
            requested_role="r",
            requested_location="l",
            started_at=_started(),
            duration_ms=1,
            status=SearchStatus.EMPTY,
            raw_result_count=0,
            accepted_result_count=0,
            sneaky_extra="not allowed",
        )

    with pytest.raises(Exception):
        evidence.provider = "other"  # frozen


# ---------------------------------------------------------------------------
# Blocker 1 — a bundle with no operation identity is not evidence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_id", ["", "   "])
def test_evidence_rejects_an_empty_operation_id(bad_id):
    """An untraceable bundle claims a search happened but joins to nothing."""
    with pytest.raises(ValueError, match="operation_id"):
        SearchExecutionEvidence(
            operation_id=bad_id,
            provider="jsearch",
            requested_role="Compliance Manager",
            requested_location="Dubai",
            started_at=_started(),
            duration_ms=10,
            status=SearchStatus.EMPTY,
            raw_result_count=0,
            accepted_result_count=0,
        )


def test_build_bundle_refuses_to_produce_an_identity_less_bundle():
    with pytest.raises(ValueError, match="operation_id"):
        build_bundle(
            [],
            operation_id="",
            provider="jsearch",
            requested_role="Compliance Manager",
            requested_location="Dubai",
            started_at=_started(),
            duration_ms=10,
            status=SearchStatus.COMPLETED,
        )


# ---------------------------------------------------------------------------
# Blocker 2 — the four statuses are mutually exclusive, enforced by the type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [SearchStatus.EMPTY, SearchStatus.PROVIDER_UNAVAILABLE, SearchStatus.CANCELLED],
)
def test_non_completed_status_cannot_carry_accepted_listings(status):
    """PROVIDER_UNAVAILABLE / CANCELLED / EMPTY all mean nothing is deliverable."""
    with pytest.raises(ValueError, match="accepted_result_count == 0"):
        SearchExecutionEvidence(
            operation_id="op-x",
            provider="jsearch",
            requested_role="Compliance Manager",
            requested_location="Dubai",
            started_at=_started(),
            duration_ms=10,
            status=status,
            raw_result_count=3,
            accepted_result_count=2,
        )


def test_completed_status_cannot_be_empty():
    with pytest.raises(ValueError, match="COMPLETED requires"):
        SearchExecutionEvidence(
            operation_id="op-y",
            provider="jsearch",
            requested_role="Compliance Manager",
            requested_location="Dubai",
            started_at=_started(),
            duration_ms=10,
            status=SearchStatus.COMPLETED,
            raw_result_count=4,
            accepted_result_count=0,
        )


def test_degraded_flags_with_usable_results_resolve_to_completed():
    """A cache or fallback payload can carry a quota flag and still be usable.

    The caller observes PROVIDER_UNAVAILABLE from the flags; the service
    reconciles that against what survived rather than emitting a bundle that
    contradicts itself.
    """
    bundle, accepted, _ = build_bundle(
        [_record()],
        operation_id="op-z",
        provider="jsearch",
        requested_role="Compliance Manager",
        requested_location="Dubai",
        started_at=_started(),
        duration_ms=50,
        status=SearchStatus.PROVIDER_UNAVAILABLE,
    )

    assert bundle.execution.status is SearchStatus.COMPLETED
    assert bundle.execution.accepted_result_count == len(bundle.listings) > 0
    assert len(accepted) == len(bundle.listings)


def test_cancelled_execution_delivers_nothing_even_if_records_arrived():
    """A de-owned worker must not hand results to a user."""
    bundle, accepted, _ = build_bundle(
        [_record()],
        operation_id="op-c",
        provider="jsearch",
        requested_role="Compliance Manager",
        requested_location="Dubai",
        started_at=_started(),
        duration_ms=20,
        status=SearchStatus.CANCELLED,
    )

    assert bundle.execution.status is SearchStatus.CANCELLED
    assert bundle.listings == ()
    assert accepted == []
    assert bundle.execution.accepted_result_count == 0


def test_accepted_count_cannot_exceed_raw_count():
    with pytest.raises(ValueError):
        SearchExecutionEvidence(
            operation_id="op-9",
            provider="jsearch",
            requested_role="r",
            requested_location="l",
            started_at=_started(),
            duration_ms=1,
            status=SearchStatus.COMPLETED,
            raw_result_count=1,
            accepted_result_count=5,
        )


def test_bundle_listings_must_match_the_accepted_count():
    evidence = SearchExecutionEvidence(
        operation_id="op-10",
        provider="jsearch",
        requested_role="r",
        requested_location="l",
        started_at=_started(),
        duration_ms=1,
        status=SearchStatus.COMPLETED,
        raw_result_count=2,
        accepted_result_count=2,
    )
    with pytest.raises(ValueError):
        VerifiedJobSearchBundle(execution=evidence, listings=())


def test_listing_without_provenance_is_refused():
    with pytest.raises(ValueError):
        VerifiedJobListing(
            provider="",
            provider_job_id="x",
            title="Compliance Manager",
            company="Meridian Bank",
            location="Dubai",
            apply_url="https://example.com/1",
            source_url="https://example.com/1",
            fetched_at=_started(),
            apply_verified=True,
        )

    with pytest.raises(ValueError):
        VerifiedJobListing(
            provider="jsearch",
            provider_job_id="x",
            title="Compliance Manager",
            company="Meridian Bank",
            location="Dubai",
            apply_url="",
            source_url="",
            fetched_at=_started(),
            apply_verified=True,  # cannot be verified with no apply_url
        )
