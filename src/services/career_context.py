"""Canonical Career Context — one legal resolver for active-CV provenance.

Production incident (2026-07-19): the profile report said "10 years, active
CV = Roben Edwan CV.docx" while the job search silently said "~8 years" from
Banking_CV.pdf. Investigation mapped the divergence to multiple sources
answering independently:

  * FIVE duplicate rico_users rows share this identity's email; canonical
    bundle selection (rico_db.get_user_bundle) prefers the most recently
    UPDATED row, so any CV upload floats the whole identity onto whichever
    duplicate row the parse touched last (name became the CV title line
    "Vip Relationship Manager", years became 8.0).
  * user_documents is EMAIL-scoped (shared) while rico_profiles is
    row-scoped (fragmented) — is_primary and the report's "active" marker
    can disagree by construction.

Architecture boundary (owner ruling 2026-07-19):
  * user_documents.is_primary is the ACTIVE-DOCUMENT selector — which CV
    is in force. It is NOT a canonical user-identity source; nothing here
    treats it as one.
  * A matching email is NOT sufficient proof of a single identity: when
    more than one rico_users row matches the authenticated identifier, the
    identity is AMBIGUOUS and this resolver says so explicitly instead of
    silently trusting whichever row get_user_bundle floated to.
  * M1 (this module) is a READ-PATH CONSISTENCY MITIGATION only. M2
    resolves the duplicate identity/data rows themselves (owner-gated,
    touches production data). M3 hardens all writers (CV parse must stop
    writing title lines into identity names, etc.). See
    AI_WORKSPACE/CAREER_CONTEXT_PROGRAM.md.

This module is the READ-side resolver both the profile report and the job
search must consult. It performs NO writes: it never overwrites
rico_profiles from CV extraction, never replaces a known value with null,
and never mutates documents.

Degradation contract (fail SAFE, not fail soft): when resolution cannot be
completed (document store error, unexpected failure), the resolver reports
degraded=True and withholds absolute figures rather than letting callers
fall back to the legacy read that produced the incident. Callers must then
use neutral copy — no absolute years, no unverified name — and log a
sanitized diagnostic (exception type only; never user data).

Rules implemented here:
  * ONE legal active-CV pointer: user_documents.is_primary (doc_type=cv),
    via document_resolver; a latest-CV fallback is exposed WITH provenance
    ("latest", never silently equated to primary).
  * Years provenance: profile value and primary-CV value are both carried;
    on conflict the absolute figure is OMITTED from display (display_years
    is None) and the conflict is exposed so surfaces can ask the user.
  * Ambiguous identity: with duplicate rico_users rows, a profile-sourced
    figure is displayable only when the email-scoped primary CV
    corroborates it; the profile-row name is untrusted unless the user
    confirmed it.
  * Identity-name guard: a name that resolves to a job title (taxonomy) or
    is dominated by role vocabulary is flagged invalid and never displayed
    as the user's name — unless the user explicitly confirmed it
    (profile name_confirmed / name_source="user").
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Conflicting sources must differ by at least this much before we suppress
# the absolute figure (a 10 vs 10.0 or 10 vs 10.4 mismatch is not a conflict).
_YEARS_CONFLICT_THRESHOLD = 1.0


@dataclass
class CareerContext:
    """Read-only resolved career context with explicit provenance."""

    active_cv: Optional[dict] = None
    active_cv_source: str = "none"  # "primary" | "latest" | "none"
    conflicting_primary_flags: bool = False

    profile_years: Optional[float] = None
    cv_years: Optional[float] = None
    years_conflict: bool = False
    # The value surfaces may show as an absolute figure; None when conflicted,
    # degraded, or uncorroborated under an ambiguous identity (callers omit
    # the number or ask for confirmation — never guess).
    display_years: Optional[float] = None
    years_source: str = "none"  # "profile" | "primary_cv" | "profile_corroborated_by_primary_cv" | "unverified" | "none"

    name_value: Optional[str] = None
    name_is_valid_identity: bool = True
    # The single yes/no callers use: display this name at all?
    # False when the name looks like a job title (and is not user-confirmed),
    # when the identity is ambiguous without user confirmation, or when
    # resolution degraded before the name could be evaluated.
    name_trusted: bool = False

    # >1 rico_users rows matched the authenticated identifier (None = store
    # unavailable, cardinality unknown — NOT the same as 1).
    identity_rows: Optional[int] = None
    ambiguous_identity: bool = False

    # Resolution could not be completed — callers must degrade to neutral
    # copy (no absolute years, no unverified name), never to the legacy read.
    degraded: bool = False

    notes: list = field(default_factory=list)

    def parity_snapshot(self) -> dict:
        """The identical career-context triple BOTH surfaces must return.

        Defined ONCE here so the profile report and the job search cannot
        diverge in what they claim about the active document or the
        identity state. Exposes NO row data — an opaque document id, a
        source label, and a state label only.
        """
        if self.degraded:
            state = "unverified"
        elif self.ambiguous_identity:
            state = "ambiguous"
        elif self.identity_rows is None:
            state = "unknown"
        else:
            state = "single"
        return {
            "active_document_id": (self.active_cv or {}).get("id"),
            "career_context_source": self.active_cv_source,
            "identity_state": state,
        }


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _profile_get(profile: Any, key: str) -> Any:
    if profile is None:
        return None
    if isinstance(profile, dict):
        return profile.get(key)
    return getattr(profile, key, None)


def _identity_row_count(user_id: str) -> Optional[int]:
    """READ-ONLY rico_users cardinality for the authenticated identifier.

    None = unknown (store unavailable/unconfigured); never raises.
    """
    try:
        from src.rico_db import RicoDB
        return RicoDB().count_identity_rows(user_id)
    except Exception as exc:
        logger.warning(
            "career_context: identity cardinality check failed (%s)",
            type(exc).__name__,
        )
        return None


def is_identity_name(name: Any) -> bool:
    """True when *name* looks like a person's name, not a job title.

    A CV parse writing a title line ("Vip Relationship Manager") into the
    identity-name field must be caught here. Data-driven: the taxonomy
    resolver recognises role-like strings, and role vocabulary tokens
    (manager/officer/engineer/...) come from the scorer's generic-token set.
    """
    text = str(name or "").strip()
    if not text:
        return False
    try:
        from src.agent.intelligence.role_classifier import resolve_taxonomy_role
        if resolve_taxonomy_role(text):
            return False
    except Exception:
        pass
    try:
        from src.llm_scorer import _GENERIC_ROLE_TOKENS, _TOKEN_RE
        tokens = [t for t in _TOKEN_RE.findall(text.lower()) if t]
        if tokens:
            role_hits = sum(1 for t in tokens if t in _GENERIC_ROLE_TOKENS)
            # A real name has at most an incidental role word; a title line is
            # dominated by them ("vip RELATIONSHIP MANAGER" → 1/3+ generics).
            if role_hits and role_hits * 2 >= len(tokens):
                return False
    except Exception:
        pass
    return True


def _name_user_confirmed(profile: Any) -> bool:
    """True when the user explicitly confirmed the stored name as theirs.

    Read-path support for the M3 writer contract: a user-confirmed name is
    trusted even when it contains professional terms (real names can), and
    even under an ambiguous identity. Nothing writes these fields yet in
    production — CV extraction must never set them (writer hardening is M3).
    """
    if bool(_profile_get(profile, "name_confirmed")):
        return True
    source = str(_profile_get(profile, "name_source") or "").strip().lower()
    return source in {"user", "user_confirmed"}


def resolve_career_context(user_id: str, profile: Any = None) -> CareerContext:
    """Resolve the canonical career context for *user_id*. Never raises.

    *user_id* must be the AUTHENTICATED identifier (JWT subject), never a
    request-body value. READ-ONLY: consults the profile object handed in
    (never re-fetches or rewrites it) and user_documents via
    document_resolver. This is the ONE resolver both the profile report and
    the job search consult, so their answers can never diverge again.

    On failure the context comes back degraded (absolute figures withheld,
    name untrusted) — callers must show neutral copy, NOT fall back to the
    legacy read.
    """
    ctx = CareerContext()
    try:
        # ── Identity cardinality: matching email is NOT sufficient proof of
        # a single identity. Duplicate rows mean the profile row was chosen
        # by get_user_bundle heuristics — say so explicitly. ───────────────
        ctx.identity_rows = _identity_row_count(user_id)
        if ctx.identity_rows is not None and ctx.identity_rows > 1:
            ctx.ambiguous_identity = True
            ctx.notes.append("duplicate_identity_rows")

        # ── Active CV: the legal ACTIVE-DOCUMENT pointer is is_primary
        # (not an identity source); latest is a labeled fallback, never a
        # silent substitute. Store failure ≠ no documents: it degrades. ────
        try:
            from src.services.document_resolver import get_cv_candidates_strict
            candidates = [
                d for d in get_cv_candidates_strict(user_id) if isinstance(d, dict)
            ]
        except Exception as exc:
            logger.warning(
                "career_context: document store unavailable (%s); degrading",
                type(exc).__name__,
            )
            ctx.degraded = True
            ctx.notes.append("document_store_unavailable")
            candidates = []
        primaries = [d for d in candidates if d.get("is_primary")]
        if len(primaries) > 1:
            ctx.conflicting_primary_flags = True
            ctx.notes.append("multiple_primary_flags")
        if primaries:
            ctx.active_cv = primaries[0]
            ctx.active_cv_source = "primary"
        elif candidates:
            ctx.active_cv = candidates[0]
            ctx.active_cv_source = "latest"
            ctx.notes.append("no_primary_flag_latest_used")

        # ── Years with provenance; conflict suppresses the absolute figure.
        ctx.profile_years = _as_float(_profile_get(profile, "years_experience"))
        ctx.cv_years = _as_float((ctx.active_cv or {}).get("years_experience"))
        if ctx.profile_years is not None and ctx.cv_years is not None:
            if abs(ctx.profile_years - ctx.cv_years) >= _YEARS_CONFLICT_THRESHOLD:
                ctx.years_conflict = True
                ctx.display_years = None
                ctx.years_source = "none"
                ctx.notes.append("years_conflict_profile_vs_primary_cv")
            else:
                ctx.display_years = ctx.profile_years
                ctx.years_source = "profile"
        elif ctx.profile_years is not None:
            # Never replace a known value with null: an active CV whose parse
            # extracted no years keeps the profile figure.
            ctx.display_years = ctx.profile_years
            ctx.years_source = "profile"
        elif ctx.cv_years is not None:
            ctx.display_years = ctx.cv_years
            ctx.years_source = "primary_cv"
            ctx.notes.append("years_from_primary_cv_only")

        # Ambiguous identity: the profile row was arbitrarily selected among
        # duplicates, so a profile-sourced figure is displayable only when
        # the email-scoped primary CV corroborates it. A CV-only figure
        # stays: the primary slot is a single email-scoped anchor.
        if ctx.ambiguous_identity and not ctx.years_conflict:
            if ctx.profile_years is not None and ctx.cv_years is not None:
                ctx.years_source = "profile_corroborated_by_primary_cv"
            elif ctx.profile_years is not None:
                ctx.display_years = None
                ctx.years_source = "none"
                ctx.notes.append("years_uncorroborated_ambiguous_identity")

        # Degraded resolution: CV-side values could not be read, so nothing
        # can be verified — withhold the absolute figure entirely.
        if ctx.degraded:
            ctx.display_years = None
            ctx.years_source = "unverified"
            ctx.notes.append("years_unverified_resolver_degraded")

        # ── Identity-name guard. ───────────────────────────────────────────
        raw_name = _profile_get(profile, "name")
        ctx.name_value = str(raw_name).strip() if raw_name else None
        if ctx.name_value is not None:
            confirmed = _name_user_confirmed(profile)
            if confirmed:
                ctx.name_is_valid_identity = True
                ctx.notes.append("name_user_confirmed")
            else:
                ctx.name_is_valid_identity = is_identity_name(ctx.name_value)
                if not ctx.name_is_valid_identity:
                    ctx.notes.append("identity_name_looks_like_job_title")
            # Trust requires validity AND either user confirmation or an
            # unambiguous identity (the row the name came from is certain).
            ctx.name_trusted = ctx.name_is_valid_identity and (
                confirmed or not ctx.ambiguous_identity
            )
            if ctx.name_value and not ctx.name_trusted and ctx.name_is_valid_identity:
                ctx.notes.append("name_provenance_ambiguous")
    except Exception as exc:
        # Sanitized diagnostic: exception type only — never user data.
        logger.warning(
            "career_context: resolution failed (%s); degrading to neutral",
            type(exc).__name__,
        )
        ctx.degraded = True
        ctx.display_years = None
        ctx.years_source = "unverified"
        ctx.name_trusted = False
        if "resolver_error" not in ctx.notes:
            ctx.notes.append("resolver_error")
    return ctx
