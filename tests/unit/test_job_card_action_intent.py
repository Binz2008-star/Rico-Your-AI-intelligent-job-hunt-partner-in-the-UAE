"""Unit tests for job-card action intent classification.

Verifies that job card action messages of the form
    "{action} — {title} at {company}"
are correctly classified and that title/company are extracted.
"""
from __future__ import annotations

import pytest
from src.agent.intelligence.intent_classifier import classify_intent


@pytest.mark.parametrize("message,expected_intent,expected_title,expected_company", [
    (
        "Prepare application — HSE Manager- Manufacturing at Renew",
        "prepare_application",
        "HSE Manager- Manufacturing",
        "Renew",
    ),
    (
        "Prepare application — Software Engineer at Acme Corp",
        "prepare_application",
        "Software Engineer",
        "Acme Corp",
    ),
    (
        "Mark as applied — Environmental Compliance Officer at TotalEnergies",
        "mark_applied",
        "Environmental Compliance Officer",
        "TotalEnergies",
    ),
    (
        "Track this job — Senior HSE Advisor at ADNOC",
        "track_job",
        "Senior HSE Advisor",
        "ADNOC",
    ),
    (
        "Save job — Project Manager at Al Futtaim",
        "save_job",
        "Project Manager",
        "Al Futtaim",
    ),
    # Em-dash variant
    (
        "Prepare application — Data Scientist at Google",
        "prepare_application",
        "Data Scientist",
        "Google",
    ),
])
def test_job_card_action_intent(message, expected_intent, expected_title, expected_company):
    result = classify_intent(message)
    assert result.intent == expected_intent, (
        f"Expected intent '{expected_intent}', got '{result.intent}' for: {message!r}"
    )
    assert result.extracted_title == expected_title, (
        f"Expected title '{expected_title}', got '{result.extracted_title}'"
    )
    assert result.extracted_company == expected_company, (
        f"Expected company '{expected_company}', got '{result.extracted_company}'"
    )
    assert result.confidence == 0.95
    assert result.source == "regex"


def test_generic_prepare_application_does_not_match_job_card_pattern():
    """Plain 'prepare application' without the em-dash format should not match job card pattern."""
    result = classify_intent("prepare application angle for my target roles")
    assert result.intent != "prepare_application" or (
        result.extracted_title is None and result.extracted_company is None
    ), "Generic prepare message should not extract title/company"


def test_job_card_pattern_does_not_match_unrelated_messages():
    """Standard search messages should not be misclassified as job card actions."""
    result = classify_intent("find jobs for Environmental Compliance Officer")
    assert result.intent == "job_search_explicit"

    result = classify_intent("save Environmental Manager as target role")
    assert result.intent == "save_target_role"
