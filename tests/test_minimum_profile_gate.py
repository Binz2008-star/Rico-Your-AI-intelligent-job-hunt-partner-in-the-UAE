"""
tests/test_minimum_profile_gate.py

Onboarding completion must be gated on a minimum career profile, never on
the mere existence of a rico_users shell row created at signup.

Covers:
  - evaluate_minimum_profile / has_career_profile_data helpers
  - GET /api/v1/rico/profile: signup shell row → profile_exists=False
  - POST /api/v1/onboarding/submit: empty rejected, partial → in_progress,
    complete → completed
All DB / repo calls are patched — no real database required.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.rico_agent import RicoProfile
from src.services.profile_context_resolver import (
    ProfileContext,
    evaluate_minimum_profile,
    has_career_profile_data,
    resolve_profile_context,
)

_USER = {"email": "vishnu@example.com", "role": "user"}


def _shell_profile(user_id: str = "vishnu@example.com") -> RicoProfile:
    """What get_profile() returns for a web signup that never onboarded:
    a rico_users row with name/email but zero career data."""
    return RicoProfile(user_id=user_id, name="Vishnu Santhosh", email=user_id)


def _complete_profile(user_id: str = "vishnu@example.com") -> RicoProfile:
    return RicoProfile(
        user_id=user_id,
        name="Vishnu Santhosh",
        email=user_id,
        target_roles=["HSE Officer"],
        preferred_cities=["Dubai"],
        years_experience=4,
        skills=["nebosh", "risk assessment"],
    )


# ── Helper unit tests ─────────────────────────────────────────────────────────

class TestEvaluateMinimumProfile:
    def test_shell_profile_is_incomplete_with_all_fields_missing(self):
        ctx = resolve_profile_context("u1", _shell_profile())
        complete, missing = evaluate_minimum_profile(ctx)
        assert complete is False
        assert set(missing) == {
            "target_roles", "preferred_cities", "years_experience", "skills",
        }

    def test_none_profile_is_incomplete(self):
        complete, missing = evaluate_minimum_profile(resolve_profile_context("u1", None))
        assert complete is False
        assert len(missing) == 4

    def test_partial_profile_reports_remaining_fields(self):
        ctx = ProfileContext(user_id="u1", target_roles=["HSE Officer"], skills=["nebosh"])
        complete, missing = evaluate_minimum_profile(ctx)
        assert complete is False
        assert set(missing) == {"preferred_cities", "years_experience"}

    def test_complete_profile_with_skills(self):
        ctx = resolve_profile_context("u1", _complete_profile())
        complete, missing = evaluate_minimum_profile(ctx)
        assert complete is True
        assert missing == []

    def test_cv_substitutes_for_skills(self):
        ctx = ProfileContext(
            user_id="u1",
            target_roles=["HSE Officer"],
            preferred_cities=["Dubai"],
            years_experience=4.0,
            cv_status="parsed",
        )
        complete, missing = evaluate_minimum_profile(ctx)
        assert complete is True
        assert missing == []

    def test_zero_years_experience_counts_as_present(self):
        ctx = ProfileContext(
            user_id="u1",
            target_roles=["HSE Officer"],
            preferred_cities=["Dubai"],
            years_experience=0.0,
            skills=["nebosh"],
        )
        complete, _ = evaluate_minimum_profile(ctx)
        assert complete is True


class TestHasCareerProfileData:
    def test_shell_row_has_no_career_data(self):
        ctx = resolve_profile_context("u1", _shell_profile())
        assert has_career_profile_data(ctx) is False

    def test_none_profile_has_no_career_data(self):
        assert has_career_profile_data(resolve_profile_context("u1", None)) is False

    def test_any_career_field_counts(self):
        assert has_career_profile_data(ProfileContext(user_id="u1", skills=["python"])) is True
        assert has_career_profile_data(ProfileContext(user_id="u1", cv_filename="cv.pdf")) is True
        assert has_career_profile_data(ProfileContext(user_id="u1", years_experience=2.0)) is True


# ── GET /api/v1/rico/profile ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    return TestClient(app, raise_server_exceptions=False)


class TestProfileExistsSemantics:
    def test_signup_shell_row_returns_profile_exists_false(self, client):
        with patch("src.api.routers.rico_chat.get_current_user", return_value=_USER), \
             patch("src.api.routers.rico_chat.get_profile", return_value=_shell_profile()):
            r = client.get("/api/v1/rico/profile")
        assert r.status_code == 200
        body = r.json()
        assert body["profile_exists"] is False
        assert body["email"] == _USER["email"]

    def test_missing_profile_returns_profile_exists_false(self, client):
        with patch("src.api.routers.rico_chat.get_current_user", return_value=_USER), \
             patch("src.api.routers.rico_chat.get_profile", return_value=None):
            r = client.get("/api/v1/rico/profile")
        assert r.status_code == 200
        assert r.json()["profile_exists"] is False

    def test_real_career_profile_returns_profile_exists_true(self, client):
        mock_ctx = MagicMock()
        mock_ctx.completeness_score = 0.7
        with patch("src.api.routers.rico_chat.get_current_user", return_value=_USER), \
             patch("src.api.routers.rico_chat.get_profile", return_value=_complete_profile()), \
             patch("src.agent.context.resolver.resolve_profile_context", return_value=mock_ctx):
            r = client.get("/api/v1/rico/profile")
        assert r.status_code == 200
        body = r.json()
        assert body["profile_exists"] is True
        assert body["target_roles"] == ["HSE Officer"]


# ── POST /api/v1/onboarding/submit ────────────────────────────────────────────

class TestOnboardingSubmit:
    def test_empty_submission_rejected(self, client):
        with patch("src.api.routers.onboarding.get_current_user", return_value=_USER), \
             patch("src.repositories.profile_repo.upsert_profile") as mock_upsert:
            r = client.post("/api/v1/onboarding/submit", json={})
        assert r.status_code == 422
        mock_upsert.assert_not_called()

    def test_partial_submission_marks_in_progress(self, client):
        with patch("src.api.routers.onboarding.get_current_user", return_value=_USER), \
             patch("src.repositories.profile_repo.upsert_profile") as mock_upsert, \
             patch("src.repositories.profile_repo.get_profile",
                   return_value=RicoProfile(user_id=_USER["email"], target_roles=["HSE Officer"])), \
             patch("src.repositories.onboarding_repo.set_onboarding_status") as mock_set, \
             patch("src.repositories.onboarding_repo.mark_onboarding_complete") as mock_complete:
            r = client.post(
                "/api/v1/onboarding/submit",
                json={"target_roles": ["HSE Officer"]},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "in_progress"
        assert set(body["missing_fields"]) == {"preferred_cities", "years_experience", "skills"}
        assert body["profile_exists"] is True
        mock_upsert.assert_called_once()
        mock_set.assert_called_once_with(_USER["email"], "in_progress")
        mock_complete.assert_not_called()

    def test_complete_submission_marks_completed(self, client):
        with patch("src.api.routers.onboarding.get_current_user", return_value=_USER), \
             patch("src.repositories.profile_repo.upsert_profile") as mock_upsert, \
             patch("src.repositories.profile_repo.get_profile", return_value=_complete_profile()), \
             patch("src.repositories.onboarding_repo.set_onboarding_status") as mock_set, \
             patch("src.repositories.onboarding_repo.mark_onboarding_complete") as mock_complete:
            r = client.post(
                "/api/v1/onboarding/submit",
                json={
                    "target_roles": ["HSE Officer"],
                    "preferred_cities": ["Dubai"],
                    "years_experience": 4,
                    "skills": ["nebosh", "risk assessment"],
                },
            )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "completed"
        assert body["missing_fields"] == []
        assert body["profile_exists"] is True
        mock_upsert.assert_called_once()
        mock_complete.assert_called_once_with(_USER["email"])
        mock_set.assert_not_called()
