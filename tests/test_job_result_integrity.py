# -*- coding: utf-8 -*-
"""Job Result Integrity Gate — provider-to-card trust contract (incident #1121).

The production incident (#1121): a Totaljobs record with title "Project Manager",
body "Mental Health Practitioner / Recovery Service", location Manchester UK,
apply state Unavailable — was surfaced in a UAE workflow. A provider HTTP 200 must
not make a listing a trusted opportunity. These tests exercise the real integrity
module and the real search pipeline (via ChatHarness); no toy helpers.
"""
from __future__ import annotations

import json
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


# ── 7. Dead (malformed) apply URL cannot produce an Apply action ────────────
def test_malformed_apply_url_rejected_missing_allowed_unverified():
    # A present-but-malformed URL is a hard rejection (no Apply action possible).
    assert validate_listing(_rec(apply_url="not-a-url"),
                            single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) \
        == RejectionReason.APPLY_URL_INVALID
    # A MISSING url is allowed (marked unverified downstream; still no Apply
    # action) per the "usable OR marked unverified" contract — not over-rejected.
    assert validate_listing(_rec(apply_url=""),
                            single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) is None


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
    matches = res.get("matches") or []
    titles = [m.get("title", "") for m in matches]
    # (11) job cards: only the valid UAE listing is present
    assert "Project Manager" not in titles
    assert all("United Kingdom" not in str(m.get("location", "")) for m in matches)
    # (12) shortlist derives from matches → the corrupt record cannot be shortlisted
    # (10) only surviving matches are ever scored (rejected dropped before scoring)
    if matches:
        assert titles == ["Sustainability Manager"]
    # No card carries ANY field derived from the corrupt record: not a score, a
    # why-it-fits line, an honest-gaps line, a match card, or an action control.
    blob = json.dumps(res, ensure_ascii=False)
    assert "Project Manager" not in blob
    assert "Mental Health" not in blob
    assert "Recovery Service" not in blob
    # The surviving valid card WAS fully scored/explained (proves the pipeline ran
    # end-to-end and rejection happened before scoring, not by skipping scoring).
    if matches:
        card = matches[0]
        assert "score" in card and "why_this_fits" in card and "actions" in card
        assert card.get("apply_verified") is True  # valid URL → actionable
    # aggregate integrity summary is surfaced (counts only)
    assert (res.get("integrity_filtered") or {}).get("total", 0) >= 1


class _MissingUrlHarness(ChatHarness):
    """A valid UAE listing whose apply URL has not been enriched yet (missing)."""

    def _search(self, role: str, location: str = "", **_kw: Any) -> FetchResult:
        self.searched_roles.append(role)
        return FetchResult(
            items=[{
                "title": "Sustainability Manager", "company": "Masdar",
                "location": "Abu Dhabi, United Arab Emirates",
                "description": "ESG and sustainability strategy across the group.",
                # no apply_url / link at all
            }],
            provider="jsearch",
        )


def test_missing_url_card_is_unverified_and_offers_no_apply():
    h = _MissingUrlHarness()
    _seed(h)
    res = h.say("u@test", "Find Sustainability Manager jobs in the UAE")
    matches = res.get("matches") or []
    if matches:  # accepted (missing URL is allowed) but must be unverified
        card = matches[0]
        assert card.get("apply_verified") is False
        assert card.get("link_unavailable") is True
        assert not card.get("usable_link")


# ═══════════════════════════════════════════════════════════════════════════════
# Protected-domain review fix (#1123 thread): the requested role's OWN domain
# must participate — a valid protected-domain request must not be mis-flagged.
# ═══════════════════════════════════════════════════════════════════════════════
NURSE_TERMS = ({"nurse", "staff"}, {"staff nurse"})
MHP_TERMS = ({"mental", "health", "practitioner"}, {"mental health practitioner"})
PM_TERMS = ({"project"}, {"project manager"})
RN_TERMS = ({"registered", "nurse"}, {"registered nurse"})


def test_pd1_requested_nurse_nursing_body_accepted():
    rec = _rec(title="Staff Nurse", location="Dubai, UAE",
               description="Provide nursing and patient care duties on the ward.")
    assert validate_listing(rec, single_terms=NURSE_TERMS[0], phrase_terms=NURSE_TERMS[1]) is None


def test_pd2_requested_mental_health_practitioner_accepted():
    rec = _rec(title="Mental Health Practitioner", location="Abu Dhabi, UAE",
               description="Mental health recovery service; clinical patient support.")
    assert validate_listing(rec, single_terms=MHP_TERMS[0], phrase_terms=MHP_TERMS[1]) is None


def test_pd3_project_manager_title_mental_health_body_rejected():
    rec = _rec(title="Project Manager", location="Dubai, UAE",
               description="Mental Health Practitioner / Recovery Service. Clinical patient care.")
    assert validate_listing(rec, single_terms=PM_TERMS[0], phrase_terms=PM_TERMS[1]) \
        == RejectionReason.TITLE_DESCRIPTION_CONFLICT


def test_pd5_healthcare_request_generic_manager_title_not_accepted():
    rec = _rec(title="Operations Manager", location="Dubai, UAE",
               description="Deliver nursing care for patients on the ward; clinical duties.")
    # Requested a nurse; title is a generic manager that does not confirm the role.
    assert validate_listing(rec, single_terms=RN_TERMS[0], phrase_terms=RN_TERMS[1]) is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Arabic role integrity — validated with Arabic vocabulary, never skipped, never
# requiring English words; insufficient evidence is not silently trusted.
# ═══════════════════════════════════════════════════════════════════════════════
def test_ar_a_hse_title_hse_body_accepted():
    rec = {
        "title": "مدير الصحة والسلامة والبيئة",
        "location": "دبي, الإمارات",
        "description": "قيادة أنظمة الصحة والسلامة والبيئة وتقييم المخاطر والامتثال.",
        "apply_url": "https://example.com/ar/hse",
    }
    assert validate_listing(rec, single_terms=HSE_TERMS[0], phrase_terms=HSE_TERMS[1]) is None


def test_ar_b_sustainability_title_nursing_body_rejected():
    rec = {
        "title": "مدير الاستدامة",
        "location": "دبي, الإمارات",
        "description": "تقديم الرعاية التمريضية للمرضى في العيادة والمستشفى.",
        "apply_url": "https://example.com/ar/sus",
    }
    assert validate_listing(rec, single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) \
        == RejectionReason.TITLE_DESCRIPTION_CONFLICT


def test_ar_c_arabic_listing_non_uae_location_rejected():
    rec = {
        "title": "مدير الاستدامة",
        "location": "لندن, المملكة المتحدة",
        "description": "قيادة الاستدامة والحوكمة البيئية.",
        "apply_url": "https://example.com/ar/uk",
    }
    assert validate_listing(rec, single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) \
        == RejectionReason.OUTSIDE_REQUESTED_MARKET


def test_ar_d_mixed_arabic_english_valid_uae_accepted():
    rec = {
        "title": "Sustainability Manager مدير الاستدامة",
        "location": "Dubai, الإمارات",
        "description": "Lead ESG and قيادة تقارير الاستدامة across the group.",
        "apply_url": "https://example.com/mixed",
    }
    assert validate_listing(rec, single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) is None


def test_ar_e_insufficient_evidence_rejected():
    rec = {
        "title": "و",           # single Arabic letter — no role signal
        "location": "دبي, الإمارات",
        "description": "",
        "apply_url": "https://example.com/x",
    }
    assert validate_listing(rec, single_terms=SUS_TERMS[0], phrase_terms=SUS_TERMS[1]) \
        == RejectionReason.INSUFFICIENT_LISTING_EVIDENCE


# ═══════════════════════════════════════════════════════════════════════════════
# Apply-URL contract: valid→actionable(apply_verified); missing→unverified/no-apply;
# malformed→reject; unavailable→reject.
# ═══════════════════════════════════════════════════════════════════════════════
def test_applyurl_valid_is_verified_missing_is_unverified():
    valid = _rec(apply_url="https://example.com/jobs/9")
    missing = _rec(apply_url="")
    kept, rejected = filter_listings([valid, missing], requested_terms=SUS_TERMS)
    assert len(kept) == 2 and not rejected
    by_url = {bool(k.get("apply_url")): k for k in kept}
    assert by_url[True]["apply_verified"] is True        # valid URL → actionable
    assert by_url[False]["apply_verified"] is False       # missing URL → unverified, no Apply


def test_applyurl_malformed_rejected():
    kept, rejected = filter_listings([_rec(apply_url="not-a-url")], requested_terms=SUS_TERMS)
    assert kept == [] and rejected.get(RejectionReason.APPLY_URL_INVALID.value) == 1


def test_applyurl_unavailable_rejected():
    kept, rejected = filter_listings([_rec(availability="expired")], requested_terms=SUS_TERMS)
    assert kept == [] and rejected.get(RejectionReason.LISTING_UNAVAILABLE.value) == 1
