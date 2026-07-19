"""Relevance floor — cross-family single-token fix (2026-07-19).

Production evidence (twice in one day, morning 13:26Z and evening 16:22Z
smokes): a search for "HSE Manager" surfaced **"Head of Trading Risk" at
Bybit** as its only "match" and labeled it confidently. Root cause: the
taxonomy family expansion for HSE Manager contributes the single word
"risk", and the old floor accepted ANY one single-token title hit — so a
trading-desk role cleared an HSE floor. In the 16:22Z incident the
integrity gate honestly filtered 21 off-title provider results and the
lone survivor was the irrelevant one.

The fix is data-driven with three evidence layers (shared by the floor and
the integrity gate via job_integrity.role_text_supported):
  * phrase substring (incl. taxonomy alias phrases: "safety manager" →
    HSE Manager),
  * one STRONG single token (the requested/canonical role's OWN words),
  * or >= 2 distinct WEAK single tokens (family-expansion vocabulary).

No per-role or per-account hardcoding: everything below runs against the
real job_role_taxonomy.json.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.job_integrity import filter_listings, role_text_supported
from src.rico_chat_api import RicoChatAPI

_api = RicoChatAPI.__new__(RicoChatAPI)


def _floor_keeps(requested_role: str, title: str) -> bool:
    strong, weak, phrases = _api._requested_domain_terms(requested_role)
    return _api._job_matches_requested_domain(
        {"title": title}, strong, weak, phrases
    )


# ── THE production regression ────────────────────────────────────────────────

def test_hse_manager_floor_drops_head_of_trading_risk():
    """The Bybit case: one cross-family word ("risk") is not title evidence."""
    assert _floor_keeps("HSE Manager", "Head of Trading Risk") is False


def test_hse_manager_floor_keeps_genuinely_relevant_titles():
    """The relevant titles from the same production day must all survive."""
    for title in [
        "QHSE Manager (m/f/d)",          # phrase substring ("hse manager")
        "HSE Manager (Offshore)",         # exact phrase
        "Safety Manager",                 # taxonomy alias of HSE Manager
        "Health, Safety and Environment Manager",  # >= 2 weak family words
        "Senior HSE Engineer",            # strong own token "hse"
    ]:
        assert _floor_keeps("HSE Manager", title) is True, title


def test_risk_manager_request_still_reaches_risk_titles():
    """The same word is STRONG when the user actually asked for it."""
    assert _floor_keeps("Risk Manager", "Head of Trading Risk") is True


# ── Cross-domain collisions (synthetic, multiple unrelated roles) ────────────

def test_single_cross_family_words_are_not_evidence_for_other_roles():
    # "audit"/"compliance" appear in many families — one hit must not match.
    assert _floor_keeps("HSE Manager", "Internal Audit Director") is False
    assert _floor_keeps("Accountant", "HSE Compliance Officer") is False
    assert _floor_keeps("Environmental Manager", "Credit Risk Analyst") is False


def test_own_token_evidence_still_works_for_unrelated_roles():
    assert _floor_keeps("Accountant", "Senior Accountant") is True
    assert _floor_keeps("Environmental Manager", "Environmental Consultant") is True


# ── Arabic / degenerate inputs ───────────────────────────────────────────────

def test_arabic_only_role_yields_empty_vocabulary_and_skips_floor():
    """Arabic role text produces no Latin tokens — the caller must skip the
    floor entirely (empty sets) rather than over-filter."""
    strong, weak, phrases = _api._requested_domain_terms("محاسب")
    assert strong == set() and weak == set() and phrases == set()


def test_blank_role_yields_empty_vocabulary():
    assert _api._requested_domain_terms("") == (set(), set(), set())


def test_empty_title_never_matches():
    strong, weak, phrases = _api._requested_domain_terms("HSE Manager")
    assert _api._job_matches_requested_domain({"title": ""}, strong, weak, phrases) is False


# ── Shared rule semantics (role_text_supported) ──────────────────────────────

def test_two_distinct_weak_hits_required():
    strong, weak, phrases = set(), {"risk", "audit", "environment"}, set()
    assert role_text_supported("Risk Director", strong, phrases, weak) is False
    # Exact-token semantics (deliberate — "tax" never matches "taxi"):
    # "Environment Risk Lead" carries two distinct weak tokens.
    assert role_text_supported("Environment Risk Lead", strong, phrases, weak) is True
    assert role_text_supported("Environmental Risk Lead", strong, phrases, weak) is False


def test_legacy_callers_without_weak_set_keep_old_semantics():
    """Existing integrity-gate callers pass (singles, phrases) only — their
    curated singles still act as sufficient (strong) evidence."""
    assert role_text_supported("Sustainability Manager", {"sustainability"}, set()) is True


# ── Integrity gate consumes the same 3-layer vocabulary ──────────────────────

def _bybit_record() -> dict:
    return {
        "title": "Head of Trading Risk",
        "company": "Bybit",
        "location": "United Arab Emirates",
        "description": "Lead and grow the Trading Risk team across the organization.",
        "apply_url": "https://jooble.org/jdp/0000000000000000000",
    }


def test_integrity_gate_rejects_bybit_for_hse_with_3tuple_vocabulary():
    strong, weak, phrases = _api._requested_domain_terms("HSE Manager")
    kept, rejected = filter_listings(
        [_bybit_record()],
        requested_role="HSE Manager",
        requested_terms=(strong, weak, phrases),
        uae_only=True,
    )
    assert kept == []
    assert rejected.get("title_role_mismatch") == 1


def test_integrity_gate_keeps_relevant_record_with_3tuple_vocabulary():
    strong, weak, phrases = _api._requested_domain_terms("HSE Manager")
    rec = {
        "title": "QHSE Manager - Tier 1 Contractor",
        "company": "NSR Associates",
        "location": "Dubai, UAE",
        "description": "Own the HSE management system, audits and inspections.",
        "apply_url": "https://example.com/job/1",
    }
    kept, rejected = filter_listings(
        [rec],
        requested_role="HSE Manager",
        requested_terms=(strong, weak, phrases),
        uae_only=True,
    )
    assert len(kept) == 1
    assert rejected == {}


def test_integrity_gate_legacy_2tuple_unchanged():
    """Old callers/tests pass 2-tuples — behavior must be identical to before."""
    kept, rejected = filter_listings(
        [_bybit_record()],
        requested_role="Risk Manager",
        requested_terms=({"risk"}, set()),
        uae_only=True,
    )
    assert len(kept) == 1


# ── Alias helper (data-driven) ───────────────────────────────────────────────

def test_role_alias_phrases_maps_safety_manager_to_hse_manager():
    from src.agent.intelligence.role_classifier import role_alias_phrases
    aliases = role_alias_phrases("HSE Manager")
    assert "safety manager" in aliases
    assert "hse manager" in aliases
    assert role_alias_phrases("") == set()
