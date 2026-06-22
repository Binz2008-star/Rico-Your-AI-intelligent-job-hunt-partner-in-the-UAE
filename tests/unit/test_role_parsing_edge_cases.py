# -*- coding: utf-8 -*-
"""
PR D regression — remaining role-parsing edge cases (Production Tests 2,3,5,6).

T2: "Search UAE jobs for Technical Product Owner only" — strip trailing qualifiers.
T3: "Search UAE jobs for HSE Manager and QHSE Manager" — recognise BOTH roles.
T5: "Find jobs based on my CV, but do not search Software Engineer, …" — preserve
    exclusions with zero positive roles; never suggest excluded roles.
T6: "I want product and technical management jobs, not coding jobs" — map the
    descriptive category to allowed roles + exclude coding roles.

Mocks/fixtures only — 0 external provider calls.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agent.intelligence.intent_classifier import (
    classify_intent, extract_role_list, _strip_role_qualifiers,
)
from src.rico_chat_api import RicoChatAPI


_ALLOWED = [
    "Technical Product Owner", "Product Owner", "Technical Project Manager",
    "Digital Transformation Manager", "Operations Technology Manager",
]
_CODING = ["Software Engineer", "Full Stack", "Backend", "Golang", "Machine Learning"]


# ── T2: trailing qualifier strip ──────────────────────────────────────────────

@pytest.mark.parametrize("msg,expected", [
    ("Search UAE jobs for Technical Product Owner only", "Technical Product Owner"),
    ("find Operations Manager jobs please", "Operations Manager"),
    ("find HSE Manager jobs now", "HSE Manager"),
])
def test_t2_trailing_qualifier_stripped(msg, expected):
    r = classify_intent(msg, has_cv_profile=True)
    assert r.legacy_intent == "job_search_explicit"
    assert r.extracted_role == expected


def test_strip_role_qualifiers_helper():
    assert _strip_role_qualifiers("Technical Product Owner only") == "Technical Product Owner"
    assert _strip_role_qualifiers("Accountant please now") == "Accountant"
    assert _strip_role_qualifiers("HSE Manager") == "HSE Manager"


# ── T3: "jobs for A and B" multi-role ─────────────────────────────────────────

def test_t3_two_roles_recognised():
    r = classify_intent("Search UAE jobs for HSE Manager and QHSE Manager", has_cv_profile=True)
    assert r.legacy_intent == "job_search_multi_role"
    assert (r.entities or {}).get("roles") == ["HSE Manager", "QHSE Manager"]


def test_t3_extract_role_list_jobs_for():
    roles, _ = extract_role_list("Search UAE jobs for HSE Manager and QHSE Manager")
    assert roles == ["HSE Manager", "QHSE Manager"]


def test_t4_comma_list_still_works():
    """The existing comma-list path (#723) must be unaffected."""
    r = classify_intent(
        "Search for Technical Product Owner, Product Owner, and Technical Project Manager roles in UAE",
        has_cv_profile=True,
    )
    assert r.legacy_intent == "job_search_multi_role"
    assert (r.entities or {}).get("roles") == [
        "Technical Product Owner", "Product Owner", "Technical Project Manager",
    ]


# ── T5: CV-based search + exclusions ──────────────────────────────────────────

def test_t5_cv_with_exclusions_routes_to_profile_match():
    r = classify_intent(
        "Find jobs based on my CV, but do not search Software Engineer, Full Stack, "
        "Backend, Golang, or Machine Learning roles",
        has_cv_profile=True,
    )
    assert r.legacy_intent == "job_search_profile_match"
    assert (r.entities or {}).get("excluded_roles") == _CODING


def test_t5_filter_excluded_roles_helper():
    roles = ["Software Engineer", "Backend Developer", "Product Owner", "Golang Engineer"]
    kept = RicoChatAPI._filter_excluded_roles(roles, _CODING)
    assert kept == ["Product Owner"]  # all coding-adjacent removed


def _profile(**ov):
    data = dict(has_cv=True, name="T", preferred_cities=["Dubai"], location="Dubai",
                years_experience=8, skills=["x"], certifications=[],
                target_roles=["Software Engineer", "Product Owner"], current_role="PO")
    data.update(ov)
    return SimpleNamespace(**data)


def test_t5_handler_excludes_software_engineer(monkeypatch):
    """Profile-match search must NOT pick an excluded role as the search target."""
    api = RicoChatAPI(persist=False)
    captured = {}
    monkeypatch.setattr(api, "_resolve_profile", lambda uid: _profile())
    monkeypatch.setattr(api, "_get_recent_context", lambda uid: {})
    monkeypatch.setattr(api, "_store_recent_context", lambda uid, c: None)
    monkeypatch.setattr(api, "_append_chat", lambda *a, **k: None)
    monkeypatch.setattr(
        api, "_target_role_search_response",
        lambda user_id, role, profile, **kw: captured.update(role=role) or {"type": "job_matches", "message": "ok", "matches": []},
    )
    r = api._handle_active_user(
        "u-t5",
        "Find jobs based on my CV, but do not search Software Engineer, Full Stack, "
        "Backend, Golang, or Machine Learning roles",
    )
    # Target became Product Owner (Software Engineer filtered out), never SE.
    assert captured["role"] == "Product Owner"
    assert r.get("excluded_roles") == _CODING


# ── T6: descriptive category mapping ──────────────────────────────────────────

def test_t6_category_maps_to_allowed_roles_and_excludes_coding():
    r = classify_intent("I want product and technical management jobs, not coding jobs", has_cv_profile=True)
    assert r.legacy_intent == "job_search_multi_role"
    assert (r.entities or {}).get("roles") == _ALLOWED
    assert (r.entities or {}).get("excluded_roles") == _CODING


def test_t6_category_without_not_coding_still_maps():
    r = classify_intent("show me product and technical management roles", has_cv_profile=True)
    assert r.legacy_intent == "job_search_multi_role"
    assert (r.entities or {}).get("roles") == _ALLOWED
