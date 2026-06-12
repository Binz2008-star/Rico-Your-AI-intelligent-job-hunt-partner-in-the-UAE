"""
tests/test_minimum_profile_gate.py

Verifies the minimum career profile gate that prevents stale "completed"
onboarding rows from bypassing profile validation.

Coverage
--------
* evaluate_minimum_profile helper (pass / fail / edge cases)  [pure, always run]
* has_career_profile_data helper                              [pure, always run]
* GET /rico/profile profile_exists for shell users            [skipped if fastapi absent]
* POST /onboarding/submit rejects empty body (422)            [skipped if fastapi absent]
* POST /onboarding/submit gate-aware status                   [skipped if fastapi absent]
* REGRESSION: completed DB row + no career data → downgraded  [skipped if pydantic absent]
"""
from __future__ import annotations

import importlib.util
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Availability flags
# ---------------------------------------------------------------------------
_FASTAPI_OK = importlib.util.find_spec("fastapi") is not None
_PYDANTIC_OK = importlib.util.find_spec("pydantic") is not None

from src.models.onboarding import ONBOARDING_COMPLETED, ONBOARDING_IN_PROGRESS
from src.rico_agent import RicoProfile
from src.services.profile_context_resolver import (
    ProfileContext,
    evaluate_minimum_profile,
    has_career_profile_data,
    resolve_profile_context,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _ctx(**kwargs) -> ProfileContext:
    return ProfileContext(user_id="test-user", **kwargs)


def _full_profile(user_id: str = "u1") -> RicoProfile:
    """RicoProfile that passes the minimum gate."""
    return RicoProfile(
        user_id=user_id,
        target_roles=["Software Engineer"],
        preferred_cities=["Dubai"],
        years_experience=5.0,
        skills=["Python", "FastAPI"],
    )


def _shell_profile(user_id: str = "u1") -> RicoProfile:
    """Signup-shell RicoProfile — career fields all empty."""
    return RicoProfile(user_id=user_id)


# ---------------------------------------------------------------------------
# evaluate_minimum_profile — pure-function tests (always run)
# ---------------------------------------------------------------------------

class TestEvaluateMinimumProfile:
    def test_complete_profile_passes(self):
        ctx = _ctx(
            target_roles=["Data Analyst"],
            preferred_cities=["Abu Dhabi"],
            years_experience=4.0,
            skills=["SQL", "Python"],
        )
        ok, missing = evaluate_minimum_profile(ctx)
        assert ok is True
        assert missing == []

    def test_missing_target_roles_fails(self):
        ctx = _ctx(preferred_cities=["Dubai"], years_experience=2.0, skills=["Excel"])
        ok, missing = evaluate_minimum_profile(ctx)
        assert ok is False
        assert "target_roles" in missing

    def test_missing_preferred_cities_fails(self):
        ctx = _ctx(target_roles=["HR Manager"], years_experience=3.0, skills=["Recruiting"])
        ok, missing = evaluate_minimum_profile(ctx)
        assert ok is False
        assert "preferred_cities" in missing

    def test_missing_years_experience_fails(self):
        ctx = _ctx(target_roles=["UX Designer"], preferred_cities=["Sharjah"], skills=["Figma"])
        ok, missing = evaluate_minimum_profile(ctx)
        assert ok is False
        assert "years_experience" in missing

    def test_zero_years_experience_passes(self):
        """years_experience=0 is valid (fresh graduate)."""
        ctx = _ctx(
            target_roles=["Junior Developer"],
            preferred_cities=["Dubai"],
            years_experience=0.0,
            skills=["JavaScript"],
        )
        ok, missing = evaluate_minimum_profile(ctx)
        assert ok is True
        assert "years_experience" not in missing

    def test_missing_skills_and_no_cv_fails(self):
        ctx = _ctx(target_roles=["PM"], preferred_cities=["Dubai"], years_experience=5.0)
        ok, missing = evaluate_minimum_profile(ctx)
        assert ok is False
        assert "skills" in missing

    def test_cv_filename_substitutes_for_skills(self):
        """Uploaded CV (filename set) satisfies the skills-or-CV requirement."""
        ctx = _ctx(
            target_roles=["Accountant"],
            preferred_cities=["Abu Dhabi"],
            years_experience=7.0,
            cv_filename="CV_Roben.pdf",
        )
        ok, missing = evaluate_minimum_profile(ctx)
        assert ok is True
        assert "skills" not in missing

    def test_cv_status_parsed_substitutes_for_skills(self):
        """cv_status='parsed' satisfies the skills-or-CV requirement."""
        ctx = _ctx(
            target_roles=["Accountant"],
            preferred_cities=["Abu Dhabi"],
            years_experience=7.0,
            cv_status="parsed",
        )
        ok, missing = evaluate_minimum_profile(ctx)
        assert ok is True
        assert "skills" not in missing

    def test_all_missing_returns_four_fields(self):
        ctx = _ctx()
        ok, missing = evaluate_minimum_profile(ctx)
        assert ok is False
        assert set(missing) == {"target_roles", "preferred_cities", "years_experience", "skills"}


# ---------------------------------------------------------------------------
# has_career_profile_data — pure-function tests (always run)
# ---------------------------------------------------------------------------

class TestHasCareerProfileData:
    def test_empty_profile_returns_false(self):
        assert has_career_profile_data(_ctx()) is False

    def test_target_roles_alone_returns_true(self):
        assert has_career_profile_data(_ctx(target_roles=["Engineer"])) is True

    def test_years_experience_zero_returns_true(self):
        assert has_career_profile_data(_ctx(years_experience=0.0)) is True

    def test_cv_filename_returns_true(self):
        assert has_career_profile_data(_ctx(cv_filename="my_cv.pdf")) is True

    def test_cv_status_returns_true(self):
        assert has_career_profile_data(_ctx(cv_status="parsed")) is True

    def test_shell_profile_resolved_returns_false(self):
        """Signup-shell RicoProfile → has_career_profile_data=False."""
        ctx = resolve_profile_context("u1", _shell_profile())
        assert has_career_profile_data(ctx) is False

    def test_full_profile_resolved_returns_true(self):
        ctx = resolve_profile_context("u1", _full_profile())
        assert has_career_profile_data(ctx) is True


# ---------------------------------------------------------------------------
# Gate integration: verify evaluate_minimum_profile correctly classifies
# known user shapes (always run — pure service layer, no HTTP)
# ---------------------------------------------------------------------------

class TestGateIntegration:
    """These tests verify the gate at the service boundary — no HTTP needed."""

    def test_shell_user_fails_gate(self):
        ctx = resolve_profile_context("u1", _shell_profile())
        ok, missing = evaluate_minimum_profile(ctx)
        assert ok is False
        assert len(missing) == 4

    def test_full_user_passes_gate(self):
        ctx = resolve_profile_context("u1", _full_profile())
        ok, missing = evaluate_minimum_profile(ctx)
        assert ok is True
        assert missing == []

    def test_cv_user_no_explicit_skills_passes_gate(self):
        """User with CV filename but no skills list passes skills-or-CV."""
        cv_profile = RicoProfile(
            user_id="u1",
            target_roles=["Finance Manager"],
            preferred_cities=["Dubai"],
            years_experience=8.0,
            cv_filename="John_Finance_CV.pdf",
        )
        ctx = resolve_profile_context("u1", cv_profile)
        ok, missing = evaluate_minimum_profile(ctx)
        assert ok is True
        assert "skills" not in missing

    def test_fresh_graduate_zero_experience_passes(self):
        profile = RicoProfile(
            user_id="u1",
            target_roles=["Graduate Engineer"],
            preferred_cities=["Dubai"],
            years_experience=0.0,
            skills=["Python"],
        )
        ctx = resolve_profile_context("u1", profile)
        ok, missing = evaluate_minimum_profile(ctx)
        assert ok is True


# ---------------------------------------------------------------------------
# HTTP-layer tests — skipped when fastapi is not installed
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _FASTAPI_OK, reason="fastapi not installed in this environment")
class TestProfileExistsEndpoint:
    def _invoke(self, profile_obj, user_id: str = "u@test.com") -> dict:
        from src.api.routers.rico_chat import rico_get_profile

        mock_request = MagicMock()
        with patch("src.api.routers.rico_chat.get_profile", return_value=profile_obj), \
             patch("src.api.routers.rico_chat.get_current_user",
                   return_value={"email": user_id, "role": "user"}):
            result = rico_get_profile(mock_request)
        return result.dict() if hasattr(result, "dict") else result.__dict__

    def test_shell_profile_returns_profile_exists_false(self):
        data = self._invoke(_shell_profile("u@test.com"), "u@test.com")
        assert data["profile_exists"] is False

    def test_null_profile_returns_profile_exists_false(self):
        data = self._invoke(None, "u@test.com")
        assert data["profile_exists"] is False


@pytest.mark.skipif(not _FASTAPI_OK, reason="fastapi not installed in this environment")
class TestOnboardingSubmitEndpoint:
    def _invoke(self, body_dict: dict, profile_return, user_id: str = "u@test.com"):
        from fastapi import HTTPException
        from src.api.routers.onboarding import OnboardingSubmitRequest, onboarding_submit

        body = OnboardingSubmitRequest(**body_dict)
        mock_request = MagicMock()
        # upsert_profile and get_profile are lazy-imported inside onboarding_submit
        # from src.repositories.profile_repo — patch at the source module so the
        # local import picks up the mock regardless of import order.
        # set_onboarding_status is lazy-imported from src.repositories.onboarding_repo.
        with patch("src.api.routers.onboarding.get_current_user",
                   return_value={"email": user_id, "role": "user"}), \
             patch("src.repositories.profile_repo.upsert_profile", return_value=MagicMock()), \
             patch("src.repositories.profile_repo.get_profile", return_value=profile_return), \
             patch("src.repositories.onboarding_repo.set_onboarding_status") as mock_status:
            try:
                result = onboarding_submit(mock_request, body)
                return result, mock_status
            except HTTPException as exc:
                return exc, mock_status

    def test_empty_body_returns_422(self):
        from fastapi import HTTPException
        exc, _ = self._invoke({}, _shell_profile())
        assert isinstance(exc, HTTPException)
        assert exc.status_code == 422

    def test_partial_submit_returns_in_progress(self):
        partial = RicoProfile(user_id="u@test.com", target_roles=["Engineer"])
        result, mock_status = self._invoke({"target_roles": ["Engineer"]}, partial)
        assert result["status"] == ONBOARDING_IN_PROGRESS
        assert len(result["missing_fields"]) > 0
        mock_status.assert_called_once_with("u@test.com", ONBOARDING_IN_PROGRESS)

    def test_complete_submit_returns_completed(self):
        result, mock_status = self._invoke(
            {
                "target_roles": ["Software Engineer"],
                "preferred_cities": ["Dubai"],
                "years_experience": 5.0,
                "skills": ["Python", "FastAPI"],
            },
            _full_profile("u@test.com"),
        )
        assert result["status"] == ONBOARDING_COMPLETED
        assert result["missing_fields"] == []
        mock_status.assert_called_once_with("u@test.com", ONBOARDING_COMPLETED)


# ---------------------------------------------------------------------------
# REGRESSION: stale "completed" row bypasses gate — skipped if pydantic absent
#
# These tests verify the chat _process_message_inner gate check.
# They require pydantic (via the rico_chat_api import chain).
# When pydantic IS available, they must all pass.
# ---------------------------------------------------------------------------

def _make_api_if_possible():
    """Import RicoChatAPI, or raise SkipTest if dependencies are missing."""
    try:
        from src.rico_chat_api import RicoChatAPI
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.skip(f"rico_chat_api unavailable ({exc})")
    api = RicoChatAPI.__new__(RicoChatAPI)
    api.memory = MagicMock()
    api.agent = MagicMock()
    api.system = MagicMock()
    api.memory.load_profile.return_value = MagicMock()
    api.system.run_for_profile.return_value = {"matches": []}
    return api


class TestCompletedRowBypassRegression:
    def test_completed_db_no_career_data_job_search_is_downgraded(self):
        """
        Shell user (status='completed', no career data) asks for a job search.
        Gate fires because the message requires career matching:
          1. detect the gate failure
          2. call set_onboarding_status(in_progress)
          3. return type='onboarding' with missing_fields
          4. NOT call _handle_active_user
        """
        api = _make_api_if_possible()
        shell = _shell_profile("stale-user")

        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch("src.rico_chat_api.get_profile", return_value=shell), \
             patch("src.rico_chat_api.set_onboarding_status") as mock_set, \
             patch.object(api, "_handle_active_user") as mock_active:
            response = api.process_message("stale-user", "find me a job")

        assert response["type"] == "onboarding", (
            "Expected onboarding downgrade for job search from shell user, got: "
            + response.get("type", "<none>")
        )
        assert "missing_fields" in response
        assert len(response["missing_fields"]) > 0
        mock_set.assert_called_once_with("stale-user", ONBOARDING_IN_PROGRESS)
        mock_active.assert_not_called()

    def test_completed_db_no_career_data_hello_routes_to_active(self):
        """
        Shell user (status='completed', no career data) says 'hello'.
        Gate must NOT fire — Rico stays conversational for non-job-search messages.
        """
        api = _make_api_if_possible()
        shell = _shell_profile("stale-user-hello")

        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch("src.rico_chat_api.get_profile", return_value=shell), \
             patch("src.rico_chat_api.set_onboarding_status") as mock_set, \
             patch.object(api, "_handle_active_user",
                          return_value={"type": "clarification", "message": "Hi!"}) as mock_active:
            response = api.process_message("stale-user-hello", "hello")

        assert response["type"] != "onboarding", (
            "Gate must not fire for 'hello' — Rico should not be a form bot"
        )
        mock_active.assert_called_once()
        mock_set.assert_not_called()

    def test_completed_db_with_full_career_data_routes_to_active(self):
        """
        User has status='completed' AND valid career data — routes to active-user
        flow, not onboarding.
        """
        api = _make_api_if_possible()
        full = _full_profile("active-user")

        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch("src.rico_chat_api.get_profile", return_value=full), \
             patch("src.rico_chat_api.set_onboarding_status") as mock_set, \
             patch.object(api, "_handle_active_user",
                          return_value={"type": "options", "options": []}) as mock_active:
            response = api.process_message("active-user", "what's next?")

        assert response["type"] != "onboarding"
        mock_active.assert_called_once()
        mock_set.assert_not_called()

    def test_completed_db_cv_only_no_skills_routes_to_active(self):
        """
        CV filename present (no explicit skills list) satisfies the
        skills-or-CV requirement — must NOT trigger a downgrade.
        """
        api = _make_api_if_possible()
        cv_profile = RicoProfile(
            user_id="cv-user",
            target_roles=["Finance Manager"],
            preferred_cities=["Dubai"],
            years_experience=8.0,
            cv_filename="John_Finance_CV.pdf",
        )

        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch("src.rico_chat_api.get_profile", return_value=cv_profile), \
             patch("src.rico_chat_api.set_onboarding_status") as mock_set, \
             patch.object(api, "_handle_active_user",
                          return_value={"type": "options", "options": []}) as mock_active:
            response = api.process_message("cv-user", "find me jobs")

        assert response["type"] != "onboarding"
        mock_active.assert_called_once()
        mock_set.assert_not_called()

    def test_completed_db_partial_profile_missing_required_fields_is_downgraded(self):
        """
        User has status='completed' AND some career data (current_role is set, so
        has_career_profile_data would return True).  But evaluate_minimum_profile
        fails because target_roles, preferred_cities, years_experience, and skills
        are all absent.

        The strict gate must downgrade to in_progress — not route to active user.
        This distinguishes evaluate_minimum_profile (4-field check) from the weaker
        has_career_profile_data (any-field check).
        """
        api = _make_api_if_possible()
        partial = RicoProfile(
            user_id="partial-user",
            current_role="Software Engineer",  # has_career_profile_data=True
            # All minimum gate fields absent: no target_roles, preferred_cities,
            # years_experience, skills, or CV evidence
        )

        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch("src.rico_chat_api.get_profile", return_value=partial), \
             patch("src.rico_chat_api.set_onboarding_status") as mock_set, \
             patch.object(api, "_handle_active_user") as mock_active:
            response = api.process_message("partial-user", "find me a job")

        assert response["type"] == "onboarding", (
            "Expected downgrade for partial profile, got: " + response.get("type", "<none>")
        )
        assert "missing_fields" in response
        assert set(response["missing_fields"]) == {
            "target_roles", "preferred_cities", "years_experience", "skills"
        }
        mock_set.assert_called_once_with("partial-user", ONBOARDING_IN_PROGRESS)
        mock_active.assert_not_called()

    def test_completed_partial_profile_missing_cities_hello_routes_to_active(self):
        """
        User with status='completed', has target_roles/skills/years_experience but
        missing preferred_cities.  Saying 'hello' must NOT fire the gate —
        Rico answers conversationally, not as a form bot.
        """
        api = _make_api_if_possible()
        partial = RicoProfile(
            user_id="partial-cities",
            target_roles=["HSE Manager"],
            years_experience=5.0,
            skills=["NEBOSH"],
            # preferred_cities intentionally absent
        )

        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch("src.rico_chat_api.get_profile", return_value=partial), \
             patch("src.rico_chat_api.set_onboarding_status") as mock_set, \
             patch.object(api, "_handle_active_user",
                          return_value={"type": "clarification", "message": "Hi!"}) as mock_active:
            response = api.process_message("partial-cities", "hello")

        assert response["type"] != "onboarding", (
            "Gate must not fire for 'hello' even when preferred_cities is missing"
        )
        mock_active.assert_called_once()
        mock_set.assert_not_called()

    def test_completed_partial_profile_missing_cities_job_search_is_downgraded(self):
        """
        Same partial profile but user asks to find jobs.
        Gate fires because the message requires career matching.
        """
        api = _make_api_if_possible()
        partial = RicoProfile(
            user_id="partial-cities-search",
            target_roles=["HSE Manager"],
            years_experience=5.0,
            skills=["NEBOSH"],
            # preferred_cities intentionally absent
        )

        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch("src.rico_chat_api.get_profile", return_value=partial), \
             patch("src.rico_chat_api.set_onboarding_status") as mock_set, \
             patch.object(api, "_handle_active_user") as mock_active:
            response = api.process_message("partial-cities-search", "find jobs that match my CV")

        assert response["type"] == "onboarding"
        assert "preferred_cities" in response.get("missing_fields", [])
        mock_set.assert_called_once_with("partial-cities-search", ONBOARDING_IN_PROGRESS)
        mock_active.assert_not_called()

    def test_arabic_job_search_with_missing_fields_returns_arabic_prompt(self):
        """Arabic job-search request with missing profile fields → Arabic missing-fields prompt."""
        api = _make_api_if_possible()
        shell = _shell_profile("ar-user")

        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch("src.rico_chat_api.get_profile", return_value=shell), \
             patch("src.rico_chat_api.set_onboarding_status"):
            response = api.process_message("ar-user", "دورلي على وظائف تناسب خبرتي")

        assert response["type"] == "onboarding"
        assert "missing_fields" in response
        msg = response.get("message", "")
        assert any(ord(c) > 0x600 for c in msg), "Expected Arabic characters in downgrade message"

    def test_downgrade_is_bilingual_for_arabic_job_search(self):
        """Arabic job-search (not greeting) with missing fields → Arabic prompt."""
        api = _make_api_if_possible()
        shell = _shell_profile("ar-user-2")

        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch("src.rico_chat_api.get_profile", return_value=shell), \
             patch("src.rico_chat_api.set_onboarding_status"):
            response = api.process_message("ar-user-2", "ابحث عن وظائف")

        assert response["type"] == "onboarding"
        assert "missing_fields" in response
        msg = response.get("message", "")
        assert any(ord(c) > 0x600 for c in msg), "Expected Arabic characters in downgrade message"
