"""tests/unit/test_cv_persistence_chat.py

Regression tests for Issue #101: public CV profile persistence so chat
stops re-asking known fields.

Covers:
- RicoProfile dataclass preserves CV fields (cv_filename, cv_status, etc.)
- _has_cv_profile detects CV-backed profiles correctly
- _looks_like_bare_target_role is case-insensitive
- _get_blocked_questions blocks experience/location/industry when known
- _remove_blocked_questions strips blocked lines from AI responses
- "Find UAE jobs that match my CV" with a parsed CV must search, not return
  internal/technical flow text
"""
import pytest
from unittest.mock import MagicMock

from src.rico_agent import RicoProfile
from src.rico_chat_api import RicoChatAPI
from src.jsearch_client import FetchResult


class TestRicoProfileCVFields:
    """RicoProfile must accept and round-trip CV-related fields."""

    def test_cv_filename_preserved(self):
        profile = RicoProfile(
            user_id="test@example.com",
            cv_filename="cv_test.pdf",
        )
        assert profile.cv_filename == "cv_test.pdf"

    def test_cv_status_preserved(self):
        profile = RicoProfile(
            user_id="test@example.com",
            cv_status="parsed",
        )
        assert profile.cv_status == "parsed"

    def test_profile_creation_mode_preserved(self):
        profile = RicoProfile(
            user_id="test@example.com",
            profile_creation_mode="cv_first",
        )
        assert profile.profile_creation_mode == "cv_first"

    def test_manual_profile_wizard_disabled_preserved(self):
        profile = RicoProfile(
            user_id="test@example.com",
            manual_profile_wizard_disabled=True,
        )
        assert profile.manual_profile_wizard_disabled is True

    def test_full_cv_profile_roundtrip(self):
        profile = RicoProfile(
            user_id="public:web-test",
            cv_filename="robin_cv.pdf",
            cv_status="parsed",
            skills=["hse", "iso 14001", "compliance"],
            years_experience=10.0,
            profile_creation_mode="cv_first",
            manual_profile_wizard_disabled=True,
        )
        assert profile.cv_filename == "robin_cv.pdf"
        assert profile.cv_status == "parsed"
        assert profile.skills == ["hse", "iso 14001", "compliance"]
        assert profile.years_experience == 10.0


class TestHasCvProfile:
    """_has_cv_profile must detect CV-backed profiles via any reliable signal."""

    def test_none_profile_returns_false(self):
        assert RicoChatAPI._has_cv_profile(None) is False

    def test_cv_filename_signal(self):
        profile = RicoProfile(user_id="u1", cv_filename="cv.pdf")
        assert RicoChatAPI._has_cv_profile(profile) is True

    def test_cv_status_parsed_signal(self):
        profile = RicoProfile(user_id="u1", cv_status="parsed")
        assert RicoChatAPI._has_cv_profile(profile) is True

    def test_skills_signal(self):
        profile = RicoProfile(user_id="u1", skills=["python"])
        assert RicoChatAPI._has_cv_profile(profile) is True

    def test_years_experience_signal(self):
        profile = RicoProfile(user_id="u1", years_experience=5.0)
        assert RicoChatAPI._has_cv_profile(profile) is True

    def test_empty_profile_returns_false(self):
        profile = RicoProfile(user_id="u1")
        assert RicoChatAPI._has_cv_profile(profile) is False

    def test_dict_profile_cv_status(self):
        assert RicoChatAPI._has_cv_profile({"cv_status": "parsed"}) is True

    def test_dict_profile_empty(self):
        assert RicoChatAPI._has_cv_profile({}) is False


class TestLooksLikeBareTargetRole:
    """_looks_like_bare_target_role must accept lowercase role names."""

    @pytest.mark.parametrize("message", [
        "sales man",
        "Sales Man",
        "SALES MAN",
        "software engineer",
        "hse manager",
        "general manager",
        "product owner",
        "data scientist",
    ])
    def test_lowercase_roles_are_accepted(self, message):
        assert RicoChatAPI._looks_like_bare_target_role(message) is True

    def test_whats_next_phrases_rejected(self):
        assert RicoChatAPI._looks_like_bare_target_role("what's next") is False

    def test_digits_rejected(self):
        assert RicoChatAPI._looks_like_bare_target_role("sales manager 2") is False

    def test_too_many_words_rejected(self):
        assert RicoChatAPI._looks_like_bare_target_role("this is a very long role name") is False

    def test_empty_rejected(self):
        assert RicoChatAPI._looks_like_bare_target_role("") is False


class TestGetBlockedQuestions:
    """_get_blocked_questions must block questions for fields already known from CV."""

    def test_no_profile_returns_empty(self):
        api = RicoChatAPI()
        assert api._get_blocked_questions(None) == []

    def test_cv_filename_blocks_experience(self):
        api = RicoChatAPI()
        profile = RicoProfile(user_id="u1", cv_filename="cv.pdf")
        blocked = api._get_blocked_questions(profile)
        assert "experience" in blocked

    def test_cv_status_parsed_blocks_experience(self):
        api = RicoChatAPI()
        profile = RicoProfile(user_id="u1", cv_status="parsed")
        blocked = api._get_blocked_questions(profile)
        assert "experience" in blocked

    def test_years_experience_blocks_experience(self):
        api = RicoChatAPI()
        profile = RicoProfile(user_id="u1", years_experience=8.0)
        blocked = api._get_blocked_questions(profile)
        assert "experience" in blocked

    def test_preferred_cities_blocks_location(self):
        api = RicoChatAPI()
        profile = RicoProfile(user_id="u1", preferred_cities=["Dubai"])
        blocked = api._get_blocked_questions(profile)
        assert "location" in blocked

    def test_dict_cities_blocks_location(self):
        api = RicoChatAPI()
        profile = {"cities": ["Abu Dhabi"]}
        blocked = api._get_blocked_questions(profile)
        assert "location" in blocked

    def test_skills_blocks_industry(self):
        api = RicoChatAPI()
        profile = RicoProfile(user_id="u1", skills=["python", "sql"])
        blocked = api._get_blocked_questions(profile)
        assert "industry" in blocked

    def test_empty_skills_do_not_block_industry(self):
        api = RicoChatAPI()
        profile = RicoProfile(user_id="u1", skills=[])
        blocked = api._get_blocked_questions(profile)
        assert "industry" not in blocked

    def test_industries_blocks_industry(self):
        api = RicoChatAPI()
        profile = RicoProfile(user_id="u1", industries=["technology"])
        blocked = api._get_blocked_questions(profile)
        assert "industry" in blocked

    def test_full_cv_profile_blocks_all_three(self):
        api = RicoChatAPI()
        profile = RicoProfile(
            user_id="u1",
            cv_filename="cv.pdf",
            cv_status="parsed",
            skills=["hse", "compliance"],
            years_experience=10.0,
            preferred_cities=["Dubai"],
            industries=["energy"],
        )
        blocked = api._get_blocked_questions(profile)
        assert "experience" in blocked
        assert "location" in blocked
        assert "industry" in blocked


class TestRemoveBlockedQuestions:
    """_remove_blocked_questions must strip lines containing blocked patterns."""

    def test_filters_experience_level_line(self):
        api = RicoChatAPI()
        response = "What is your experience level?\nHere are some jobs."
        result = api._remove_blocked_questions(response, ["experience"])
        assert "experience level" not in result
        assert "Here are some jobs." in result

    def test_filters_years_of_experience_line(self):
        api = RicoChatAPI()
        response = "How many years of experience do you have?\nGreat!"
        result = api._remove_blocked_questions(response, ["experience"])
        assert "years of experience" not in result

    def test_filters_location_line(self):
        api = RicoChatAPI()
        response = "What city do you prefer?\nI found jobs."
        result = api._remove_blocked_questions(response, ["location"])
        assert "city" not in result
        assert "I found jobs." in result

    def test_filters_industry_line(self):
        api = RicoChatAPI()
        response = "Which industry are you targeting?\nHere you go."
        result = api._remove_blocked_questions(response, ["industry"])
        assert "industry" not in result

    def test_no_blocked_returns_original(self):
        api = RicoChatAPI()
        response = "What type of sales?"
        result = api._remove_blocked_questions(response, [])
        assert result == response

    def test_empty_response_returns_empty(self):
        api = RicoChatAPI()
        assert api._remove_blocked_questions("", ["experience"]) == ""

    def test_multiline_filters_multiple_blocked(self):
        api = RicoChatAPI()
        response = (
            "What type of sales?\n"
            "Preferred location?\n"
            "Experience level?\n"
            "Here are matching jobs."
        )
        blocked = ["experience", "location"]
        result = api._remove_blocked_questions(response, blocked)
        assert "Experience level" not in result
        assert "Preferred location" not in result
        assert "What type of sales" in result
        assert "Here are matching jobs." in result


# ── Regression: "Find UAE jobs that match my CV" with parsed CV ───────────────

_INTERNAL_PHRASES = [
    "CV-first profile flow",
    "extract every available detail",
    "pre-fill the career profile",
    "long manual question-by-question form",
    "profile flow",
]

_FIND_JOBS_MESSAGES = [
    "Find UAE jobs that match my CV",
    "find uae jobs based on my cv",
    "search jobs using my cv",
    "find jobs that suit me",
]


class TestFindJobsWithParsedCV:
    """When a user has a parsed CV and asks to find UAE jobs, Rico must:
    - NOT return internal/technical flow text
    - Either start a job search or ask one clear question (role suggestions)
    - Never expose 'CV-first profile flow', 'extract every', etc.
    """

    def _make_api_with_parsed_cv(self, monkeypatch, target_roles=None):
        profile = MagicMock()
        profile.user_id = "test@example.com"
        profile.has_cv = True
        profile.cv_filename = "robin_cv.pdf"
        profile.cv_status = "parsed"
        profile.target_roles = target_roles if target_roles is not None else ["Environmental Manager"]
        profile.skills = ["ISO 14001", "HSE", "compliance"]
        profile.years_experience = 10
        profile.preferred_cities = ["Dubai"]
        profile.industries = ["energy"]
        profile.manual_profile_wizard_disabled = False
        profile.deal_breakers = []
        profile.nationality = ""
        profile.citizenship = ""
        api = RicoChatAPI(persist=False)
        api.memory = MagicMock()
        api.system = MagicMock()
        api.system.run_for_profile.return_value = {"matches": []}
        api.openai_agent = MagicMock()

        monkeypatch.setattr(api, "_resolve_profile", lambda _uid: profile)
        monkeypatch.setattr(api, "_resolve_pending_field", lambda *a, **kw: None)
        monkeypatch.setattr(api, "_search_jsearch_meta", lambda _role: FetchResult(items=[]))
        monkeypatch.setattr(api, "_enrich_with_role_intelligence", lambda *a, **kw: None)
        monkeypatch.setattr(
            api, "_begin_job_search_operation",
            lambda _uid, _role: {"operation_id": "op-test"},
        )
        monkeypatch.setattr("src.rico_chat_api.mark_completed", lambda *a, **kw: None)
        return api, profile

    @pytest.mark.parametrize("message", _FIND_JOBS_MESSAGES)
    def test_no_internal_phrases_in_response(self, monkeypatch, message):
        api, _ = self._make_api_with_parsed_cv(monkeypatch)
        response = api._handle_active_user("test@example.com", message)
        msg = response.get("message", "")
        for phrase in _INTERNAL_PHRASES:
            assert phrase not in msg, (
                f"Internal phrase {phrase!r} found in response to {message!r}: {msg!r}"
            )

    def test_find_uae_jobs_with_cv_triggers_job_search(self, monkeypatch):
        api, _ = self._make_api_with_parsed_cv(
            monkeypatch, target_roles=["Environmental Manager"]
        )
        response = api._handle_active_user(
            "test@example.com", "Find UAE jobs that match my CV"
        )
        assert response["type"] == "job_matches", (
            f"Expected job_matches, got {response['type']!r}. Message: {response.get('message')!r}"
        )

    def test_find_uae_jobs_search_query_is_clean_role(self, monkeypatch):
        api, _ = self._make_api_with_parsed_cv(
            monkeypatch, target_roles=["Environmental Manager"]
        )
        response = api._handle_active_user(
            "test@example.com", "Find UAE jobs that match my CV"
        )
        sq = response.get("search_query", "")
        assert "Environmental Manager" in sq or len(sq.split()) <= 5, (
            f"search_query looks like a blob: {sq!r}"
        )

    def test_find_jobs_no_target_roles_returns_suggestions(self, monkeypatch):
        """When CV is parsed but no target_roles yet, return role suggestions, not internal text."""
        api, _ = self._make_api_with_parsed_cv(monkeypatch, target_roles=[])
        response = api._handle_active_user(
            "test@example.com", "Find UAE jobs that match my CV"
        )
        msg = response.get("message", "")
        for phrase in _INTERNAL_PHRASES:
            assert phrase not in msg, (
                f"Internal phrase {phrase!r} found when no target_roles: {msg!r}"
            )
