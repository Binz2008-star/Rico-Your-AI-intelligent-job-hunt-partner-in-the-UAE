from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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


def _recent_context_with_stale_data() -> dict:
    return {
        "recent_application": {
            "title": "Any",
            "company": "الشركة",
            "location": "Dubai",
        }
    }


@pytest.mark.parametrize(
    "phrase",
    [
        "اكتبلي قصيده",
        "اكتبلي نكتة",
        "اكتبلي قصة",
        "write me a poem",
        "write a joke",
        "write a story",
    ],
)
def test_creative_requests_bypass_application_context(phrase: str) -> None:
    """Creative/general writing requests should not trigger application draft generation."""
    assert RicoChatAPI._is_creative_writing_request(phrase) is True


@pytest.mark.parametrize(
    "phrase",
    [
        "translate this cover letter",
        "explain this job description",
        "rewrite my application message",
        "ترجم رسالة التقديم",
        "اشرح وصف الوظيفة",
    ],
)
def test_job_application_requests_do_not_bypass(phrase: str) -> None:
    """Job/application-related requests should NOT bypass application context."""
    assert RicoChatAPI._is_creative_writing_request(phrase) is False


def test_poem_about_job_hunting_bypasses() -> None:
    """A poem about job hunting is still a creative request and should bypass."""
    assert RicoChatAPI._is_creative_writing_request("write me a poem about job hunting") is True


def test_stale_context_with_role_any_company_arabic_is_ignored_for_creative_request() -> None:
    """Stale context with placeholder values should be ignored for unrelated creative requests."""
    api = _make_api()

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=MagicMock()),
        patch.object(api, "_get_recent_context", return_value=_recent_context_with_stale_data()),
        patch("src.repositories.applications_repo.create", side_effect=AssertionError("must not write")),
    ):
        result = api.process_message(USER, "اكتبلي قصيده")

    # Should not return application draft type
    assert result["type"] != "draft_message"
    assert result["type"] != "application_channel_clarification"
    # Should not mention "Any" or "الشركة" in the response
    msg = result.get("message", "").lower()
    assert "any" not in msg
    assert "الشركة" not in result.get("message", "")


def test_application_draft_with_placeholder_title_asks_for_details() -> None:
    """Application draft should ask for job title if it's a placeholder value."""
    api = _make_api()

    job = {"title": "Any", "company": "Google", "location": "Dubai"}
    profile = _make_profile()

    draft = api._draft_application_message(job, profile, arabic=False)

    assert "Please provide the job title" in draft
    assert "Any" not in draft


def test_application_draft_with_placeholder_company_asks_for_details() -> None:
    """Application draft should ask for company name if it's a placeholder value."""
    api = _make_api()

    job = {"title": "Software Engineer", "company": "الشركة", "location": "Dubai"}
    profile = _make_profile()

    draft = api._draft_application_message(job, profile, arabic=False)

    assert "Please provide the company name" in draft
    assert "الشركة" not in draft


def test_application_draft_with_arabic_placeholder_asks_for_details() -> None:
    """Application draft should ask for details in Arabic when using Arabic placeholders."""
    api = _make_api()

    job = {"title": "الدور", "company": "Google", "location": "Dubai"}
    profile = _make_profile()

    draft = api._draft_application_message(job, profile, arabic=True)

    assert "يرجى تزويدي باسم الدور الوظيفي" in draft
    # The placeholder should not be used as the actual job title in a draft
    assert "لدور الدور" not in draft  # Should not say "apply for role الدور"


def test_application_draft_with_valid_details_generates_message() -> None:
    """Application draft should generate message when title and company are valid."""
    api = _make_api()

    job = {"title": "Software Engineer", "company": "Google", "location": "Dubai"}
    profile = _make_profile()

    draft = api._draft_application_message(job, profile, arabic=False)

    # Should not ask for details
    assert "Please provide" not in draft
    # Should contain the actual job details
    assert "Software Engineer" in draft
    assert "Google" in draft


def test_creative_request_does_not_use_stale_application_context() -> None:
    """Creative requests should not use stale application context from previous turns."""
    api = _make_api()

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=MagicMock()),
        patch.object(api, "_get_recent_context", return_value=_recent_context_with_stale_data()),
    ):
        result = api.process_message(USER, "write me a poem")

    # Should route to AI fallback for creative writing, not application context
    assert result["type"] != "draft_message"
    assert result["type"] != "application_channel_clarification"
    # Response should not contain job application context
    msg = result.get("message", "")
    assert "Any" not in msg
    assert "الشركة" not in msg
