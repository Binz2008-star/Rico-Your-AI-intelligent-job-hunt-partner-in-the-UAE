"""search_dedup.py — Deduplicate live job-search results with source provenance.

Multiple role queries against the same UAE market — and the provider cascade
itself (Jooble → Adzuna → JSearch) — routinely return the SAME posting more
than once. Before this module those duplicates reached the user as repeated
cards, wasting the five-match window and eroding trust in the result set (a
core concern of the trust-first directive: the shown set must be honest).

``dedupe_job_matches`` collapses duplicates using the SAME canonical identity
the rest of the system already uses for a job — ``src.applications.get_job_id``
(SHA of the link URL, or of ``title|company|location`` when there is no link).
That is exactly the key apply/save/skip dedup keys on, so search dedup can never
disagree with the rest of the pipeline about whether two records are "the same
job". There is no fuzzy title matching and no link rewriting: only records the
system already treats as identical are merged.

Provenance is preserved, not discarded. The first-seen record keeps its position
and all of its own fields (link, score, verification status), and the set of
providers every duplicate was seen on is merged onto it as ``sources`` (plus a
``duplicate_count``). A card can then honestly state where a posting came from
and on how many sources it appeared — broader verified-source signal without
inventing anything.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _provider_of(job: dict[str, Any]) -> str:
    """Best-effort provider/source label for a normalized job dict.

    Live provider results carry ``source`` (e.g. ``"jooble"``); DB-backed rows
    may carry ``provider``. Returns "" when neither is present so unknown
    provenance is never fabricated.
    """
    for key in ("source", "provider"):
        val = str(job.get(key) or "").strip()
        if val:
            return val
    return ""


def dedupe_job_matches(matches: Any) -> Any:
    """Collapse duplicate job postings, preserving first-seen order and provenance.

    Args:
        matches: list of normalized job dicts (the search-result window).

    Returns:
        A new list with duplicates removed. The first occurrence of each job
        survives, mutated in place to carry:

          * ``sources``          — ordered unique provider labels the posting
                                    was seen on (deduped, provenance-preserving).
          * ``duplicate_count``  — how many raw records collapsed into it (>= 1).

        Non-dict entries and records with no derivable identity are passed
        through untouched and never merged (fail-open: never drop a job we
        cannot positively prove is a duplicate).
    """
    if not isinstance(matches, list):
        return matches

    from src.applications import get_job_id

    survivors: list[Any] = []
    by_key: dict[str, dict[str, Any]] = {}
    sources_by_key: dict[str, list[str]] = {}

    for job in matches:
        if not isinstance(job, dict):
            survivors.append(job)
            continue

        try:
            key = get_job_id(job)
        except Exception:
            key = ""

        if not key:
            # No canonical identity → cannot prove it is a duplicate. Keep it.
            survivors.append(job)
            continue

        provider = _provider_of(job)

        if key in by_key:
            winner = by_key[key]
            srcs = sources_by_key[key]
            if provider and provider not in srcs:
                srcs.append(provider)
            winner["duplicate_count"] = int(winner.get("duplicate_count") or 1) + 1
            winner["sources"] = list(srcs)
            continue

        # First time we've seen this job — it wins its slot untouched except for
        # the additive provenance annotations.
        srcs = [provider] if provider else []
        by_key[key] = job
        sources_by_key[key] = srcs
        job["sources"] = list(srcs)
        job["duplicate_count"] = 1
        survivors.append(job)

    removed = len(matches) - len(survivors)
    if removed > 0:
        logger.info(
            "search_dedup collapsed %d duplicate match(es) (%d -> %d)",
            removed, len(matches), len(survivors),
        )
    return survivors
