"""Characterization tests for the chat job-search ordering path (TC-2).

These tests are **evidence, not a fix**. They pin down the *current* behavior of
the layer that actually orders chat job results so that a future fix can be made
against a measured baseline instead of a guess.

Context (2026-07-03 live QA, TC-2): an ESG / Compliance profile confirmed in
`/command` still returned Operations, Admin, ServiceNow Developer, Field Service
Engineer and HR Administrator in the top 5. The raw QA report blamed "the
scorer". Two independent characterizations show the scorer/ranker is **not** the
cause:

  1. `src/scoring.py::score_jobs_for_user` ranks relevant ESG/Compliance jobs far
     above irrelevant ones (see `test_scoring_characterization.py`). BUT that
     function is only wired into the `/jobs` REST API
     (`src/services/jobs_service.py`), **not** the chat render path.

  2. The chat render path (`RicoChatAPI._target_role_search_response`,
     `src/rico_chat_api.py`) ranks with a *different*, lighter function:
     `src/llm_scorer.py::rank_by_profile_fit`. This file characterizes that
     function — the one that actually decides the chat top-5.

Traced chat path (user message -> top-5 render):

    classify_intent (job_search_profile_match / job_search_explicit)
      -> role resolution / query builder  (search_role from profile target role)
      -> job_providers.search_jobs(search_role, location)   [candidate set]
      -> filters (applied-dedup, non-national, employment-type, title+company dedup)
      -> rank_by_profile_fit(all_matches, target_roles, skills, deal_breakers)
      -> all_matches.sort(key=_quality_key)   [fit_band + source quality + learned pref]
      -> all_matches[:5]  -> _format_match  -> render

Conclusion pinned below: when the candidate set contains relevant jobs AND the
target roles passed in are the confirmed ones, `rank_by_profile_fit` orders
correctly. TC-2 therefore reproduces only when EITHER (a) the target roles used
to build the query / score fit are stale (still Operations, not the confirmed
ESG/Compliance), OR (b) the provider candidate set contains no relevant jobs at
all (a query-generation problem). Both are upstream of scoring.
"""

from src.llm_scorer import rank_by_profile_fit


# --- Fixtures: an ESG/Compliance seeker and a realistic mixed candidate set ----

ESG_TARGET_ROLES = ["ESG Manager", "Compliance Manager", "Sustainability Manager"]
ESG_SKILLS = ["ESG", "ISO 14001", "sustainability", "compliance", "HSE", "audit"]

MIXED_CANDIDATES = [
    {"title": "ESG Manager", "company": "ADNOC", "location": "Abu Dhabi",
     "description": "sustainability ISO 14001 compliance reporting"},
    {"title": "Compliance Officer", "company": "Emirates NBD", "location": "Dubai",
     "description": "regulatory compliance audit governance"},
    {"title": "ServiceNow Developer", "company": "TechCo", "location": "Dubai",
     "description": "servicenow itsm javascript scripting"},
    {"title": "Field Service Engineer", "company": "Siemens", "location": "Dubai",
     "description": "field service mechanical maintenance"},
    {"title": "HR Administrator", "company": "Damac", "location": "Dubai",
     "description": "hr admin payroll onboarding"},
    {"title": "Operations Manager", "company": "Aramex", "location": "Dubai",
     "description": "operations logistics team management"},
]


def _fits(ranked):
    return {j["title"]: j["profile_fit_score"] for j in ranked}


# --- 1. The ranker is CORRECT when target + candidate set align -----------------

def test_ranker_floats_relevant_jobs_when_targets_match():
    """With confirmed ESG/Compliance targets and a mixed candidate set that
    includes ESG jobs, the chat-path ranker puts the relevant jobs on top.

    This is the measured proof that `rank_by_profile_fit` is NOT the TC-2 defect.
    """
    ranked = rank_by_profile_fit(
        [dict(j) for j in MIXED_CANDIDATES],
        target_roles=ESG_TARGET_ROLES,
        skills=ESG_SKILLS,
        deal_breakers=[],
    )
    fits = _fits(ranked)

    # Relevant roles score, irrelevant roles floor at 0.
    assert fits["ESG Manager"] > 0
    assert fits["Compliance Officer"] > 0
    assert fits["ServiceNow Developer"] == 0
    assert fits["Field Service Engineer"] == 0
    assert fits["HR Administrator"] == 0

    # Relevant jobs outrank every irrelevant job.
    assert fits["ESG Manager"] > fits["Operations Manager"]
    assert fits["Compliance Officer"] > fits["ServiceNow Developer"]

    # Top of the returned (already-sorted-desc) list is the ESG job.
    assert ranked[0]["title"] == "ESG Manager"


# --- 2. FAILURE MODE A: stale target roles reproduce TC-2 ------------------------

def test_stale_operations_target_floats_operations_admin():
    """If the profile still carries Operations/Admin targets (the ESG switch did
    not propagate), the ranker *faithfully* floats Operations Manager and HR
    Administrator above the ESG Manager. This reproduces the TC-2 symptom and
    localizes the bug to target-role propagation, upstream of the ranker.
    """
    stale_targets = ["Operations Manager", "Administration Manager"]
    stale_skills = ["operations", "logistics", "admin"]

    ranked = rank_by_profile_fit(
        [dict(j) for j in MIXED_CANDIDATES],
        target_roles=stale_targets,
        skills=stale_skills,
        deal_breakers=[],
    )
    fits = _fits(ranked)

    # With stale Operations targets, the ESG Manager scores 0 and Operations wins.
    assert fits["Operations Manager"] > fits["ESG Manager"]
    assert fits["Operations Manager"] > 0
    assert fits["ESG Manager"] == 0
    assert ranked[0]["title"] == "Operations Manager"


# --- 3. FAILURE MODE B: wrong candidate set collapses fit to a constant ----------

def test_no_relevant_candidates_collapse_fit_to_zero():
    """If the query was built from a stale/wrong role, the provider returns no
    relevant jobs. Every candidate then scores fit=0, so `rank_by_profile_fit`
    imposes no meaningful order and the final top-5 is decided entirely by the
    downstream `_quality_key` sort (source quality + learned preference), which
    can surface previously-preferred Operations/Admin jobs. This is a
    query-generation defect, not a scoring defect.
    """
    esg_targets = ["ESG Manager", "Compliance Manager"]
    no_esg_candidates = [
        {"title": "Operations Manager", "company": "Aramex", "location": "Dubai",
         "description": "operations logistics"},
        {"title": "HR Administrator", "company": "Damac", "location": "Dubai",
         "description": "hr admin payroll"},
        {"title": "ServiceNow Developer", "company": "TechCo", "location": "Dubai",
         "description": "servicenow itsm"},
    ]

    ranked = rank_by_profile_fit(
        [dict(j) for j in no_esg_candidates],
        target_roles=esg_targets,
        skills=["ESG", "compliance"],
        deal_breakers=[],
    )
    fits = _fits(ranked)

    # No candidate matches the ESG target -> fit collapses to a constant 0.
    assert set(fits.values()) == {0}, (
        "When the candidate set has no relevant jobs, profile-fit provides no "
        "signal; ordering is decided downstream, not by the scorer."
    )


# --- 4. Pin the wiring gap: chat path uses rank_by_profile_fit, not the scorer ---

def test_chat_ranker_is_rank_by_profile_fit_not_score_jobs_for_user():
    """Guard against silent re-wiring. `score_jobs_for_user` lives in the /jobs
    REST path; the chat render path imports `rank_by_profile_fit`. If someone
    swaps them, the two systems' relevance behavior will diverge and this pin
    should be revisited alongside the TC-2 fix.

    Reads the source file from disk instead of importing the (heavy) chat module
    so the pin runs in a bare env without the full dependency tree.
    """
    from pathlib import Path

    chat_src = (
        Path(__file__).resolve().parent.parent / "src" / "rico_chat_api.py"
    ).read_text(encoding="utf-8")

    assert "rank_by_profile_fit" in chat_src, (
        "chat render path is expected to rank with rank_by_profile_fit"
    )
    # score_jobs_for_user must NOT have leaked into the chat path (it belongs to
    # the /jobs REST service). If this trips, the two relevance systems merged.
    assert "score_jobs_for_user" not in chat_src, (
        "score_jobs_for_user appeared in the chat path; relevance wiring changed"
    )
