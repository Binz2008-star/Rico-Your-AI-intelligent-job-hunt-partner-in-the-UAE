"""Focused unit tests for the Resend HTTPS email adapter and provider model.

All network is mocked — no real HTTP calls, no SMTP, no secrets in logs.
"""
from __future__ import annotations

import logging
from unittest.mock import patch, Mock

import httpx
import pytest

from src.services import mailer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_resend_env(monkeypatch, *, api_key="re_test_key_12345"):
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", api_key)
    monkeypatch.setenv("EMAIL_FROM", "info@ricohunt.com")
    monkeypatch.setenv("EMAIL_FROM_NAME", "Rico Hunt")


def _mock_response(status_code: int) -> Mock:
    resp = Mock()
    resp.status_code = status_code
    return resp


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

class TestProviderSelection:
    def test_resend_provider(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "resend")
        assert mailer._resolve_provider() == "resend"

    def test_smtp_provider(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
        assert mailer._resolve_provider() == "smtp"

    def test_disabled_provider(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "disabled")
        assert mailer._resolve_provider() == "disabled"

    def test_invalid_provider_returns_none(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "carrier-pigeon")
        assert mailer._resolve_provider() is None

    def test_unset_provider_defaults_to_smtp_outside_production(self, monkeypatch):
        monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
        monkeypatch.delenv("RAILWAY_REPLICA_ID", raising=False)
        assert mailer._resolve_provider() == "smtp"

    def test_unset_provider_returns_none_in_production(self, monkeypatch):
        monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
        monkeypatch.setenv("RAILWAY_REPLICA_ID", "some-replica-id")
        assert mailer._resolve_provider() is None


# ---------------------------------------------------------------------------
# Fail-closed: invalid and production-unset configurations
# ---------------------------------------------------------------------------

class TestFailClosed:
    def test_invalid_provider_returns_false_without_network(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "carrier-pigeon")
        with patch("src.services.mailer.httpx.post") as mock_post, \
             patch("src.services.mailer.smtplib.SMTP_SSL") as mock_smtp_ssl, \
             patch("src.services.mailer.smtplib.SMTP") as mock_smtp:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        mock_post.assert_not_called()
        mock_smtp_ssl.assert_not_called()
        mock_smtp.assert_not_called()

    def test_unset_in_production_returns_false_without_network(self, monkeypatch):
        monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
        monkeypatch.setenv("RAILWAY_REPLICA_ID", "some-replica-id")
        with patch("src.services.mailer.httpx.post") as mock_post, \
             patch("src.services.mailer.smtplib.SMTP_SSL") as mock_smtp_ssl, \
             patch("src.services.mailer.smtplib.SMTP") as mock_smtp:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        mock_post.assert_not_called()
        mock_smtp_ssl.assert_not_called()
        mock_smtp.assert_not_called()


# ---------------------------------------------------------------------------
# Disabled provider
# ---------------------------------------------------------------------------

class TestDisabledProvider:
    def test_disabled_returns_false_without_network(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "disabled")
        with patch("src.services.mailer.httpx.post") as mock_post:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        mock_post.assert_not_called()

    def test_disabled_logs_sanitized_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("EMAIL_PROVIDER", "disabled")
        with caplog.at_level(logging.WARNING, logger="src.services.mailer"):
            mailer.send_email(to_email="user@example.com", subject="Test", body="Body")
        assert any("email_delivery_disabled" in r.message for r in caplog.records)
        # Raw email must not appear in logs
        assert not any("user@example.com" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Resend: success
# ---------------------------------------------------------------------------

class TestResendSuccess:
    def test_resend_success_on_2xx(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", return_value=_mock_response(200)) as mock_post:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is True
        mock_post.assert_called_once()

    def test_resend_success_on_201(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", return_value=_mock_response(201)):
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is True

    def test_resend_correct_sender_formatting(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", return_value=_mock_response(200)) as mock_post:
            mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        call_kwargs = mock_post.call_args.kwargs
        payload = call_kwargs["json"]
        assert payload["from"] == "Rico Hunt <info@ricohunt.com>"
        assert payload["to"] == ["user@example.com"]


# ---------------------------------------------------------------------------
# Resend: HTML handling
# ---------------------------------------------------------------------------

class TestResendHtml:
    def test_html_included_when_supplied(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", return_value=_mock_response(200)) as mock_post:
            mailer.send_email(
                to_email="user@example.com", subject="Test", body="text", html="<b>html</b>"
            )
        payload = mock_post.call_args.kwargs["json"]
        assert payload["html"] == "<b>html</b>"

    def test_html_omitted_when_absent(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", return_value=_mock_response(200)) as mock_post:
            mailer.send_email(
                to_email="user@example.com", subject="Test", body="text"
            )
        payload = mock_post.call_args.kwargs["json"]
        assert "html" not in payload


# ---------------------------------------------------------------------------
# Resend: missing API key
# ---------------------------------------------------------------------------

class TestResendMissingApiKey:
    def test_missing_api_key_returns_false_without_network(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "resend")
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        with patch("src.services.mailer.httpx.post") as mock_post:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        mock_post.assert_not_called()

    def test_empty_api_key_returns_false_without_network(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "resend")
        monkeypatch.setenv("RESEND_API_KEY", "   ")
        with patch("src.services.mailer.httpx.post") as mock_post:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# Resend: never falls back to SMTP
# ---------------------------------------------------------------------------

class TestResendNoSmtpFallback:
    def test_resend_never_calls_smtp_on_failure(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", return_value=_mock_response(422)), \
             patch("src.services.mailer.smtplib.SMTP_SSL") as mock_smtp_ssl, \
             patch("src.services.mailer.smtplib.SMTP") as mock_smtp:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        mock_smtp_ssl.assert_not_called()
        mock_smtp.assert_not_called()

    def test_resend_never_calls_smtp_on_missing_key(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "resend")
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        with patch("src.services.mailer.smtplib.SMTP_SSL") as mock_smtp_ssl, \
             patch("src.services.mailer.smtplib.SMTP") as mock_smtp:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        mock_smtp_ssl.assert_not_called()
        mock_smtp.assert_not_called()


# ---------------------------------------------------------------------------
# Resend: retry policy
# ---------------------------------------------------------------------------

class TestResendRetry:
    def test_no_retry_on_400(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", return_value=_mock_response(400)) as mock_post:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        assert mock_post.call_count == 1

    def test_no_retry_on_401(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", return_value=_mock_response(401)) as mock_post:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        assert mock_post.call_count == 1

    def test_no_retry_on_403(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", return_value=_mock_response(403)) as mock_post:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        assert mock_post.call_count == 1

    def test_no_retry_on_404(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", return_value=_mock_response(404)) as mock_post:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        assert mock_post.call_count == 1

    def test_no_retry_on_422(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", return_value=_mock_response(422)) as mock_post:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        assert mock_post.call_count == 1

    def test_retry_once_on_429_then_succeeds(self, monkeypatch):
        _set_resend_env(monkeypatch)
        responses = [_mock_response(429), _mock_response(200)]
        with patch("src.services.mailer.httpx.post", side_effect=responses) as mock_post, \
             patch("time.sleep") as mock_sleep:
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is True
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(0.5)

    def test_retry_once_on_5xx_then_succeeds(self, monkeypatch):
        _set_resend_env(monkeypatch)
        responses = [_mock_response(503), _mock_response(200)]
        with patch("src.services.mailer.httpx.post", side_effect=responses) as mock_post, \
             patch("time.sleep"):
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is True
        assert mock_post.call_count == 2

    def test_retry_once_on_network_timeout_then_succeeds(self, monkeypatch):
        _set_resend_env(monkeypatch)
        responses = [httpx.TimeoutException("connect timeout"), _mock_response(200)]
        with patch("src.services.mailer.httpx.post", side_effect=responses) as mock_post, \
             patch("time.sleep"):
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is True
        assert mock_post.call_count == 2

    def test_retry_once_on_transport_error_then_succeeds(self, monkeypatch):
        _set_resend_env(monkeypatch)
        responses = [httpx.TransportError("connection reset"), _mock_response(200)]
        with patch("src.services.mailer.httpx.post", side_effect=responses) as mock_post, \
             patch("time.sleep"):
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is True
        assert mock_post.call_count == 2

    def test_retries_exhausted_on_429_returns_false(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", return_value=_mock_response(429)) as mock_post, \
             patch("time.sleep"):
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        assert mock_post.call_count == 2  # initial + 1 retry

    def test_retries_exhausted_on_5xx_returns_false(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", return_value=_mock_response(500)) as mock_post, \
             patch("time.sleep"):
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        assert mock_post.call_count == 2

    def test_retries_exhausted_on_timeout_returns_false(self, monkeypatch):
        _set_resend_env(monkeypatch)
        with patch("src.services.mailer.httpx.post", side_effect=httpx.TimeoutException("timeout")) as mock_post, \
             patch("time.sleep"):
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is False
        assert mock_post.call_count == 2


# ---------------------------------------------------------------------------
# Resend: idempotency key
# ---------------------------------------------------------------------------

class TestResendIdempotency:
    def test_same_idempotency_key_reused_across_retry(self, monkeypatch):
        _set_resend_env(monkeypatch)
        responses = [_mock_response(429), _mock_response(200)]
        with patch("src.services.mailer.httpx.post", side_effect=responses) as mock_post, \
             patch("time.sleep"):
            mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        # Both calls should have the same Idempotency-Key header
        call1_headers = mock_post.call_args_list[0].kwargs["headers"]
        call2_headers = mock_post.call_args_list[1].kwargs["headers"]
        key1 = call1_headers["Idempotency-Key"]
        key2 = call2_headers["Idempotency-Key"]
        assert key1 == key2
        assert len(key1) > 0  # non-empty UUID


# ---------------------------------------------------------------------------
# Resend: timeout budget
# ---------------------------------------------------------------------------

class TestResendTimeout:
    def test_timeout_values_are_strict(self):
        timeout = mailer._RESEND_TIMEOUT
        assert timeout.connect == 3.0
        assert timeout.read == 5.0
        assert timeout.write == 5.0
        assert timeout.pool == 2.0


# ---------------------------------------------------------------------------
# Resend: logging privacy
# ---------------------------------------------------------------------------

class TestResendLogPrivacy:
    def test_secrets_absent_from_logs_on_success(self, monkeypatch, caplog):
        _set_resend_env(monkeypatch, api_key="re_super_secret_key_999")
        with caplog.at_level(logging.DEBUG, logger="src.services.mailer"):
            with patch("src.services.mailer.httpx.post", return_value=_mock_response(200)):
                mailer.send_email(
                    to_email="user@example.com", subject="Test", body="Body"
                )
        for record in caplog.records:
            assert "re_super_secret_key_999" not in record.message
            assert "Bearer" not in record.message

    def test_secrets_absent_from_logs_on_failure(self, monkeypatch, caplog):
        _set_resend_env(monkeypatch, api_key="re_super_secret_key_999")
        with caplog.at_level(logging.DEBUG, logger="src.services.mailer"):
            with patch("src.services.mailer.httpx.post", return_value=_mock_response(422)):
                mailer.send_email(
                    to_email="user@example.com", subject="Test", body="Body"
                )
        for record in caplog.records:
            assert "re_super_secret_key_999" not in record.message
            assert "Bearer" not in record.message

    def test_raw_recipient_absent_from_logs(self, monkeypatch, caplog):
        _set_resend_env(monkeypatch)
        with caplog.at_level(logging.DEBUG, logger="src.services.mailer"):
            with patch("src.services.mailer.httpx.post", return_value=_mock_response(200)):
                mailer.send_email(
                    to_email="sensitive@example.com", subject="Test", body="Body"
                )
        for record in caplog.records:
            assert "sensitive@example.com" not in record.message

    def test_no_response_body_in_logs(self, monkeypatch, caplog):
        _set_resend_env(monkeypatch)
        resp = Mock()
        resp.status_code = 422
        resp.text = '{"error":"invalid_api_key","message":"The API key is invalid"}'
        with caplog.at_level(logging.DEBUG, logger="src.services.mailer"):
            with patch("src.services.mailer.httpx.post", return_value=resp):
                mailer.send_email(
                    to_email="user@example.com", subject="Test", body="Body"
                )
        for record in caplog.records:
            assert "invalid_api_key" not in record.message
            assert resp.text not in record.message


# ---------------------------------------------------------------------------
# SMTP provider: legacy preservation
# ---------------------------------------------------------------------------

class TestSmtpProviderPreserved:
    def test_explicit_smtp_provider_preserves_legacy_behavior(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
        monkeypatch.setenv("SMTP_HOST", "smtp.zoho.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "info@ricohunt.com")
        monkeypatch.setenv("SMTP_PASSWORD", "zoho_password")
        monkeypatch.setenv("EMAIL_FROM", "info@ricohunt.com")
        monkeypatch.setenv("EMAIL_FROM_NAME", "Rico Hunt")

        with patch("src.services.mailer.smtplib.SMTP") as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = Mock(return_value=False)

            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_with("info@ricohunt.com", "zoho_password")

    def test_smtp_provider_does_not_call_resend(self, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
        monkeypatch.setenv("SMTP_USER", "test@x.com")
        monkeypatch.setenv("SMTP_PASSWORD", "pw")
        monkeypatch.setenv("SMTP_PORT", "465")

        with patch("src.services.mailer.httpx.post") as mock_post, \
             patch("src.services.mailer.smtplib.SMTP_SSL") as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = Mock(return_value=False)
            result = mailer.send_email(
                to_email="user@example.com", subject="Test", body="Body"
            )
        assert result is True
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# SMTP provider: sanitized failure logging
# ---------------------------------------------------------------------------

class TestSmtpLogPrivacy:
    def test_smtp_failure_no_raw_subject_in_logs(self, monkeypatch, caplog):
        monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
        monkeypatch.setenv("SMTP_USER", "test@x.com")
        monkeypatch.setenv("SMTP_PASSWORD", "pw")
        monkeypatch.setenv("SMTP_PORT", "465")

        with caplog.at_level(logging.DEBUG, logger="src.services.mailer"):
            with patch("src.services.mailer.smtplib.SMTP_SSL", side_effect=Exception("SMTP server response with secret data")):
                result = mailer.send_email(
                    to_email="user@example.com",
                    subject="Verify your RicoHunt email address",
                    body="Body",
                )
        assert result is False
        for record in caplog.records:
            # Raw subject must not appear in logs
            assert "Verify your RicoHunt email address" not in record.message
            # Raw recipient must not appear in logs
            assert "user@example.com" not in record.message
            # Raw exception text must not appear in logs
            assert "SMTP server response with secret data" not in record.message

    def test_smtp_failure_logs_sanitized_error_category(self, monkeypatch, caplog):
        monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
        monkeypatch.setenv("SMTP_USER", "test@x.com")
        monkeypatch.setenv("SMTP_PASSWORD", "pw")
        monkeypatch.setenv("SMTP_PORT", "465")

        with caplog.at_level(logging.ERROR, logger="src.services.mailer"):
            with patch("src.services.mailer.smtplib.SMTP_SSL", side_effect=ConnectionRefusedError("refused")):
                result = mailer.send_email(
                    to_email="user@example.com",
                    subject="Test",
                    body="Body",
                )
        assert result is False
        # Should log the error category, not the raw exception text
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_records) > 0
        assert any("email_delivery_failed" in r.message for r in error_records)
        assert any("ConnectionRefusedError" in r.message for r in error_records)
        # Raw exception text must not appear
        assert not any("refused" in r.message for r in error_records)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
