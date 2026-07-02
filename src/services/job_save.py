"""Trusted save-identity + apply-link decision for persisting a job (#747 follow-up).

A user can save a job to their pipeline from many surfaces, including ones whose
job payload originates from chat ``recent_context`` / LLM output — an *untrusted*
origin under the Phase-0 job-link trust gate (``src.services.job_link_trust``).
This module decides, in one place:

* ``save_key``   — the identity the save is keyed by. Prefers a real source-backed
  identifier (``source_job_id`` / ``persisted_job_id``) so re-saving the same
  real job is idempotent. Falls back to a deterministic ``title|company`` hash.
  The bare, spoofable ``job_id`` is **never** used as the key.
* ``apply_url``  — the apply URL **only** when it passes the trust gate for the
  given origin; otherwise ``None``. A job with no trusted apply URL is still
  saveable, but callers must not claim a verified link.
* ``verified``   — convenience boolean: ``apply_url is not None``.

Pure and dependency-light: no DB, no network, never raises.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Optional

from src.services.job_link_trust import resolve_trusted_apply_url


@dataclass(frozen=True)
class SaveDecision:
    """Outcome of resolving how a job should be persisted to the pipeline."""

    save_key: str
    apply_url: Optional[str]
    verified: bool


def _trusted_source_identity(job: dict[str, Any]) -> Optional[str]:
    """Return a real source-backed identifier, or None.

    Mirrors the trusted-provenance markers in ``job_link_trust`` — the bare
    ``job_id`` is intentionally excluded because it can be synthesised by the
    LLM or copied from chat context.
    """
    for field in ("source_job_id", "persisted_job_id"):
        value = job.get(field)
        if value not in (None, "", 0):
            return f"{field}:{value}"
    return None


def _fallback_identity(job: dict[str, Any]) -> str:
    """Deterministic ``title|company`` hash so the same job de-dupes on save."""
    title = str(job.get("title") or job.get("job_title") or "").strip().lower()
    company = str(job.get("company") or job.get("company_name") or "").strip().lower()
    raw = f"{title}|{company}"
    return "tc:" + hashlib.md5(raw.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def resolve_save_decision(
    job: dict[str, Any], *, origin: Optional[str] = None
) -> SaveDecision:
    """Decide the save key and trusted apply URL for *job*.

    Parameters
    ----------
    job:
        The job dict to be saved.
    origin:
        Delivery-channel hint passed straight to the trust gate. Pass
        ``'recent_context'`` (or another value in
        ``job_link_trust.UNTRUSTED_ORIGINS``) when the payload came from chat
        context / search matches rather than the DB or ingestion pipeline.
    """
    save_key = _trusted_source_identity(job) or _fallback_identity(job)
    apply_url = resolve_trusted_apply_url(job, origin=origin)
    return SaveDecision(save_key=save_key, apply_url=apply_url, verified=apply_url is not None)
