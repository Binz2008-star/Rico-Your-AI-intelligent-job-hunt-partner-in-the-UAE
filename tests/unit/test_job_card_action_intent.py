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
        assert result.intent == "application.recent_context", (
            f"Expected 'application.recent_context' for phrase: {phrase!r}, got '{result.intent}'"
        )


def test_intent_v2_dotted_notation():
    """Intent v2 should use dotted notation for intent groups."""
    # Job search intents
    result = classify_intent("find live jobs for HSE Manager")
    assert result.intent == "job_search.explicit_role"
    assert result.entities.get("role") == "HSE Manager"

    result = classify_intent("find live jobs for Environmental Compliance Officer")
    assert result.intent == "job_search.explicit_role"
    assert result.entities.get("role") == "Environmental Compliance Officer"

    # Profile update intents
    result = classify_intent("save Environmental Manager as target role")
    assert result.intent == "profile.update_target_roles"
    assert result.entities.get("role") == "Environmental Manager"

    # Job card actions
    result = classify_intent("Prepare application — Office Manager - Part time (UAE Nationals Only) at Akamai")
    assert result.intent == "job_action.prepare_application"
    assert result.entities.get("job_title") == "Office Manager - Part time (UAE Nationals Only)"
    assert result.entities.get("company") == "Akamai"

    result = classify_intent("Open apply link — Office Manager - Part time (UAE Nationals Only) at Akamai")
    assert result.intent == "job_action.open_apply_link"
    assert result.entities.get("job_title") == "Office Manager - Part time (UAE Nationals Only)"
    assert result.entities.get("company") == "Akamai"

    result = classify_intent("Mark as applied — Office Manager - Part time (UAE Nationals Only) at Akamai")
    assert result.intent == "job_action.mark_applied"
    assert result.entities.get("job_title") == "Office Manager - Part time (UAE Nationals Only)"
    assert result.entities.get("company") == "Akamai"

    # Follow-up phrases
    result = classify_intent("where?")
    assert result.intent == "application.recent_context"
    assert result.context_required == True
    assert result.context_type == "recent_application"

    result = classify_intent("what about the job I just applied to?")
    assert result.intent == "application.recent_context"
    assert result.context_required == True
    assert result.context_type == "recent_application"

    # Profile match
    result = classify_intent("find me one that matches")
    assert result.intent == "job_search.profile_match"
    assert result.action == "search"

    # Profile show
    result = classify_intent("show my profile")
    assert result.intent == "profile.show"
    assert result.action == "show"
