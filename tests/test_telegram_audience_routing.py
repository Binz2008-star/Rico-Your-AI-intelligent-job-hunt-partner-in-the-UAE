"""Tests for audience-aware Telegram notification routing.

Guarantees that admin/dev technical notifications (CI, deploy, errors, provider
quota) never leak into the user-facing Rico Job Hunt chat, and that job/career
notifications still reach users.

See src/services/notification_router.py.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.services import notification_router as nr

# Env vars the router consults — cleared before every test for isolation.
_TELEGRAM_ENV = [
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_ADMIN_CHAT_ID",
    "ADMIN_TELEGRAM_CHAT_ID",
    "TELEGRAM_DEV_CHAT_ID",
    "DEV_TELEGRAM_CHAT_ID",
    "TELEGRAM_ADMIN_BOT_TOKEN",
]


@pytest.fixture(autouse=True)
def _clean_telegram_env(monkeypatch):
    """Start each test with a clean Telegram env."""
    for key in _TELEGRAM_ENV:
        monkeypatch.delenv(key, raising=False)
    yield


def _ok_response():
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.text = ""
    return resp


# ── Classification ────────────────────────────────────────────────────────────

class TestClassification:

    @pytest.mark.parametrize(
        "ntype",
        [nr.ADMIN_CI, nr.ADMIN_DEPLOY, nr.ADMIN_ERROR, nr.ADMIN_PROVIDER, "admin_anything"],
    )
    def test_admin_types_are_admin(self, ntype):
        assert nr.is_admin_type(ntype) is True
        assert nr.is_user_type(ntype) is False

    @pytest.mark.parametrize("ntype", [nr.USER_JOB, nr.USER_ACCOUNT, "user_interview"])
    def test_user_types_are_user(self, ntype):
        assert nr.is_admin_type(ntype) is False
        assert nr.is_user_type(ntype) is True

    @pytest.mark.parametrize("ntype", ["", None, "garbage", "ci"])
    def test_unknown_types_fail_safe_to_admin(self, ntype):
        # Fail safe: an unclassified alert must NOT be treated as user-facing.
        assert nr.is_admin_type(ntype) is True


# ── admin_* must never reach the user chat ────────────────────────────────────

class TestAdminNotificationsNeverHitUserChat:

    def test_github_ci_failure_not_sent_to_user_chat(self, monkeypatch):
        """admin_ci with only a user chat configured → user chat untouched."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "user-111")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
        # No admin/dev chat configured.

        with patch("src.telegram_bot.send_telegram_message") as user_send, \
             patch("src.telegram_bot.send_telegram_to_user") as user_dm, \
             patch("src.services.notification_router.requests.post") as post:
            result = nr.send_notification(
                "🚨 Workflow Failed: QA Tests", nr.ADMIN_CI
            )

        assert result is False
        user_send.assert_not_called()
        user_dm.assert_not_called()
        post.assert_not_called()  # nothing sent anywhere — dropped + logged

    def test_vercel_deploy_message_not_sent_to_user_chat(self, monkeypatch):
        """admin_deploy with only a user chat configured → user chat untouched."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "user-111")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

        with patch("src.telegram_bot.send_telegram_message") as user_send, \
             patch("src.telegram_bot.send_telegram_to_user") as user_dm, \
             patch("src.services.notification_router.requests.post") as post:
            result = nr.send_notification(
                "Vercel: production deploy succeeded", nr.ADMIN_DEPLOY
            )

        assert result is False
        user_send.assert_not_called()
        user_dm.assert_not_called()
        post.assert_not_called()

    @pytest.mark.parametrize(
        "ntype",
        [nr.ADMIN_CI, nr.ADMIN_DEPLOY, nr.ADMIN_ERROR, nr.ADMIN_PROVIDER],
    )
    def test_missing_admin_channel_does_not_fallback_to_user_chat(self, monkeypatch, ntype):
        """No admin channel → admin alerts are dropped, NOT redirected to users."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "user-111")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

        with patch("src.telegram_bot.send_telegram_message") as user_send, \
             patch("src.telegram_bot.send_telegram_to_user") as user_dm, \
             patch("src.services.notification_router.requests.post") as post:
            result = nr.send_notification("technical alert", ntype)

        assert result is False
        user_send.assert_not_called()
        user_dm.assert_not_called()
        post.assert_not_called()

    def test_admin_notification_with_user_chat_id_is_refused(self, monkeypatch):
        """A user chat_id handed to an admin notification must be ignored."""
        monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin-999")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

        with patch("src.services.notification_router.requests.post", return_value=_ok_response()) as post, \
             patch("src.telegram_bot.send_telegram_to_user") as user_dm:
            result = nr.send_notification(
                "deploy failed", nr.ADMIN_DEPLOY, chat_id="user-555"
            )

        assert result is True
        user_dm.assert_not_called()
        # Delivered to the admin chat, never the supplied user chat_id.
        _, kwargs = post.call_args
        assert kwargs["json"]["chat_id"] == "admin-999"


# ── admin_* delivered to the admin/dev channel ────────────────────────────────

class TestAdminNotificationsReachAdminChannel:

    def test_provider_quota_alert_goes_to_admin_only(self, monkeypatch):
        """admin_provider → admin chat, never the user chat."""
        monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin-999")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "user-111")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

        with patch("src.services.notification_router.requests.post", return_value=_ok_response()) as post, \
             patch("src.telegram_bot.send_telegram_message") as user_send, \
             patch("src.telegram_bot.send_telegram_to_user") as user_dm:
            result = nr.send_notification(
                "DeepSeek quota exhausted — falling back to HF", nr.ADMIN_PROVIDER
            )

        assert result is True
        user_send.assert_not_called()
        user_dm.assert_not_called()
        post.assert_called_once()
        _, kwargs = post.call_args
        assert kwargs["json"]["chat_id"] == "admin-999"

    def test_dev_chat_used_when_admin_chat_absent(self, monkeypatch):
        """TELEGRAM_DEV_CHAT_ID is used when TELEGRAM_ADMIN_CHAT_ID is unset."""
        monkeypatch.setenv("TELEGRAM_DEV_CHAT_ID", "dev-777")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

        with patch("src.services.notification_router.requests.post", return_value=_ok_response()) as post:
            result = nr.send_admin_notification("CI failed", nr.ADMIN_CI)

        assert result is True
        _, kwargs = post.call_args
        assert kwargs["json"]["chat_id"] == "dev-777"

    def test_dedicated_admin_bot_token_preferred(self, monkeypatch):
        """TELEGRAM_ADMIN_BOT_TOKEN is used for the API URL when present."""
        monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin-999")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "user-tok")
        monkeypatch.setenv("TELEGRAM_ADMIN_BOT_TOKEN", "admin-tok")

        with patch("src.services.notification_router.requests.post", return_value=_ok_response()) as post:
            nr.send_admin_notification("CI failed", nr.ADMIN_CI)

        url = post.call_args[0][0]
        assert "admin-tok" in url
        assert "user-tok" not in url


# ── user_* still reach users ──────────────────────────────────────────────────

class TestUserNotificationsReachUsers:

    def test_job_match_notification_sent_to_user_chat(self, monkeypatch):
        """user_job with no explicit chat_id → shared user chat sender."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "user-111")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

        with patch("src.telegram_bot.send_telegram_message", return_value=True) as user_send, \
             patch("src.services.notification_router.requests.post") as admin_post:
            result = nr.send_notification(
                "🔔 3 new job matches for you", nr.USER_JOB
            )

        assert result is True
        user_send.assert_called_once()
        admin_post.assert_not_called()  # never touches the admin path

    def test_user_job_with_explicit_chat_id_uses_per_user_sender(self, monkeypatch):
        """A per-user chat_id routes through send_telegram_to_user."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

        with patch("src.telegram_bot.send_telegram_to_user", return_value=True) as user_dm, \
             patch("src.telegram_bot.send_telegram_message") as shared_send:
            result = nr.send_notification(
                "Your saved job has a new apply link", nr.USER_ACCOUNT, chat_id="user-222"
            )

        assert result is True
        user_dm.assert_called_once_with("user-222", "Your saved job has a new apply link")
        shared_send.assert_not_called()
