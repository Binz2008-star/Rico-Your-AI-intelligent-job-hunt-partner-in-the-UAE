"""
src/rico_link_resolver.py
Canonical job apply-link resolver — single source of truth for "the URL a user
opens to apply".

Job payloads reach Rico in many shapes:
  - raw JSearch / RapidAPI items   (job_apply_link, job_google_link, ...)
  - normalized search-pipeline jobs (link, apply_link, alt_link)
  - persisted user_job_context rows (apply_url, source_url, alt_url)
  - cards echoed back from the frontend on an Apply click

Each uses a different field name for the apply URL. Historically every call
site re-implemented its own lookup, so a card built with `apply_url` could be
rejected by `apply_job` (which only checked `link`) with:

    "Job payload is missing required 'link' field"

This module normalizes all known aliases into one canonical link so that job
card rendering, recent-search-match storage, apply_job(), and the
"open the apply link for the Nth job" handler all agree on the same field.

Pure functions only — no DB, no network, no heavy imports. Never raises.
"""
from __future__ import annotations

from typing import Any, Mapping

# Priority-ordered link aliases. Direct apply URLs first; a job listing's
# source page next; the Google Jobs link (an intermediary *search* page, not a
# direct apply URL) ranks last but still counts as a usable last-resort link.
LINK_FIELD_ALIASES: tuple[str, ...] = (
    "link",
    "apply_url",
    "apply_link",
    "job_apply_link",
    "url",
    "job_url",
    "source_url",
    "alt_url",
    "alt_link",
    "job_google_link",
)

# Some callers wrap the real job under a nested key.
_NESTED_KEYS: tuple[str, ...] = ("job", "job_data")

# Guard against pathological self-referential payloads.
_MAX_DEPTH = 3


def _clean(value: Any) -> str:
    """Return a stripped string, or '' for any non-string / falsy value."""
    return value.strip() if isinstance(value, str) and value.strip() else ""


def is_usable_link(value: Any) -> bool:
    """True when value is a non-empty http(s) URL we can open in a browser."""
    v = _clean(value)
    return v.startswith("http://") or v.startswith("https://")


def resolve_job_link(job: Mapping[str, Any] | None, *, _depth: int = 0) -> str:
    """Return the best usable apply URL from any known alias, or "".

    Scans :data:`LINK_FIELD_ALIASES` in priority order, then descends into
    nested ``job`` / ``job_data`` payloads. A non-empty alias is returned even
    if it is not http(s) (some leads carry bare domains); callers that need a
    strictly openable URL should additionally check :func:`is_usable_link`.

    Never raises — returns "" when no alias holds a value.
    """
    if not isinstance(job, Mapping) or _depth > _MAX_DEPTH:
        return ""

    for key in LINK_FIELD_ALIASES:
        v = _clean(job.get(key))
        if v:
            return v

    for nested_key in _NESTED_KEYS:
        nested = job.get(nested_key)
        if isinstance(nested, Mapping):
            v = resolve_job_link(nested, _depth=_depth + 1)
            if v:
                return v

    return ""


def has_usable_link(job: Mapping[str, Any] | None) -> bool:
    """True when the job carries any resolvable apply link."""
    return bool(resolve_job_link(job))


def with_canonical_link(job: Mapping[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of ``job`` with a canonical ``link`` field.

    Sets ``link`` to the resolved URL so downstream engines and idempotency
    keys have a stable field to read. Never overwrites an existing ``link``
    with an empty string — a link-less job is returned unchanged (callers
    decide on the fallback CTA).
    """
    out = dict(job)
    resolved = resolve_job_link(job)
    if resolved:
        out["link"] = resolved
    return out
