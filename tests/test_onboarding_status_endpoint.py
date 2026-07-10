"""
tests/test_onboarding_status_endpoint.py

Tests for the read-only GET /api/v1/onboarding/status endpoint.

The endpoint exposes the *canonical* onboarding-completion signal:
  * persisted rico_onboarding_states status is the primary signal
  * the backend minimum-profile gate is the canonical readiness evaluation
  * profile_exists alone is NOT a completion signal

Legacy / merged-guest compatibility (no persisted row):
  * gate passes → complete, source "derived_legacy"
  * gate fails  → incomplete, source "derived_legacy"

All DB / repo calls are patched — no real database required.
The handler is invoked directly (no HTTP transport) with a mocked request,
mirroring tests/test_minimum_profile_gate.py::TestOnboardingSubmitEndpoint.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_FASTAPI_OK = importlib.util.find_spec("fastapi") is not None

from src.models.onboarding import (
    ONBOARDING_COMPLETED,
    ONBOARDING_IN_PROGRESS,
    ONBOARDING_PENDING,
    OnboardingState,
)
from src.repositories.onboarding_repo import OnboardingStateUnavailable
from src.rico_agent import RicoProfile


# ── Helpers ───────────────────────────────────────────────────────────────────

def _full_profile(user_id: str = "u@test.com") -> RicoProfile:
    """RicoProfile that passes the minimum gate."""
    return RicoProfile(
        user_id=user_id,
        target_roles=["Software Engineer"],
        preferred_cities=["Dubai"],
        years_experience=5.0,
        skills=["Python", "FastAPI"],
    )


def _partial_profile(user_id: str = "u@test.com") -> RicoProfile:
    """Has *some* career data (profile_exists True) but fails the minimum gate."""
    return RicoProfile(user_id=user_id, target_roles=["Engineer"])


def _shell_profile(user_id: str = "u@test.com") -> RicoProfile:
    """Signup shell — no career data at all."""
    return RicoProfile(user_id=user_id)


def _state(status: str, user_id: str = "u@test.com") -> OnboardingState:
    return OnboardingState(user_id=user_id, status=status)


@pytest.mark.skipif(not _FASTAPI_OK, reason="fastapi not installed in this environment")
class TestOnboardingStatusEndpoint:
    def _invoke(
        self,
        *,
        state,
        profile,
        user_id: str = "u@test.com",
        profile_raises: bool = False,
        state_raises: bool = False,
        authed: bool = True,
    ):
        """Invoke onboarding_status with repo/profile dependencies mocked.

        Returns the dict payload, or the raised HTTPException.
        """
        from fastapi import HTTPException
        from src.api.routers.onboarding import onboarding_status

        mock_request = MagicMock()

        if authed:
            user_patch = patch(
                "src.api.routers.onboarding.get_current_user",
                return_value={"email": user_id, "role": "user"},
            )
        else:
            user_patch = patch(
                "src.api.routers.onboarding.get_current_user",
                side_effect=HTTPException(status_code=401, detail="Not authenticated"),
            )

        state_mock = (
            MagicMock(side_effect=OnboardingStateUnavailable("boom: onboarding db down"))
            if state_raises
            else MagicMock(return_value=state)
        )
        get_profile_mock = (
            MagicMock(side_effect=RuntimeError("boom: internal db failure"))
            if profile_raises
            else MagicMock(return_value=profile)
        )

        # get_onboarding_state_readonly and get_profile are lazy-imported inside
        # the handler from their source modules — patch at the source so the
        # local import picks up the mock regardless of import order.
        with user_patch, \
             patch("src.repositories.onboarding_repo.get_onboarding_state_readonly",
                   state_mock), \
             patch("src.repositories.profile_repo.get_profile", get_profile_mock):
            try:
                return onboarding_status(mock_request)
            except HTTPException as exc:
                return exc

    # ── persisted states ───────────────────────────────────────────────────

    def test_persisted_pending_is_incomplete(self):
        result = self._invoke(state=_state(ONBOARDING_PENDING), profile=_shell_profile())
        assert result["status"] == ONBOARDING_PENDING
        assert result["complete"] is False
        assert result["source"] == "persisted"

    def test_persisted_in_progress_is_incomplete(self):
        result = self._invoke(
            state=_state(ONBOARDING_IN_PROGRESS), profile=_partial_profile()
        )
        assert result["status"] == ONBOARDING_IN_PROGRESS
        assert result["complete"] is False
        assert result["source"] == "persisted"

    def test_persisted_completed_is_complete(self):
        result = self._invoke(state=_state(ONBOARDING_COMPLETED), profile=_full_profile())
        assert result["status"] == ONBOARDING_COMPLETED
        assert result["complete"] is True
        assert result["source"] == "persisted"
        assert result["missing_fields"] == []

    def test_persisted_completed_wins_over_thin_profile(self):
        """A real completed record is authoritative even if the profile later
        thinned out — the user is not forced back through onboarding."""
        result = self._invoke(
            state=_state(ONBOARDING_COMPLETED), profile=_partial_profile()
        )
        assert result["status"] == ONBOARDING_COMPLETED
        assert result["complete"] is True
        assert result["source"] == "persisted"

    # ── derived_legacy (no persisted row) ──────────────────────────────────

    def test_no_row_complete_legacy_profile_is_complete(self):
        result = self._invoke(state=None, profile=_full_profile())
        assert result["complete"] is True
        assert result["status"] == ONBOARDING_COMPLETED
        assert result["source"] == "derived_legacy"
        assert result["missing_fields"] == []
        assert result["profile_exists"] is True

    def test_no_row_incomplete_partial_profile_is_incomplete(self):
        result = self._invoke(state=None, profile=_partial_profile())
        assert result["complete"] is False
        assert result["status"] == ONBOARDING_IN_PROGRESS
        assert result["source"] == "derived_legacy"
        assert result["profile_exists"] is True
        assert len(result["missing_fields"]) > 0

    def test_no_row_shell_profile_is_pending(self):
        result = self._invoke(state=None, profile=_shell_profile())
        assert result["complete"] is False
        assert result["status"] == ONBOARDING_PENDING
        assert result["source"] == "derived_legacy"
        assert result["profile_exists"] is False

    def test_guest_merged_complete_profile_is_complete(self):
        """A successfully-merged guest arrives with a complete profile but no
        persisted onboarding row — must be treated as complete, not re-onboarded."""
        merged = RicoProfile(
            user_id="merged@test.com",
            target_roles=["Data Analyst"],
            preferred_cities=["Abu Dhabi"],
            years_experience=3.0,
            cv_filename="merged_cv.pdf",  # CV evidence substitutes for skills
        )
        result = self._invoke(state=None, profile=merged, user_id="merged@test.com")
        assert result["complete"] is True
        assert result["status"] == ONBOARDING_COMPLETED
        assert result["source"] == "derived_legacy"

    # ── auth + failure semantics ────────────────────────────────────────────

    def test_unauthenticated_request_rejected(self):
        from fastapi import HTTPException
        result = self._invoke(state=None, profile=_full_profile(), authed=False)
        assert isinstance(result, HTTPException)
        assert result.status_code == 401

    def test_status_read_failure_does_not_expose_internals(self):
        from fastapi import HTTPException
        result = self._invoke(state=None, profile=_full_profile(), profile_raises=True)
        assert isinstance(result, HTTPException)
        assert result.status_code == 503
        # The generic message must not leak the underlying error text.
        assert "boom" not in str(result.detail).lower()
        assert "db failure" not in str(result.detail).lower()

    def test_state_read_failure_returns_generic_503(self):
        """An onboarding-state read failure (DB down / query error) → sanitized 503."""
        from fastapi import HTTPException
        result = self._invoke(state=None, profile=_full_profile(), state_raises=True)
        assert isinstance(result, HTTPException)
        assert result.status_code == 503

    def test_state_read_failure_does_not_fall_through_to_derived_legacy(self):
        """A state-read failure must NOT be misclassified as derived_legacy.

        The profile here would pass the gate — if the endpoint fell through it
        would wrongly return complete/derived_legacy. It must 503 instead.
        """
        from fastapi import HTTPException
        result = self._invoke(state=None, profile=_full_profile(), state_raises=True)
        assert isinstance(result, HTTPException)
        assert result.status_code == 503
        # Definitely not a success payload.
        assert not isinstance(result, dict)

    def test_state_read_failure_hides_internals(self):
        result = self._invoke(state=None, profile=_full_profile(), state_raises=True)
        detail = str(getattr(result, "detail", "")).lower()
        assert "boom" not in detail
        assert "db down" not in detail

    def test_read_only_never_writes_status(self):
        """A GET must not backfill / mutate onboarding status.

        (DDL/commit/mutation-free reads are proven at the repository level in
        tests/test_onboarding_repo_readonly.py; here we assert the endpoint
        never triggers a status write.)
        """
        with patch("src.repositories.onboarding_repo.set_onboarding_status") as mock_set:
            self._invoke(state=None, profile=_full_profile())
        mock_set.assert_not_called()

    def test_response_exposes_no_profile_content(self):
        """Only status + derived booleans + missing field *names* are returned —
        never profile values (name/email/skills/etc.)."""
        result = self._invoke(state=_state(ONBOARDING_COMPLETED), profile=_full_profile())
        assert set(result.keys()) == {
            "status",
            "complete",
            "source",
            "missing_fields",
            "profile_exists",
            "profile_completeness",
        }


# ── submit persistence semantics (gate-driven completed vs in_progress) ───────

@pytest.mark.skipif(not _FASTAPI_OK, reason="fastapi not installed in this environment")
class TestOnboardingSubmitPersistsGateAwareStatus:
    """submit persists 'completed' only when the minimum gate passes, and
    'in_progress' when it fails. (Companion coverage to the status endpoint.)"""

    def _invoke(self, body_dict: dict, profile_return, user_id: str = "u@test.com"):
        from fastapi import HTTPException
        from src.api.routers.onboarding import OnboardingSubmitRequest, onboarding_submit

        body = OnboardingSubmitRequest(**body_dict)
        mock_request = MagicMock()
        with patch("src.api.routers.onboarding.get_current_user",
                   return_value={"email": user_id, "role": "user"}), \
             patch("src.repositories.profile_repo.upsert_profile", return_value=MagicMock()), \
             patch("src.repositories.profile_repo.get_profile", return_value=profile_return), \
             patch("src.repositories.onboarding_repo.set_onboarding_status") as mock_status:
            try:
                return onboarding_submit(mock_request, body), mock_status
            except HTTPException as exc:
                return exc, mock_status

    def test_submit_persists_completed_only_when_gate_passes(self):
        result, mock_status = self._invoke(
            {
                "target_roles": ["Software Engineer"],
                "preferred_cities": ["Dubai"],
                "years_experience": 5.0,
                "skills": ["Python", "FastAPI"],
            },
            _full_profile(),
        )
        assert result["status"] == ONBOARDING_COMPLETED
        mock_status.assert_called_once_with("u@test.com", ONBOARDING_COMPLETED)

    def test_submit_persists_in_progress_when_gate_fails(self):
        result, mock_status = self._invoke(
            {"target_roles": ["Engineer"]},
            _partial_profile(),
        )
        assert result["status"] == ONBOARDING_IN_PROGRESS
        mock_status.assert_called_once_with("u@test.com", ONBOARDING_IN_PROGRESS)
