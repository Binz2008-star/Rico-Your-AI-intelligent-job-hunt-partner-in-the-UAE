"""Unit tests for job-card action intent classification (Intent v2).

Verifies that job card action messages of the form
    "{action} — {title} at {company}"
are correctly classified using Intent v2 dotted notation, and that
title/company are extracted correctly.
"""
from __future__ import annotations

import pytest
from src.agent.intelligence.intent_classifier import classify_intent


@pytest.mark.parametrize("message,expected_intent,expected_title,expected_company", [
    (
        "Prepare application — HSE Manager- Manufacturing at Renew",
        "job_action.prepare_application",
        "HSE Manager- Manufacturing",
        "Renew",
    ),
    (
        "Prepare application — Software Engineer at Acme Corp",
        "job_action.prepare_application",
        "Software Engineer",
        "Acme Corp",
    ),
    (
        "Mark as applied — Environmental Compliance Officer at TotalEnergies",
        "job_action.mark_applied",
        "Environmental Compliance Officer",
        "TotalEnergies",
    ),
    (
        "Track this job — Senior HSE Advisor at ADNOC",
        "job_action.track_job",
        "Senior HSE Advisor",
        "ADNOC",
    ),
    (
        "Save job — Project Manager at Al Futtaim",
        "job_action.save_job",
        "Project Manager",
        "Al Futtaim",
    ),
    (
        "Open apply link — Office Manager at Akamai",
        "job_action.open_apply_link",
        "Office Manager",
        "Akamai",
    ),
    # Em-dash variant
    (
        "Prepare application — Data Scientist at Google",
        "job_action.prepare_application",
        "Data Scientist",
        "Google",
    ),
    # Job title containing " - " (greedy capture must split on last "at")
    (
        "Prepare application — Office Manager - Part time (UAE Nationals Only) at Akamai",
        "job_action.prepare_application",
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
    assert result.legacy_intent is not None


def test_job_card_entities_populated():
    """entities dict must mirror extracted_title/company for v2 consumers."""
    result = classify_intent(
        "Mark as applied — Office Manager - Part time (UAE Nationals Only) at Akamai"
    )
    assert result.intent == "job_action.mark_applied"
    assert result.entities.get("job_title") == "Office Manager - Part time (UAE Nationals Only)"
    assert result.entities.get("company") == "Akamai"
    assert result.legacy_intent == "mark_applied"


def test_generic_prepare_application_does_not_match_job_card_pattern():
    """Plain 'prepare application' without the em-dash format should not match job card pattern."""
    result = classify_intent("prepare application angle for my target roles")
    assert result.intent != "job_action.prepare_application" or (
        result.extracted_title is None and result.extracted_company is None
    ), "Generic prepare message should not extract title/company"


def test_job_card_pattern_does_not_match_unrelated_messages():
    """Standard search messages should not be misclassified as job card actions."""
    result = classify_intent("find jobs for Environmental Compliance Officer")
    assert result.intent == "job_search.explicit_role"

    result = classify_intent("save Environmental Manager as target role")
    assert result.intent == "profile.update_target_roles"


def test_application_recent_context_phrases():
    """Short follow-up phrases must route to application.recent_context."""
    recent_context_phrases = [
        "where",
        "where?",
        "where can i see it",
        "where is it",
        "what about the job i just applied to",
        "what about the job i just applied to?",
        "what about the job i just tracked",
        "show it",
    ]
    for phrase in recent_context_phrases:
        result = classify_intent(phrase)
        assert result.intent == "application.recent_context", (
            f"Expected 'application.recent_context' for: {phrase!r}, got '{result.intent}'"
        )
        assert result.context_required is True
        assert result.context_type == "recent_application"
        assert result.legacy_intent == "application_tracking"


def test_application_show_flow_phrases():
    """List/navigation phrases must route to application.show_flow."""
    show_flow_phrases = [
        "show my applications",
        "my applications",
        "application status",
        "open application flow",
        "open applications",
        "show applied jobs",
    ]
    for phrase in show_flow_phrases:
        result = classify_intent(phrase)
        assert result.intent == "application.show_flow", (
            f"Expected 'application.show_flow' for: {phrase!r}, got '{result.intent}'"
        )
        assert result.legacy_intent == "application_tracking"


def test_intent_v2_dotted_notation():
    """Intent v2 dotted notation, entities, and legacy mapping for key flows."""
    result = classify_intent("find live jobs for HSE Manager")
    assert result.intent == "job_search.explicit_role"
    assert result.entities.get("role") == "HSE Manager"

    result = classify_intent("find live jobs for Environmental Compliance Officer")
    assert result.intent == "job_search.explicit_role"
    assert result.entities.get("role") == "Environmental Compliance Officer"

    result = classify_intent("save Environmental Manager as target role")
    assert result.intent == "profile.update_target_roles"
    assert result.entities.get("role") == "Environmental Manager"

    result = classify_intent(
        "Prepare application — Office Manager - Part time (UAE Nationals Only) at Akamai"
    )
    assert result.intent == "job_action.prepare_application"
    assert result.entities.get("job_title") == "Office Manager - Part time (UAE Nationals Only)"
    assert result.entities.get("company") == "Akamai"

    result = classify_intent(
        "Open apply link — Office Manager - Part time (UAE Nationals Only) at Akamai"
    )
    assert result.intent == "job_action.open_apply_link"
    assert result.entities.get("job_title") == "Office Manager - Part time (UAE Nationals Only)"
    assert result.entities.get("company") == "Akamai"

    result = classify_intent(
        "Mark as applied — Office Manager - Part time (UAE Nationals Only) at Akamai"
    )
    assert result.intent == "job_action.mark_applied"
    assert result.entities.get("job_title") == "Office Manager - Part time (UAE Nationals Only)"
    assert result.entities.get("company") == "Akamai"

    result = classify_intent("where?")
    assert result.intent == "application.recent_context"
    assert result.context_required is True
    assert result.context_type == "recent_application"
    assert result.legacy_intent == "application_tracking"

    result = classify_intent("what about the job I just applied to?")
    assert result.intent == "application.recent_context"
    assert result.context_required is True

    result = classify_intent("find me one that matches")
    assert result.intent == "job_search.profile_match"
    assert result.action == "search"

    result = classify_intent("show my profile")
    assert result.intent == "profile.show"
    assert result.action == "show"
