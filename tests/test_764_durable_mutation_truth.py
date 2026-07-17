"""Durable mutation truth (#764).

User-directed profile / onboarding / settings writes must persist to the
canonical database or fail the request with a retryable non-2xx. A swallowed DB
failure must never produce a 2xx "saved/updated/completed" claim, and a failed
mandatory write must leave no phantom state in the process-local mirror.

All DB access is mocked — no real database is touched.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from src.api.rate_limit import limiter
    limiter.reset()
    yield


def _auth(monkeypatch, user_id: str):
    import src.api.routers.rico_chat as rico_chat_router

    def mock_get_user(request):
        user = {"email": user_id, "role": "user"}
        request.state.current_user = user
        request.state.user_id = user_id
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", mock_get_user)


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/v1/rico/profile
# ─────────────────────────────────────────────────────────────────────────────

class TestProfilePatchDurable:
    def test_patch_passes_require_db(self, monkeypatch):
        import src.api.routers.rico_chat as rico_chat_router

        _auth(monkeypatch, "durable-a@test.com")
        captured = {}

        def spy_upsert(user_id, updates, **kwargs):
            captured["require_db"] = kwargs.get("require_db")
            return MagicMock()

        monkeypatch.setattr(rico_chat_router, "upsert_profile", spy_upsert)
        monkeypatch.setattr(rico_chat_router, "_profile_updates_visible", lambda *a, **k: True)

        client = TestClient(app)
        r = client.patch("/api/v1/rico/profile", json={"current_role": "HSE Lead"})
        assert r.status_code == 200
        assert captured["require_db"] is True

    def test_patch_returns_503_when_persistence_fails(self, monkeypatch):
        import src.api.routers.rico_chat as rico_chat_router

        _auth(monkeypatch, "durable-b@test.com")

        def failing_upsert(user_id, updates, **kwargs):
            raise RuntimeError("profile DB unavailable (require_db)")

        monkeypatch.setattr(rico_chat_router, "upsert_profile", failing_upsert)

        client = TestClient(app)
        r = client.patch("/api/v1/rico/profile", json={"current_role": "HSE Lead"})
        assert r.status_code == 503
        body = r.json()
        assert "status" not in body or body.get("status") != "ok"


# ─────────────────────────────────────────────────────────────────────────────
# profile_repo.upsert_profile — no phantom mirror state on mandatory writes
# ─────────────────────────────────────────────────────────────────────────────

class TestNoPhantomMirrorState:
    def test_require_db_failure_does_not_mutate_mirror(self, monkeypatch):
        """DB unavailable + require_db=True → raise AND mirror untouched."""
        from src.repositories import profile_repo

        user_id = "phantom-check@test.com"
        marker_role = "Phantom Role That Must Not Persist"

        monkeypatch.setattr(profile_repo, "_db", lambda: None)

        with pytest.raises(RuntimeError):
            profile_repo.upsert_profile(
                user_id, {"current_role": marker_role}, require_db=True
            )

        mirrored = profile_repo._memory().load_profile(user_id)
        assert mirrored is None or getattr(mirrored, "current_role", None) != marker_role

    def test_require_db_write_failure_does_not_mutate_mirror(self, monkeypatch):
        """DB write raises + require_db=True → raise AND mirror untouched."""
        from contextlib import contextmanager

        from src.repositories import profile_repo

        user_id = "phantom-check-2@test.com"
        marker_role = "Phantom Role After Failed Txn"

        fake_db = MagicMock()
        fake_db.get_user_bundle.side_effect = RuntimeError("txn failed")
        monkeypatch.setattr(profile_repo, "_db", lambda: fake_db)

        @contextmanager
        def fake_txn():
            yield MagicMock()

        monkeypatch.setattr(profile_repo, "_db_transaction", fake_txn)

        with pytest.raises(RuntimeError):
            profile_repo.upsert_profile(
                user_id, {"current_role": marker_role}, require_db=True
            )

        mirrored = profile_repo._memory().load_profile(user_id)
        assert mirrored is None or getattr(mirrored, "current_role", None) != marker_role

    def test_require_db_success_updates_mirror_after_commit(self, monkeypatch):
        """DB commit succeeds + require_db=True → mirror reflects the update."""
        from contextlib import contextmanager

        from src.repositories import profile_repo

        user_id = "committed-check@test.com"
        marker_role = "Committed Role"

        fake_db = MagicMock()
        fake_db.get_user_bundle.return_value = None
        fake_db.upsert_user.return_value = {"id": "42"}
        monkeypatch.setattr(profile_repo, "_db", lambda: fake_db)

        @contextmanager
        def fake_txn():
            yield MagicMock()

        monkeypatch.setattr(profile_repo, "_db_transaction", fake_txn)

        result = profile_repo.upsert_profile(
            user_id, {"current_role": marker_role}, require_db=True
        )
        assert getattr(result, "current_role", None) == marker_role

        mirrored = profile_repo._memory().load_profile(user_id)
        assert getattr(mirrored, "current_role", None) == marker_role

    def test_default_path_keeps_mirror_first_behavior(self, monkeypatch):
        """require_db=False (legacy callers): mirror is written even without DB."""
        from src.repositories import profile_repo

        user_id = "legacy-mirror@test.com"
        monkeypatch.setattr(profile_repo, "_db", lambda: None)

        result = profile_repo.upsert_profile(user_id, {"current_role": "Legacy Role"})
        assert getattr(result, "current_role", None) == "Legacy Role"


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/onboarding/submit
# ─────────────────────────────────────────────────────────────────────────────

class TestOnboardingSubmitDurable:
    def _invoke(self, *, upsert=None, set_status=None):
        from src.api.routers.onboarding import OnboardingSubmitRequest, onboarding_submit

        body = OnboardingSubmitRequest(target_roles=["HSE Manager"])
        mock_request = MagicMock()
        profile = MagicMock()

        with patch(
            "src.api.routers.onboarding.get_current_user",
            return_value={"email": "onb@test.com", "role": "user"},
        ), patch(
            "src.repositories.profile_repo.upsert_profile",
            side_effect=upsert, return_value=MagicMock(),
        ) as mock_upsert, patch(
            "src.repositories.profile_repo.get_profile", return_value=profile,
        ), patch(
            "src.services.profile_context_resolver.resolve_profile_context",
            return_value=MagicMock(completion_score=1.0),
        ), patch(
            "src.services.profile_context_resolver.evaluate_minimum_profile",
            return_value=(True, []),
        ), patch(
            "src.services.profile_context_resolver.has_career_profile_data",
            return_value=True,
        ), patch(
            "src.repositories.onboarding_repo.set_onboarding_status",
            side_effect=set_status,
        ) as mock_status:
            try:
                return onboarding_submit(mock_request, body), mock_upsert, mock_status
            except HTTPException as exc:
                return exc, mock_upsert, mock_status

    def test_submit_passes_require_db_to_profile_and_status(self):
        result, mock_upsert, mock_status = self._invoke()
        assert not isinstance(result, HTTPException)
        assert mock_upsert.call_args.kwargs.get("require_db") is True
        assert mock_status.call_args.kwargs.get("require_db") is True

    def test_submit_returns_503_when_profile_write_fails(self):
        result, _, mock_status = self._invoke(
            upsert=RuntimeError("profile DB unavailable (require_db)")
        )
        assert isinstance(result, HTTPException)
        assert result.status_code == 503
        mock_status.assert_not_called()

    def test_submit_returns_503_when_status_write_fails(self):
        from src.repositories.onboarding_repo import OnboardingStateUnavailable

        result, _, _ = self._invoke(
            set_status=OnboardingStateUnavailable("onboarding-state DB unavailable")
        )
        assert isinstance(result, HTTPException)
        assert result.status_code == 503


class TestOnboardingRepoStrictWrite:
    def test_set_status_raises_when_db_unavailable(self, monkeypatch):
        from src.repositories import onboarding_repo

        monkeypatch.setattr(onboarding_repo, "_get_conn", lambda: None)
        with pytest.raises(onboarding_repo.OnboardingStateUnavailable):
            onboarding_repo.set_onboarding_status("u@test.com", "completed", require_db=True)

    def test_set_status_default_still_swallows(self, monkeypatch):
        from src.repositories import onboarding_repo

        monkeypatch.setattr(onboarding_repo, "_get_conn", lambda: None)
        assert onboarding_repo.set_onboarding_status("u@test.com", "completed") is None

    def test_set_status_raises_on_write_failure(self, monkeypatch):
        from src.repositories import onboarding_repo

        conn = MagicMock()
        conn.cursor.side_effect = RuntimeError("write exploded")
        monkeypatch.setattr(onboarding_repo, "_get_conn", lambda: conn)
        monkeypatch.setattr(onboarding_repo, "_ensure_table", lambda c: None)
        with pytest.raises(onboarding_repo.OnboardingStateUnavailable):
            onboarding_repo.set_onboarding_status("u@test.com", "completed", require_db=True)


# ─────────────────────────────────────────────────────────────────────────────
# PUT /api/v1/settings
# ─────────────────────────────────────────────────────────────────────────────

class TestSettingsPutDurable:
    def test_settings_repo_raises_when_db_unavailable(self, monkeypatch):
        from src.repositories import settings_repo

        monkeypatch.setattr(settings_repo, "get_db_connection", lambda: None)
        with pytest.raises(RuntimeError):
            settings_repo.upsert({"min_score": 70}, user_id="u@test.com", require_db=True)

    def test_settings_repo_default_still_swallows(self, monkeypatch):
        from src.repositories import settings_repo

        monkeypatch.setattr(settings_repo, "get_db_connection", lambda: None)
        assert settings_repo.upsert({"min_score": 70}, user_id="u@test.com") is None

    def test_settings_repo_raises_on_write_failure(self, monkeypatch):
        from src.repositories import settings_repo

        conn = MagicMock()
        conn.cursor.side_effect = RuntimeError("write exploded")
        monkeypatch.setattr(settings_repo, "get_db_connection", lambda: conn)
        with pytest.raises(RuntimeError):
            settings_repo.upsert({"min_score": 70}, user_id="u@test.com", require_db=True)

    def test_update_settings_passes_require_db(self):
        from src.services import settings_service

        with patch.object(settings_service.settings_repo, "upsert") as mock_upsert, \
             patch.object(settings_service, "get_settings", return_value={}):
            settings_service.update_settings({"min_score": 70}, user_id="u@test.com")
        assert mock_upsert.call_args.kwargs.get("require_db") is True

    def test_put_settings_returns_503_when_persistence_fails(self):
        import src.api.routers.settings as settings_router

        client = TestClient(app)
        app.dependency_overrides[settings_router.get_current_user_id] = lambda: "u@test.com"
        try:
            with patch.object(
                settings_router,
                "update_settings",
                side_effect=RuntimeError("settings DB unavailable (require_db)"),
            ):
                r = client.put("/api/v1/settings", json={"min_score": 70})
        finally:
            app.dependency_overrides.pop(settings_router.get_current_user_id, None)
        assert r.status_code == 503
