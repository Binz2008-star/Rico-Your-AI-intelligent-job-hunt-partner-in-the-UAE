from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent.intelligence.intent_classifier import classify_intent
from src.rico_chat_api import RicoChatAPI


USER = "test@rico.ai"


def _make_api() -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    api._memory = {}
    api.system = MagicMock()
    api.system.run_for_profile.side_effect = AssertionError("job search must not run")
    return api


def _make_profile() -> MagicMock:
    profile = MagicMock()
    profile.has_cv = True
    profile.target_roles = ["Environmental Manager"]
    profile.skills = []
    profile.name = "Test User"
    profile.email = USER
    return profile


def _agent() -> MagicMock:
    agent = MagicMock()
    agent.openai_available = False
    agent.deepseek_available = False
    agent.hf_available = False
    agent.provider_available = True
    agent.model = ""
    return agent


def _recent_context() -> dict:
    return {
        "recent_search_matches": [
            {
                "title": "Environmental Manager - Railway Construction Project",
                "company": "Confidential Jobs",
                "location": "Dubai",
                "apply_url": "https://example.com/apply",
                "source_url": "https://example.com/job",
            }
        ]
    }


@pytest.mark.parametrize(
    "phrase",
    [
        "I applied manually",
        "I applied myself",
        "I already applied",
        "I submitted the application myself",
        "how can you log it",
        "can you log it",
        "mark it as applied",
        "I applied outside Rico",
        "ya i applied manual my self so how can u log it",
    ],
)
def test_english_manual_applied_phrases_are_status_updates_not_lifecycle_lists(phrase: str) -> None:
    result = classify_intent(phrase, has_cv_profile=True)

    assert result.intent == "application_status_update"
    assert result.intent != "lifecycle_show_applied"
    assert result.intent != "application_tracking"
    assert result.target_route == "/applications"


def test_english_lifecycle_applied_history_query_still_lists_applications() -> None:
    result = classify_intent("what jobs have I applied to?", has_cv_profile=True)

    assert result.intent == "lifecycle_show_applied"


def test_i_applied_myself_without_recent_context_prompts_for_manual_details() -> None:
    api = _make_api()

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(api, "_get_recent_context", return_value={}),
        patch("src.repositories.applications_repo.create", side_effect=AssertionError("must not write")),
        patch("src.repositories.user_job_context_repo.get_recently_interacted", return_value=[]),
        patch("src.repositories.user_job_context_repo.get_recently_discussed", return_value=[]),
    ):
        result = api.process_message(USER, "I applied myself")

    assert result["type"] == "clarification"
    assert result["intent"] == "application_status_update"
    assert "job title" in result["message"].lower()
    assert "company" in result["message"].lower()
    assert "source/link" in result["message"].lower()
    assert "/applications" in result["message"]
    assert "/queue" not in result["message"]
    assert "no tracked applications" not in result["message"].lower()


def test_how_can_you_log_it_with_recent_context_gives_manual_logging_guidance() -> None:
    api = _make_api()

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(api, "_get_recent_context", return_value=_recent_context()),
        patch("src.repositories.applications_repo.create", side_effect=AssertionError("must not write")),
    ):
        result = api.process_message(USER, "how can you log it")

    assert result["type"] == "manual_application_logging_guidance"
    assert "Environmental Manager - Railway Construction Project" in result["message"]
    assert "Confidential Jobs" in result["message"]
    assert "mark it as applied" in result["message"]
    assert "/applications" in result["message"]
    assert "/queue" not in result["message"]
    assert "no tracked applications" not in result["message"].lower()


def test_mark_it_as_applied_persists_after_recent_context() -> None:
    api = _make_api()
    create_calls: list[dict] = []
    lifecycle_calls: list[dict] = []

    def fake_create(**kwargs):
        create_calls.append(kwargs)
        return True

    def fake_lifecycle(**kwargs):
        lifecycle_calls.append(kwargs)
        return True

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(api, "_get_recent_context", return_value=_recent_context()),
        patch.object(api, "_store_recent_context"),
        patch.object(api, "_classified_role_search", side_effect=AssertionError("job search must not run")),
        patch.object(api, "_target_role_search_response", side_effect=AssertionError("job search must not run")),
        patch("src.repositories.applications_repo.find_by_job_id", return_value=None),
        patch("src.repositories.applications_repo.create", side_effect=fake_create),
        patch("src.repositories.user_job_context_repo.set_lifecycle_status", side_effect=fake_lifecycle),
    ):
        result = api.process_message(USER, "mark it as applied")

    assert result["type"] == "application_status_update"
    assert result["job_status"] == "applied"
    assert "/applications" in result["message"]
    assert "/queue" not in result["message"]
    assert create_calls[0]["status"] == "applied"
    assert create_calls[0]["user_id"] == USER
    assert lifecycle_calls[0]["status"] == "applied"
    assert lifecycle_calls[0]["user_id"] == USER


def test_mark_it_as_applied_failure_does_not_claim_saved() -> None:
    api = _make_api()

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(api, "_get_recent_context", return_value=_recent_context()),
        patch.object(api, "_store_recent_context"),
        patch("src.repositories.applications_repo.find_by_job_id", return_value=None),
        patch("src.repositories.applications_repo.create", return_value=False),
    ):
        result = api.process_message(USER, "mark it as applied")

    msg = result["message"].lower()

    assert result["type"] == "application_status_update_failed"
    assert result["job_status"] is None
    assert "could not save" in msg
    assert "marked as submitted" not in msg
    assert "marked as applied" not in msg
    assert "saved" not in msg
    assert result["target_route"] == "/applications"
