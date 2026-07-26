"""Build a verified job-search bundle from one provider execution.

This is the seam. Before it, records are whatever a provider returned. After
it, the only job values in play are :class:`~src.domain.job_search.VerifiedJobListing`
instances inside a :class:`~src.domain.job_search.VerifiedJobSearchBundle`, and
the accepted record dictionaries that correspond to them one-for-one.

It exists outside ``src/rico_chat_api.py`` on purpose. The chat module already
holds eleven builders that emit ``job_matches``; adding a twelfth rule inside it
would put the trust decision back in the same place the problem lives. A caller
adopts this service by replacing its inline integrity block with one call — the
integrity gate moves here rather than being duplicated.

The integrity gate runs **exactly once**, here, before the bundle is created. A
caller therefore cannot see raw provider items through this path: by the time it
holds anything, the untrustworthy records are already gone and the counts that
prove it are in the evidence.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.domain.job_search import (
    SearchExecutionEvidence,
    SearchStatus,
    VerifiedJobListing,
    VerifiedJobSearchBundle,
)

logger = logging.getLogger(__name__)

# Read in order; the first non-empty value wins. These are the keys the
# provider adapters and the integrity gate already agree on — this service
# reads them, it does not introduce new ones.
_APPLY_URL_KEYS = ("apply_url", "apply_link", "link", "url", "canonical_url")
_SOURCE_URL_KEYS = ("source_url", "canonical_url", "link", "url")
_JOB_ID_KEYS = ("provider_job_id", "job_id", "source_job_id", "id")


def _first(record: Dict[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _provider_job_id(record: Dict[str, Any], apply_url: str) -> str:
    """A stable identifier at the source.

    Falls back to the project's canonical job id so a provider that omits its
    own identifier still yields an identifiable listing rather than being
    dropped — the identity is derived from the link, which is exactly what the
    rest of the system already keys on.
    """
    explicit = _first(record, _JOB_ID_KEYS)
    if explicit:
        return explicit
    try:
        from src.applications import get_job_id

        derived = get_job_id({**record, "link": apply_url or record.get("link", "")})
        if derived:
            return derived
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("provider_job_id derivation unavailable: %s", type(exc).__name__)
    return ""


def _to_listing(
    record: Dict[str, Any], *, provider: str, fetched_at: datetime
) -> Optional[VerifiedJobListing]:
    """Project one accepted record onto the contract, or None if it cannot be.

    A record that survived the integrity gate but still cannot produce an
    identifiable, sourced listing is dropped rather than forced through. Being
    unable to describe a job's provenance is precisely the condition under which
    it must not be named.
    """
    apply_url = _first(record, _APPLY_URL_KEYS)
    source_url = _first(record, _SOURCE_URL_KEYS) or apply_url
    try:
        return VerifiedJobListing(
            provider=(record.get("source") or record.get("provider") or provider or "").strip(),
            provider_job_id=_provider_job_id(record, apply_url),
            title=(record.get("title") or "").strip(),
            company=(record.get("company") or "").strip(),
            location=(record.get("location") or "").strip(),
            apply_url=apply_url,
            source_url=source_url,
            fetched_at=fetched_at,
            apply_verified=bool(record.get("apply_verified")) and bool(apply_url),
        )
    except (ValueError, TypeError) as exc:
        logger.info(
            "verified_listing_rejected reason=%s title_len=%d",
            type(exc).__name__,
            len(str(record.get("title") or "")),
        )
        return None


def build_bundle(
    raw_items: Iterable[Dict[str, Any]],
    *,
    operation_id: str,
    provider: str,
    requested_role: str,
    requested_location: str,
    started_at: datetime,
    duration_ms: int,
    status: SearchStatus,
    requested_terms: Optional[tuple] = None,
    uae_only: bool = True,
) -> Tuple[VerifiedJobSearchBundle, List[Dict[str, Any]], Dict[str, int]]:
    """Run the integrity gate once, then build the bundle.

    Returns ``(bundle, accepted_records, integrity_rejections)``.

    ``accepted_records`` are the surviving provider dictionaries, index-aligned
    with ``bundle.listings``, so an existing caller can keep its downstream
    scoring and formatting unchanged while the bundle carries the provenance.
    They are the accepted subset only — a caller never receives raw items from
    this function.

    ``status`` is what the caller observed about the execution. It is corrected
    down to ``EMPTY`` when nothing survived, because a search that accepted no
    listing did not complete in any sense the user would recognise.
    """
    records = [r for r in (raw_items or []) if isinstance(r, dict)]
    raw_count = len(records)
    rejections: Dict[str, int] = {}

    if records:
        try:
            from src.job_integrity import filter_listings

            records, rejections = filter_listings(
                records,
                requested_role=requested_role,
                requested_terms=requested_terms,
                uae_only=uae_only,
            )
            if rejections:
                logger.info(
                    "job_integrity_gate role=%r kept=%d/%d rejected=%s op=%s",
                    requested_role, len(records), raw_count, rejections, operation_id,
                )
        except Exception as exc:
            # Fail closed. The gate is the trust decision; if it cannot run we
            # accept nothing rather than passing unfiltered provider output to
            # a surface that will name companies from it.
            logger.warning(
                "job_integrity_gate_error role=%r err=%s — failing closed",
                requested_role, type(exc).__name__,
            )
            records = []
            rejections = {"integrity_gate_unavailable": raw_count}

    fetched_at = datetime.now(timezone.utc)
    listings: List[VerifiedJobListing] = []
    accepted: List[Dict[str, Any]] = []
    for record in records:
        listing = _to_listing(record, provider=provider, fetched_at=fetched_at)
        if listing is None:
            rejections["unverifiable_provenance"] = rejections.get("unverifiable_provenance", 0) + 1
            continue
        listings.append(listing)
        accepted.append(record)

    effective_status = status
    if status is SearchStatus.COMPLETED and not listings:
        effective_status = SearchStatus.EMPTY

    evidence = SearchExecutionEvidence(
        operation_id=operation_id,
        provider=provider or "none",
        requested_role=requested_role,
        requested_location=requested_location,
        started_at=started_at,
        duration_ms=max(0, int(duration_ms)),
        status=effective_status,
        raw_result_count=raw_count,
        accepted_result_count=len(listings),
    )
    bundle = VerifiedJobSearchBundle(execution=evidence, listings=tuple(listings))
    return bundle, accepted, rejections


__all__ = ["build_bundle"]
