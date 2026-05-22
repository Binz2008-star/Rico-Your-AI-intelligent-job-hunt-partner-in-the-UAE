"""
Regression tests for job-search intent routing fix (Issue #136)

These tests verify that explicit job searches are not intercepted by
profile recommendation flows, which was causing generic job searches
to be redirected instead of executing the search workflow.

The fix removed the fast-path override in rico_chat_api.py:1052-1057
that intercepted job_search_explicit intents without a job_title entity.
"""
import pytest
from unittest.mock import MagicMock, patch


def test_generic_find_jobs_executes_search_workflow():
    """
    Test that 'find jobs' (generic search without job_title) executes
    the normal search workflow instead of being intercepted by profile
    role suggestions.

    Regression for: Issue #136 - job-search intent interception
    """
    from src.rico_chat_api import RicoChatAPI

    # Mock the profile and system
    mock_profile = MagicMock()
    mock_profile.user_id = "test@example.com"
    mock_profile.target_roles = ["HSE Manager"]
    mock_profile.skills = ["HSE"]
    mock_profile.has_cv = True

    mock_system = MagicMock()
    mock_system.run_for_profile.return_value = {
        "matches": [
            {"title": "HSE Manager", "company": "Test Company", "score": 90},
        ]
    }

    chat_api = RicoChatAPI()
    chat_api.system = mock_system

    with patch.object(chat_api, "_resolve_profile", return_value=mock_profile), \
         patch.object(chat_api, "_build_router_context", return_value={}), \
         patch("src.rico_intent_router.route", return_value=MagicMock(entities={})):

        result = chat_api.process_message(
            user_id="test@example.com",
            message="find jobs"
        )

        # Verify that system.run_for_profile was called (not profile role suggestions)
        mock_system.run_for_profile.assert_called_once_with(mock_profile)

        # Verify the response contains job matches
        assert result.get("type") == "job_matches"
        assert "matches" in result


def test_specific_job_search_with_title_executes_search_workflow():
    """
    Test that 'find live jobs for Operations Manager' executes the normal
    search workflow with the extracted job_title entity.

    Regression for: Issue #136 - job-search intent interception
    """
    from src.rico_chat_api import RicoChatAPI

    # Mock the profile and system
    mock_profile = MagicMock()
    mock_profile.user_id = "test@example.com"
    mock_profile.target_roles = ["Operations Manager"]
    mock_profile.skills = ["Operations"]
    mock_profile.has_cv = True

    mock_system = MagicMock()
    mock_system.run_for_profile.return_value = {
        "matches": [
            {"title": "Operations Manager", "company": "Test Company", "score": 88},
        ]
    }

    chat_api = RicoChatAPI()
    chat_api.system = mock_system

    with patch.object(chat_api, "_resolve_profile", return_value=mock_profile), \
         patch.object(chat_api, "_build_router_context", return_value={}), \
         patch("src.rico_intent_router.route", return_value=MagicMock(entities={"job_title": "Operations Manager"})):

        result = chat_api.process_message(
            user_id="test@example.com",
            message="find live jobs for Operations Manager"
        )

        # Verify that system.run_for_profile was called
        mock_system.run_for_profile.assert_called_once_with(mock_profile)

        # Verify the response contains job matches
        assert result.get("type") == "job_matches"
        assert "matches" in result


def test_specific_job_search_with_sustainability_role_executes_search_workflow():
    """
    Test that 'find live jobs for Senior Sustainability Officer' executes
    the normal search workflow with the extracted job_title entity.

    Regression for: Issue #136 - job-search intent interception
    """
    from src.rico_chat_api import RicoChatAPI

    # Mock the profile and system
    mock_profile = MagicMock()
    mock_profile.user_id = "test@example.com"
    mock_profile.target_roles = ["Senior Sustainability Officer"]
    mock_profile.skills = ["Sustainability", "ESG"]
    mock_profile.has_cv = True

    mock_system = MagicMock()
    mock_system.run_for_profile.return_value = {
        "matches": [
            {"title": "Senior Sustainability Officer", "company": "Test Company", "score": 92},
        ]
    }

    chat_api = RicoChatAPI()
    chat_api.system = mock_system

    with patch.object(chat_api, "_resolve_profile", return_value=mock_profile), \
         patch.object(chat_api, "_build_router_context", return_value={}), \
         patch("src.rico_intent_router.route", return_value=MagicMock(entities={"job_title": "Senior Sustainability Officer"})):

        result = chat_api.process_message(
            user_id="test@example.com",
            message="find live jobs for Senior Sustainability Officer"
        )

        # Verify that system.run_for_profile was called
        mock_system.run_for_profile.assert_called_once_with(mock_profile)

        # Verify the response contains job matches
        assert result.get("type") == "job_matches"
        assert "matches" in result


def test_format_match_omits_null_why_for_jsearch_result():
    """
    Test that _format_match omits null optional fields for JSearch results
    without rico_explanation, preventing Zod schema validation failures.

    Regression for: Post-merge Zod failure - JobMatchSchema.why is optional,
    not nullable. Direct JSearch results do not include rico_explanation, so
    the response should not emit "why": null.
    """
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    job = {
        "title": "HSE Manager",
        "company": "Acme Safety",
        "location": "Dubai, AE",
        "score": 50,
        "source": "jsearch",
        "description": "HSE role in Dubai",
    }

    formatted = api._format_match(job, profile=None)

    assert formatted["title"] == "HSE Manager"
    assert formatted["company"] == "Acme Safety"
    assert formatted["score"] == 50
    assert "why" not in formatted
    assert isinstance(formatted["title"], str)
    assert isinstance(formatted["company"], str)
