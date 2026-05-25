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
    (
        "Open apply link — Office Manager at Akamai",
        "open_apply_link",
        "Office Manager",
        "Akamai",
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


def test_application_tracking_followup_phrases():
    """Follow-up phrases should be classified as application_tracking intent."""
    followup_phrases = [
        "where",
        "where can i see it",
        "where is it",
        "what about the job i just applied to",
        "what about the job i just tracked",
        "show it",
        "open application flow",
        "open applications",
    ]
    for phrase in followup_phrases:
        result = classify_intent(phrase)
        assert result.intent == "application_tracking", (
            f"Expected 'application_tracking' for phrase: {phrase!r}, got '{result.intent}'"
        )


def test_intent_result_v2_fields():
    """IntentResult should have v2 fields for future use."""
    result = classify_intent("find jobs for Software Engineer")
    # Check that new v2 fields exist (even if not populated yet)
    assert hasattr(result, "subintent")
    assert hasattr(result, "entities")
    assert hasattr(result, "context_required")
    assert hasattr(result, "context_type")
    assert hasattr(result, "action")
    assert hasattr(result, "target_route")
    assert hasattr(result, "legacy_intent")
    # Legacy fields should still exist
    assert hasattr(result, "extracted_role")
    assert hasattr(result, "extracted_title")
    assert hasattr(result, "extracted_company")


def test_compatibility_mapper():
    """The compatibility mapper should map v2 intents to legacy names."""
    from src.agent.intelligence.intent_classifier import _map_intent_to_legacy
    assert _map_intent_to_legacy("job_search.explicit_role") == "job_search_explicit"
    assert _map_intent_to_legacy("job_action.prepare_application") == "prepare_application"
    assert _map_intent_to_legacy("application.show_flow") == "application_tracking"
    assert _map_intent_to_legacy("profile.show") == "profile_summary"
    # Unmapped intents should return as-is
    assert _map_intent_to_legacy("unknown") == "unknown"
    assert _map_intent_to_legacy("help") == "help"
