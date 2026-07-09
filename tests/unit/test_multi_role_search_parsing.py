# -*- coding: utf-8 -*-
"""
Regression tests for multi-role job-search parsing.

Production bug: a single message listing several target roles —

    "Search for Technical Product Owner, Product Owner, Technical Project Manager,
     Digital Transformation Manager, and Operations Technology Manager roles in
     UAE. Do not search pure Software Engineer, Full Stack, Backend, Golang, or
     Machine Learning roles unless I explicitly ask for coding jobs."

— was captured as ONE unknown role because the role-change regex greedily grabbed
everything after "search for". Rico replied "I do not recognize '<the whole list>'
as a job role".

Fix:
- extract_role_list() splits the comma/and-separated positive list into individual
  target roles and parses the trailing "do not search …" clause into an exclusion
  list, stripping "roles in UAE" / "jobs in Dubai" qualifiers.
- classify_intent() routes such messages to the "job_search_multi_role" intent with
  both lists in entities, instead of "role_change" with the whole string as a role.

These tests are intentionally scoped to parsing/classification and do not call any
live search provider.
"""
from __future__ import annotations

import pytest

from src.agent.intelligence.intent_classifier import (
    classify_intent,
    extract_role_list,
)


# The exact production prompt that triggered the bug.
PROD_PROMPT = (
    "Search for Technical Product Owner, Product Owner, Technical Project Manager, "
    "Digital Transformation Manager, and Operations Technology Manager roles in UAE. "
    "Do not search pure Software Engineer, Full Stack, Backend, Golang, or Machine "
    "Learning roles unless I explicitly ask for coding jobs."
)

EXPECTED_ROLES = [
    "Technical Product Owner",
    "Product Owner",
    "Technical Project Manager",
    "Digital Transformation Manager",
    "Operations Technology Manager",
]

EXPECTED_EXCLUSIONS = [
    "Software Engineer",
    "Full Stack",
    "Backend",
    "Golang",
    "Machine Learning",
]


# ── extract_role_list() ───────────────────────────────────────────────────────

def test_production_prompt_extracts_all_five_target_roles():
    roles, excluded = extract_role_list(PROD_PROMPT)
    assert roles == EXPECTED_ROLES


def test_production_prompt_extracts_all_five_exclusions():
    roles, excluded = extract_role_list(PROD_PROMPT)
    assert excluded == EXPECTED_EXCLUSIONS


def test_trailing_roles_in_uae_qualifier_is_stripped():
    """"Operations Technology Manager roles in UAE" -> bare role, no qualifier."""
    roles, _ = extract_role_list(PROD_PROMPT)
    assert "Operations Technology Manager" in roles
    assert all("UAE" not in r and "roles" not in r.lower() for r in roles)


def test_pure_qualifier_stripped_from_excluded_roles():
    """"pure Software Engineer" -> "Software Engineer"."""
    _, excluded = extract_role_list(PROD_PROMPT)
    assert "Software Engineer" in excluded
    assert not any(r.lower().startswith("pure ") for r in excluded)


@pytest.mark.parametrize("text,expected", [
    ("search for Product Owner and Project Manager jobs",
     ["Product Owner", "Project Manager"]),
    ("find Data Analyst, Data Scientist and BI Developer roles in Dubai",
     ["Data Analyst", "Data Scientist", "BI Developer"]),
    ("show me HSE Manager / Safety Officer positions",
     ["HSE Manager", "Safety Officer"]),
])
def test_other_multi_role_lists(text, expected):
    roles, _ = extract_role_list(text)
    assert roles == expected


def test_single_role_search_yields_one_role():
    """A normal single-role search must not be split into a multi-role list."""
    roles, excluded = extract_role_list("find operations manager jobs in ajman")
    assert roles == ["operations manager"]
    assert excluded == []


def test_in_location_alone_is_not_a_role():
    roles, _ = extract_role_list("search for jobs in Dubai and Abu Dhabi")
    assert roles == []


# ── classify_intent() ─────────────────────────────────────────────────────────

def test_production_prompt_routes_to_multi_role_intent():
    result = classify_intent(PROD_PROMPT, has_cv_profile=True)
    assert result.legacy_intent == "job_search_multi_role"
    # Primary role is exposed via the legacy extracted_role field for back-compat.
    assert result.extracted_role == "Technical Product Owner"


def test_production_prompt_intent_carries_role_and_exclusion_lists():
    result = classify_intent(PROD_PROMPT, has_cv_profile=True)
    assert result.entities.get("roles") == EXPECTED_ROLES
    assert result.entities.get("excluded_roles") == EXPECTED_EXCLUSIONS


def test_production_prompt_uae_is_not_a_city_constraint():
    """"in UAE" is the default scope, so no location entity should be attached."""
    result = classify_intent(PROD_PROMPT, has_cv_profile=True)
    assert "location" not in result.entities


def test_multi_role_list_with_city_attaches_location():
    result = classify_intent(
        "search for Product Owner and Project Manager roles in Dubai",
        has_cv_profile=True,
    )
    assert result.legacy_intent == "job_search_multi_role"
    assert result.entities.get("location") == "Dubai"


# ── #812: compound-title connectives must not be split on "and" ──────────────
# Production bug: "find environmental health and safety manager jobs in Dubai"
# was parsed as two fragment roles ["environmental health", "safety manager"]
# because extract_role_list() splits every bare "and". These "X and Y" phrases
# are themselves job-title vocabulary in the UAE market and must survive as a
# single role.

@pytest.mark.parametrize("text,expected_role", [
    ("find environmental health and safety manager jobs in Dubai",
     "environmental health and safety manager"),
    ("search for food and beverage manager jobs",
     "food and beverage manager"),
    ("find oil and gas engineer positions",
     "oil and gas engineer"),
    ("show me facilities and maintenance manager roles",
     "facilities and maintenance manager"),
    ("search for health and safety officer jobs",
     "health and safety officer"),
])
def test_compound_title_connective_not_split(text, expected_role):
    roles, excluded = extract_role_list(text)
    assert roles == [expected_role]
    assert excluded == []


def test_compound_title_routes_to_single_role_intent():
    """The exact production message from #812 must route to a single-role
    search with the whole compound title, not job_search_multi_role."""
    result = classify_intent(
        "find environmental health and safety manager jobs in Dubai",
        has_cv_profile=True,
    )
    assert result.legacy_intent != "job_search_multi_role"
    assert result.extracted_role == "environmental health and safety manager"
    assert result.entities.get("location") == "Dubai"


def test_compound_title_alongside_a_real_second_role_still_splits():
    """A compound title combined with an unrelated second role via a real list
    connector must still split into two roles — only the known "X and Y"
    connective phrases are protected, not "and" in general."""
    roles, _ = extract_role_list(
        "search for health and safety officer and marketing manager jobs"
    )
    assert roles == ["health and safety officer", "marketing manager"]


def test_and_between_two_cities_still_splits():
    """Regression guard: the compound-title shield must not affect plain
    location lists joined by "and" (unrelated to any protected phrase)."""
    roles, _ = extract_role_list("search for jobs in Dubai and Abu Dhabi")
    assert roles == []


def test_single_role_search_is_not_multi_role():
    """Single-role searches keep the existing job_search_explicit routing."""
    result = classify_intent("find operations manager jobs in ajman", has_cv_profile=True)
    assert result.legacy_intent == "job_search_explicit"
    assert result.extracted_role == "operations manager"
