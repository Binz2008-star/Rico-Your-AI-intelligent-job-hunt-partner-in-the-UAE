"""Test email sender configuration for subscription confirmations."""
import os
from unittest.mock import patch, Mock
import pytest

from src.services.mailer import send_email


@patch.dict(os.environ, {
    "SMTP_USER": "test@gmail.com",
    "SMTP_PASSWORD": "test_password",
})
def test_mailer_uses_configured_sender():
    """Test that mailer uses EMAIL_FROM for sender address."""
    with patch.dict(os.environ, {
        "EMAIL_FROM": "info@ricohunt.com",
        "EMAIL_FROM_NAME": "Rico Hunt",
    }):
        with patch("src.services.mailer.smtplib.SMTP_SSL") as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = Mock(return_value=False)

            result = send_email(
                to_email="user@example.com",
                subject="Test Subject",
                body="Test Body"
            )

            # Check that the message was constructed with the correct sender
            assert result is True
            mock_server.login.assert_called_once()
            mock_server.send_message.assert_called_once()

            # Get the message that was sent
            call_args = mock_server.send_message.call_args
            msg = call_args[0][0]

            # Verify sender uses configured EMAIL_FROM
            assert "info@ricohunt.com" in msg["From"]
            assert "Rico Hunt" in msg["From"]


@patch.dict(os.environ, {
    "SMTP_USER": "test@gmail.com",
    "SMTP_PASSWORD": "test_password",
})
def test_mailer_fallback_to_support_email():
    """Test that mailer falls back to SUPPORT_EMAIL when EMAIL_FROM not set."""
    with patch.dict(os.environ, {
        "SUPPORT_EMAIL": "info@ricohunt.com",
    }):
        # Remove EMAIL_FROM to test fallback
        os.environ.pop("EMAIL_FROM", None)

        with patch("src.services.mailer.smtplib.SMTP_SSL") as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = Mock(return_value=False)

            result = send_email(
                to_email="user@example.com",
                subject="Test Subject",
                body="Test Body"
            )

            assert result is True
            call_args = mock_server.send_message.call_args
            msg = call_args[0][0]

            # Verify sender falls back to SUPPORT_EMAIL
            assert "info@ricohunt.com" in msg["From"]


@patch.dict(os.environ, {
    "SMTP_USER": "test@gmail.com",
    "SMTP_PASSWORD": "test_password",
})
def test_mailer_fallback_to_default():
    """Test that mailer falls back to default info@ricohunt.com when neither set."""
    # Remove both EMAIL_FROM and SUPPORT_EMAIL to test default fallback
    os.environ.pop("EMAIL_FROM", None)
    os.environ.pop("SUPPORT_EMAIL", None)

    with patch("src.services.mailer.smtplib.SMTP_SSL") as mock_smtp:
        mock_server = Mock()
        mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = Mock(return_value=False)

        result = send_email(
            to_email="user@example.com",
            subject="Test Subject",
            body="Test Body"
        )

        assert result is True
        call_args = mock_server.send_message.call_args
        msg = call_args[0][0]

        # Verify sender falls back to default
        assert "info@ricohunt.com" in msg["From"]


@patch.dict(os.environ, {
    "SMTP_USER": "test@gmail.com",
    "SMTP_PASSWORD": "test_password",
})
def test_mailer_uses_production_smtp_config():
    """Test that mailer uses SMTP_HOST/SMTP_PORT/SMTP_USER when configured."""
    with patch.dict(os.environ, {
        "SMTP_HOST": "smtp.zoho.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "info@ricohunt.com",
        "SMTP_PASSWORD": "zoho_password",
        "EMAIL_FROM": "info@ricohunt.com",
        "EMAIL_FROM_NAME": "Rico Hunt",
    }):
        with patch("src.services.mailer.smtplib.SMTP") as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = Mock(return_value=False)

            result = send_email(
                to_email="user@example.com",
                subject="Test Subject",
                body="Test Body"
            )

            assert result is True
            # Verify STARTTLS was called for port 587
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_with("info@ricohunt.com", "zoho_password")
