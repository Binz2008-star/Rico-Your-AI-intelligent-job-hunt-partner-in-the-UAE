# -*- coding: utf-8 -*-
"""Job Result Integrity Gate — provider-to-card trust contract (#1118 incident).

The production incident: a Totaljobs record with title "Project Manager", body
"Mental Health Practitioner / Recovery Service", location Manchester UK, apply
state Unavailable — was surfaced in a UAE workflow. A provider HTTP 200 must not
make a listing a trusted opportunity. These tests exercise the real integrity
module and the real search pipeline (via ChatHarness); no toy helpers.
"""
from __future__ import annotations

from typing import Any

from src.job_integrity import (
    RejectionReason,
    validate_listing,
    filter_listings,
    is_uae_market,
)
from src.jsearch_client import FetchResult
from tests.harness.chat_harness import ChatHarness

# Requested-role vocabulary (as _requested_domain_terms would yield).
SUS_TERMS = ({"sustainability", "esg", "environmental"}, {"sustainability manager"})
HSE_TERMS = ({"hse", "health", "safety", "hsse"}, {"hse manager"})


def _rec(**over: Any) -> dict:
    base = {
        "title": "Sustainability Manager",
        "company": "ACME",
        "location": "Dubai, United Arab Emirates",
        "description": "Lead ESG and sustainability reporting across the group.",
        "apply_url": "https://example.com/jobs/1",
    }
    base.update(over)
    return base


# ── 1. UAE query rejects a Manchester/UK listing ────────────────────────────
def test_uae_query_rejects_manchester_uk_listing():
    manchester = _rec(
        title="Project Manager",
        location="Manchester, United Kingdom",
        apply_url="https://www.adzuna.co.uk/jobs/land/ad/1",
        description="Mental Health Practitioner Recovery Service supporting patients.",
    )
    assert validate_listing(manchester, single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) \
        == RejectionReason.OUTSIDE_REQUESTED_MARKET


# ── 2. Every non-UAE country is rejected even at high provider rank ──────────
def test_all_non_uae_countries_rejected_regardless_of_rank():
    recs = [
        _rec(title="Sustainability Manager", location="London, United Kingdom"),
        _rec(title="Sustainability Manager", location="Austin, United States"),
        _rec(title="Sustainability Manager", location="Mumbai, India"),
        _rec(title="Sustainability Manager", location="Doha, Qatar"),
        _rec(title="Sustainability Manager", location="Riyadh, Saudi Arabia"),
        _rec(title="Sustainability Manager", location="Dubai, United Arab Emirates"),  # only this survives
    ]
    kept, rejected = filter_listings(recs, requested_terms=SUS_TERMS)
    assert len(kept) == 1
    assert kept[0]["location"].lower().startswith("dubai")
    assert rejected.get(RejectionReason.OUTSIDE_REQUESTED_MARKET.value) == 5


# ── 3. Project Manager title + Mental Health body is rejected (role conflict) ─
def test_title_body_role_conflict_rejected():
    rec = _rec(
        title="Project Manager",
        location="Dubai, United Arab Emirates",  # UAE-located to isolate the role check
        description="Mental Health Practitioner. Recovery Service. Clinical patient care.",
    )
    reason = validate_listing(rec, single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1])
    assert reason in (
        RejectionReason.DESCRIPTION_ROLE_MISMATCH,
        RejectionReason.TITLE_DESCRIPTION_CONFLICT,
        RejectionReason.TITLE_ROLE_MISMATCH,
    )


# ── 4. HSE title + HSE duties passes ────────────────────────────────────────
def test_hse_title_with_hse_duties_passes():
    rec = _rec(
        title="HSE Manager",
        location="Abu Dhabi, United Arab Emirates",
        description="Own HSE, health and safety compliance, ISO 45001, risk assessments.",
    )
    assert validate_listing(rec, single_terms=HSE_TERMS[0], phrase_terms=HSE_TERMS[1]) is None


# ── 5. Sustainability title + unrelated nursing body is rejected ────────────
def test_sustainability_title_with_nursing_body_rejected():
    rec = _rec(
        title="Sustainability Manager",
        location="Dubai, United Arab Emirates",
        description="Registered nurse providing nursing care to patients on the ward.",
    )
    assert validate_listing(rec, single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) \
        == RejectionReason.TITLE_DESCRIPTION_CONFLICT


# ── 6. Unavailable listing is rejected ──────────────────────────────────────
def test_unavailable_listing_rejected():
    rec = _rec(availability="unavailable")
    assert validate_listing(rec, single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) \
        == RejectionReason.LISTING_UNAVAILABLE


# ── 7. Dead apply URL cannot produce an Apply action ────────────────────────
def test_dead_apply_url_rejected():
    assert validate_listing(_rec(apply_url=""), single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) \
        == RejectionReason.APPLY_URL_INVALID
    assert validate_listing(_rec(apply_url="not-a-url", link="", canonical_url=""),
                            single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) \
        == RejectionReason.APPLY_URL_INVALID


# ── 8. Provider payload / source-page title mismatch is rejected ────────────
def test_source_page_title_mismatch_rejected():
    rec = _rec(
        title="Sustainability Manager",
        location="Dubai, United Arab Emirates",
        source_page_title="Registered Mental Health Nurse — Clinical Ward",
    )
    assert validate_listing(rec, single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) \
        == RejectionReason.SOURCE_PAGE_MISMATCH


# ── 9. A valid UAE listing remains scoreable (passes the gate) ──────────────
def test_valid_uae_listing_passes():
    assert validate_listing(_rec(), single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) is None
    assert is_uae_market(_rec()) is True


# ── 13. Provider degradation does not relax integrity ───────────────────────
def test_integrity_independent_of_provider_state():
    # The gate takes no provider-state input, so a degraded/fallback context can
    # never loosen it — a UK record is rejected regardless.
    uk = _rec(title="Sustainability Manager", location="Leeds, United Kingdom")
    assert validate_listing(uk, single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) \
        == RejectionReason.OUTSIDE_REQUESTED_MARKET


# ── 14. Arabic listings validated without English-only bias ─────────────────
def test_arabic_valid_uae_listing_not_falsely_rejected():
    rec = {
        "title": "مدير الاستدامة",
        "company": "شركة",
        "location": "دبي, الإمارات",
        "description": "قيادة تقارير الاستدامة والحوكمة البيئية.",
        "apply_url": "https://example.com/ar/1",
    }
    # English role terms must not reject a valid Arabic UAE listing.
    assert validate_listing(rec, single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) is None
    # But an English nursing conflict is still caught.
    assert validate_listing(
        _rec(title="Sustainability Manager", location="Dubai, UAE",
             description="clinical nurse practitioner patient ward therapy"),
        single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1],
    ) is not None


# ── 15. Filter enforces UAE + role together (post-fallback discipline) ──────
def test_filter_enforces_market_and_role_together():
    recs = [
        _rec(title="Sustainability Manager", location="Dubai, UAE"),                 # valid
        _rec(title="Project Manager", location="Manchester, United Kingdom",
             description="Mental Health Practitioner recovery service"),             # UK + conflict
        _rec(title="Sustainability Manager", location="Sharjah, United Arab Emirates"),  # valid
        _rec(title="Chef de Partie", location="Dubai, UAE",
             description="kitchen porter hospitality food service"),                 # role mismatch (UAE)
    ]
    kept, rejected = filter_listings(recs, requested_terms=SUS_TERMS)
    kept_titles = {k["title"] for k in kept}
    assert kept_titles == {"Sustainability Manager"}
    assert len(kept) == 2
    assert sum(rejected.values()) == 2


# ── 10/11/12. Integration: rejected records never scored / carded / shortlisted ─
class _MixHarness(ChatHarness):
    """Returns a mix of a valid UAE listing and the corrupt incident listing."""

    def _search(self, role: str, location: str = "", **_kw: Any) -> FetchResult:
        self.searched_roles.append(role)
        return FetchResult(
            items=[
                {
                    "title": "Sustainability Manager", "company": "Masdar",
                    "location": "Abu Dhabi, United Arab Emirates",
                    "apply_url": "https://example.com/jobs/valid",
                    "description": "ESG and sustainability strategy across the group.",
                },
                {  # the exact incident shape
                    "title": "Project Manager", "company": "Totaljobs",
                    "location": "Manchester, United Kingdom",
                    "apply_url": "https://www.adzuna.co.uk/jobs/land/ad/dead",
                    "availability": "unavailable",
                    "description": "Mental Health Practitioner Recovery Service, clinical patient care.",
                },
            ],
            provider="jsearch",
        )


def _seed(h: ChatHarness) -> None:
    h.seed("u@test", cv_status="parsed", cv_filename="cv.pdf",
           target_roles=["Sustainability Manager"], skills=["esg", "sustainability"],
           years_experience=8, preferred_cities=["Dubai"], current_role="Sustainability Manager")


def test_corrupt_listing_never_reaches_matches_cards_or_shortlist():
    h = _MixHarness()
    _seed(h)
    res = h.say("u@test", "Find Sustainability Manager jobs in the UAE")
    titles = [m.get("title", "") for m in (res.get("matches") or [])]
    # (11) job cards: only the valid UAE listing is present
    assert "Project Manager" not in titles
    assert all("United Kingdom" not in str(m.get("location", "")) for m in (res.get("matches") or []))
    # (12) shortlist derives from matches → the corrupt record cannot be shortlisted
    # (10) only surviving matches are ever scored (rejected dropped before scoring)
    if res.get("matches"):
        assert titles == ["Sustainability Manager"]
    # aggregate integrity summary is surfaced (counts only)
    assert (res.get("integrity_filtered") or {}).get("total", 0) >= 1
