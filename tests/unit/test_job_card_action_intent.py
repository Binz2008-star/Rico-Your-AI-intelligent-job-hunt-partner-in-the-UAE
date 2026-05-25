"""Unit tests for job-card action intent classification.

Verifies that job card action messages of the form
    "{action} — {title} at {company}"
are correctly classified, and that title/company are extracted correctly.
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
    # Job title containing " - " (greedy capture must split on last "at")
    (
        "Prepare application — Office Manager - Part time (UAE Nationals Only) at Akamai",
        "prepare_application",
        "Office Manager - Part time (UAE Nationals Only)",
        "Akamai",
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


def test_application_tracking_phrases():
    """List/navigation phrases must route to application_tracking."""
    tracking_phrases = [
        "show my tracked applications",
        "show my applications",
        "application status",
        "applications status",
        "tracked applications",
        "my applications",
        "show applications",
        "show applied jobs",
        "applied jobs",
        "show my applied jobs",
        "show interviews",
        "interview status",
        "my interviews",
        "show offers",
        "show rejections",
        "follow up",
        "remind me to follow up",
        "open application flow",
        "open applications",
    ]
    for phrase in tracking_phrases:
        result = classify_intent(phrase)
        assert result.intent == "application_tracking", (
            f"Expected 'application_tracking' for phrase: {phrase!r}, got '{result.intent}'"
        )


def test_recent_context_phrases():
    """Short follow-up phrases must route to recent_context."""
    recent_context_phrases = [
        "where",
        "where?",
        "where can i see it",
        "where is it",
        "show it",
        "what about the job i just applied to",
        "what about the job i just applied to?",
        "what about the job i just tracked",
    ]
    for phrase in recent_context_phrases:
        result = classify_intent(phrase)
        assert result.intent == "recent_context", (
            f"Expected 'recent_context' for: {phrase!r}, got '{result.intent}'"
        )


def test_open_apply_link_intent():
    """Open apply link messages must not trigger the apply confirmation gate."""
    cases = [
        "Open apply link -- HSE Manager at ADNOC",
        "open apply link for Software Engineer at Google",
        "Open apply link -- Office Manager - Part time (UAE Nationals Only) at Akamai",
    ]
    for msg in cases:
        result = classify_intent(msg)
        assert result.intent == "open_apply_link", (
            f"Expected 'open_apply_link', got '{result.intent}' for: {msg!r}"
        )
        assert result.intent != "apply_job", f"Must not route to apply_job: {msg!r}"


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
