"""Canonical Career Context resolver — owner-required test categories.

Incident (2026-07-19): report said 10 years / active = docx; search silently
used Banking_CV (8 years); user_documents.is_primary disagreed with the
report's active marker; identity name held "Vip Relationship Manager";
FIVE duplicate rico_users rows shared the email.

Owner gates covered here:
  * resolver exception → SAFE degradation (neutral, never the legacy read)
  * duplicate same-email identity rows → explicit ambiguity, no leakage
  * cross-user isolation
  * 10-vs-8 conflict omission
  * null years never replaces a known value
  * user-confirmed valid name containing professional terms
  * job-title-like extracted name rejection
  * report/search provenance parity
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.services.career_context import (
    is_identity_name,
    resolve_career_context,
)

_U = "cc-user@test.com"


def _docs(*rows):
    """Patch the document source, user-scoped like the real store."""
    store = {_U: list(rows)}
    def fake_candidates(user_id):
        return list(store.get(user_id, []))
    return patch(
        "src.services.document_resolver.get_cv_candidates_strict",
        side_effect=fake_candidates,
    )


def _identity_rows(n):
    """Patch the rico_users cardinality check (None = store unavailable)."""
    return patch(
        "src.services.career_context._identity_row_count", return_value=n
    )


def _cv(name, years=None, primary=False, **kw):
    return {"doc_type": "cv", "original_filename": name,
            "years_experience": years, "is_primary": primary, **kw}


def _wire_api():
    """A RicoChatAPI shell for exercising _build_openai_context wiring."""
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI.__new__(RicoChatAPI)
    return api


# 1 ── 10 vs 8 years conflict → absolute figure omitted, both sources exposed
def test_profile_vs_primary_cv_years_conflict_omits_absolute():
    with _docs(_cv("Banking.pdf", years=8.0, primary=True)):
        cc = resolve_career_context(_U, {"years_experience": 10})
    assert cc.years_conflict is True
    assert cc.display_years is None            # never silently pick a side
    assert cc.profile_years == 10.0 and cc.cv_years == 8.0
    assert "years_conflict_profile_vs_primary_cv" in cc.notes


# 2 ── null extraction never replaces a known value
def test_null_cv_extraction_keeps_profile_years():
    with _docs(_cv("New.docx", years=None, primary=True)):
        cc = resolve_career_context(_U, {"years_experience": 10})
    assert cc.display_years == 10.0
    assert cc.years_source == "profile"
    assert cc.years_conflict is False


# 3 ── primary-CV switching is followed by the resolver
def test_primary_switch_changes_active_cv():
    with _docs(_cv("A.pdf", years=10.0, primary=True), _cv("B.pdf", years=8.0)):
        assert resolve_career_context(_U, None).active_cv["original_filename"] == "A.pdf"
    with _docs(_cv("A.pdf", years=10.0), _cv("B.pdf", years=8.0, primary=True)):
        cc = resolve_career_context(_U, None)
    assert cc.active_cv["original_filename"] == "B.pdf"
    assert cc.active_cv_source == "primary"


# 4 ── conflicting primary flags: deterministic pick + explicit flag
def test_conflicting_primary_flags_are_flagged():
    with _docs(_cv("A.pdf", primary=True), _cv("B.pdf", primary=True)):
        cc = resolve_career_context(_U, None)
    assert cc.conflicting_primary_flags is True
    assert cc.active_cv["original_filename"] == "A.pdf"  # store order, stable
    assert "multiple_primary_flags" in cc.notes


def test_no_primary_falls_back_to_latest_with_provenance():
    with _docs(_cv("Newest.docx", years=8.0)):
        cc = resolve_career_context(_U, None)
    assert cc.active_cv_source == "latest"       # labeled, never silent
    assert "no_primary_flag_latest_used" in cc.notes


# 5 ── profile-report / job-search parity: both consult THIS resolver
def test_report_and_search_share_the_same_resolver():
    import inspect
    from src import rico_chat_api
    src_text = inspect.getsource(rico_chat_api.RicoChatAPI._build_openai_context)
    search_text = inspect.getsource(rico_chat_api.RicoChatAPI._target_role_search_response)
    assert "resolve_career_context" in src_text
    assert "resolve_career_context" in search_text
    # Fail SAFE is pinned: neither caller's error path re-reads the legacy
    # years value the resolver exists to verify.
    for text in (src_text, search_text):
        assert 'years = self._profile_value(profile, "years_experience")' not in text
    # Owner audit point 3: both surfaces return the SAME career-context
    # triple (active_document_id / career_context_source / identity_state)
    # via the one shared parity_snapshot method.
    assert "parity_snapshot" in src_text
    assert "parity_snapshot" in search_text


def test_parity_snapshot_is_identical_for_both_surfaces():
    """The triple both surfaces expose comes from ONE method and carries no
    row data — an opaque id, a source label, a state label."""
    with _identity_rows(5), _docs(_cv("CV.pdf", years=8.0, primary=True, id=42)):
        cc = resolve_career_context(_U, {"years_experience": 8})
    snap = cc.parity_snapshot()
    assert snap == {
        "active_document_id": 42,
        "career_context_source": "primary",
        "identity_state": "ambiguous",
    }
    with _identity_rows(1), _docs():
        single = resolve_career_context(_U, None).parity_snapshot()
    assert single == {
        "active_document_id": None,
        "career_context_source": "none",
        "identity_state": "single",
    }


# Owner audit point 1: NO automated writer (CV parse, guest merge, profile
# API) may set the name-confirmation fields — they are reserved for an
# explicit user-confirmation flow (M3). If any writer gains these strings,
# this pin fails and forces a review.
def test_no_automated_writer_can_set_name_confirmation_fields():
    import inspect
    from src.api.routers import rico_chat as chat_router
    router_src = inspect.getsource(chat_router)
    assert "name_confirmed" not in router_src
    assert "name_source" not in router_src
    from src.services import identity_merge_service as ims
    assert "name_confirmed" not in ims.MERGEABLE_PROFILE_KEYS
    assert "name_source" not in ims.MERGEABLE_PROFILE_KEYS
    # The guest→auth merge may not move the identity name at all.
    assert "name" not in ims.MERGEABLE_PROFILE_KEYS


# 6 ── identity-name guard
def test_job_title_like_names_are_rejected():
    assert is_identity_name("Vip Relationship Manager") is False  # THE incident value
    assert is_identity_name("HSE Manager") is False
    assert is_identity_name("Roben Edwan") is True
    assert is_identity_name("") is False
    with _docs():
        cc = resolve_career_context(_U, {"name": "Vip Relationship Manager"})
    assert cc.name_is_valid_identity is False
    assert cc.name_trusted is False
    assert "identity_name_looks_like_job_title" in cc.notes
    with _docs():
        good = resolve_career_context(_U, {"name": "Roben Edwan"})
    assert good.name_is_valid_identity is True
    assert good.name_trusted is True


def test_user_confirmed_name_with_professional_terms_is_trusted():
    """A user-confirmed name is theirs even if it contains professional
    terms — the guard must not override an explicit user statement."""
    with _docs():
        cc = resolve_career_context(
            _U, {"name": "Vip Relationship Manager", "name_confirmed": True}
        )
    assert cc.name_is_valid_identity is True
    assert cc.name_trusted is True
    assert "name_user_confirmed" in cc.notes
    with _docs():
        via_source = resolve_career_context(
            _U, {"name": "HSE Manager", "name_source": "user_confirmed"}
        )
    assert via_source.name_trusted is True


# 7 ── cross-user authorization: another user's documents are invisible
def test_resolver_is_user_scoped():
    with _docs(_cv("Mine.pdf", years=8.0, primary=True)):
        other = resolve_career_context("intruder@test.com", {"years_experience": 3})
    assert other.active_cv is None
    assert other.display_years == 3.0            # only their own profile input


# 8 ── duplicate same-email identity rows → explicit ambiguity, no leakage
def test_duplicate_identity_rows_flag_ambiguity_and_omit_uncorroborated_years():
    """Two+ rico_users rows share the email: the profile row was chosen by
    get_user_bundle heuristics, so a profile-only figure is NOT displayable
    (that float is the incident) — the state is exposed instead."""
    with _identity_rows(5), _docs():
        cc = resolve_career_context(_U, {"years_experience": 10})
    assert cc.ambiguous_identity is True
    assert cc.identity_rows == 5
    assert "duplicate_identity_rows" in cc.notes
    assert cc.display_years is None              # uncorroborated → withheld
    assert "years_uncorroborated_ambiguous_identity" in cc.notes


def test_duplicate_identity_rows_corroborated_years_still_display():
    """Agreement between the profile row and the email-scoped primary CV is
    corroboration — the figure stays, with explicit provenance."""
    with _identity_rows(2), _docs(_cv("CV.pdf", years=8.0, primary=True)):
        cc = resolve_career_context(_U, {"years_experience": 8})
    assert cc.ambiguous_identity is True
    assert cc.display_years == 8.0
    assert cc.years_source == "profile_corroborated_by_primary_cv"


def test_duplicate_identity_rows_conflict_still_omits():
    with _identity_rows(5), _docs(_cv("Banking.pdf", years=8.0, primary=True)):
        cc = resolve_career_context(_U, {"years_experience": 10})
    assert cc.years_conflict is True
    assert cc.display_years is None


def test_duplicate_identity_rows_make_unconfirmed_name_untrusted():
    """The name came from an arbitrarily selected row — valid-looking is not
    enough; only user confirmation restores trust. No row's profile data
    leaks into display as verified."""
    with _identity_rows(5), _docs():
        cc = resolve_career_context(_U, {"name": "Roben Edwan"})
    assert cc.name_is_valid_identity is True     # looks like a real name
    assert cc.name_trusted is False              # but its row is ambiguous
    assert "name_provenance_ambiguous" in cc.notes
    with _identity_rows(5), _docs():
        confirmed = resolve_career_context(
            _U, {"name": "Roben Edwan", "name_confirmed": True}
        )
    assert confirmed.name_trusted is True


def test_single_identity_row_is_not_ambiguous():
    with _identity_rows(1), _docs():
        cc = resolve_career_context(_U, {"years_experience": 10, "name": "Roben Edwan"})
    assert cc.ambiguous_identity is False
    assert cc.display_years == 10.0
    assert cc.name_trusted is True


# 9 ── safe degradation: resolver trouble NEVER falls back to the legacy read
def test_document_store_failure_degrades_and_withholds_years(caplog):
    """Store down ≠ no documents: the profile figure cannot be verified, so
    the absolute number is withheld (the legacy read is what produced the
    incident — it is not a fallback). The diagnostic is sanitized: no
    email, no name, no document id, no CV content."""
    import logging
    with caplog.at_level(logging.DEBUG):
        with patch(
            "src.services.document_resolver.get_cv_candidates_strict",
            side_effect=RuntimeError("store down"),
        ):
            cc = resolve_career_context(
                _U, {"years_experience": 10, "name": "Roben Edwan"}
            )
    assert cc.degraded is True
    assert cc.display_years is None
    assert cc.years_source == "unverified"
    assert "document_store_unavailable" in cc.notes
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert _U not in logged                      # no email
    assert "@" not in logged
    assert "Roben" not in logged                 # no name
    assert "store down" not in logged            # no raw exception text


def test_wire_failure_degrades_context_to_neutral_copy():
    """If the resolver itself blows up at the wire, the context is built
    WITHOUT the unverifiable fields (absolute years, stored name) and with
    neutral guidance — not with the legacy values."""
    with patch("src.services.career_context.resolve_career_context",
               side_effect=RuntimeError("gone")):
        from src.rico_chat_api import RicoChatAPI
        api = _wire_api()
        with patch.object(RicoChatAPI, "_get_openai_agent"), \
             patch.object(RicoChatAPI, "_collect_uploaded_documents", return_value=[]), \
             patch.object(RicoChatAPI, "_get_recent_context", return_value={}):
            ctx = api._build_openai_context(
                {"name": "Roben", "years_experience": 10}, user_id=_U
            )
    assert isinstance(ctx, dict)                 # context still built
    assert "years_experience" not in ctx         # absolute years withheld
    assert "name" not in ctx                     # untrusted name withheld
    assert ctx["career_context"]["status"] == "unavailable"


def test_wire_ambiguous_identity_withholds_name_and_years():
    """End-to-end through _build_openai_context: duplicate identity rows →
    neutral context (no absolute years, no name) + explicit state."""
    from src.rico_chat_api import RicoChatAPI
    api = _wire_api()
    with _identity_rows(5), _docs(), \
         patch.object(RicoChatAPI, "_get_openai_agent"), \
         patch.object(RicoChatAPI, "_collect_uploaded_documents", return_value=[]), \
         patch.object(RicoChatAPI, "_get_recent_context", return_value={}):
        ctx = api._build_openai_context(
            {"name": "Roben Edwan", "years_experience": 10}, user_id=_U
        )
    assert ctx["career_context"]["identity_state"] == "ambiguous"
    assert "years_experience" not in ctx
    assert "name" not in ctx
    assert "years_note" in ctx["career_context"]
