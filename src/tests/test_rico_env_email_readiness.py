"""Tests for email notification readiness checks in rico_env.py."""
import os
import pytest
from src.rico_env import get_rico_env_report, env_bool


def test_email_readiness_when_all_configured():
    """Email notifications are ready when enabled and credentials are present."""
    os.environ["EMAIL_USER"] = "test@example.com"
    os.environ["EMAIL_PASS"] = "test_password"
    os.environ["ENABLE_SIGNUP_EMAIL_NOTIFICATIONS"] = "true"
    
    report = get_rico_env_report()
    
    assert report.ready_for_email_notifications is True


def test_email_readiness_when_disabled():
    """Email notifications are not ready when explicitly disabled."""
    os.environ["EMAIL_USER"] = "test@example.com"
    os.environ["EMAIL_PASS"] = "test_password"
    os.environ["ENABLE_SIGNUP_EMAIL_NOTIFICATIONS"] = "false"
    
    report = get_rico_env_report()
    
    assert report.ready_for_email_notifications is False


def test_email_readiness_when_user_missing():
    """Email notifications are not ready when EMAIL_USER is missing."""
    os.environ.pop("EMAIL_USER", None)
    os.environ["EMAIL_PASS"] = "test_password"
    os.environ["ENABLE_SIGNUP_EMAIL_NOTIFICATIONS"] = "true"
    
    report = get_rico_env_report()
    
    assert report.ready_for_email_notifications is False


def test_email_readiness_when_pass_missing():
    """Email notifications are not ready when EMAIL_PASS is missing."""
    os.environ["EMAIL_USER"] = "test@example.com"
    os.environ.pop("EMAIL_PASS", None)
    os.environ["ENABLE_SIGNUP_EMAIL_NOTIFICATIONS"] = "true"
    
    report = get_rico_env_report()
    
    assert report.ready_for_email_notifications is False


def test_email_readiness_when_both_credentials_missing():
    """Email notifications are not ready when both credentials are missing."""
    os.environ.pop("EMAIL_USER", None)
    os.environ.pop("EMAIL_PASS", None)
    os.environ["ENABLE_SIGNUP_EMAIL_NOTIFICATIONS"] = "true"
    
    report = get_rico_env_report()
    
    assert report.ready_for_email_notifications is False


def test_email_readiness_defaults_to_enabled():
    """Email notifications default to enabled when env var is unset."""
    os.environ["EMAIL_USER"] = "test@example.com"
    os.environ["EMAIL_PASS"] = "test_password"
    os.environ.pop("ENABLE_SIGNUP_EMAIL_NOTIFICATIONS", None)
    
    report = get_rico_env_report()
    
    assert report.ready_for_email_notifications is True


def test_email_readiness_with_empty_user():
    """Email notifications are not ready when EMAIL_USER is empty string."""
    os.environ["EMAIL_USER"] = ""
    os.environ["EMAIL_PASS"] = "test_password"
    os.environ["ENABLE_SIGNUP_EMAIL_NOTIFICATIONS"] = "true"
    
    report = get_rico_env_report()
    
    assert report.ready_for_email_notifications is False


def test_email_readiness_with_empty_pass():
    """Email notifications are not ready when EMAIL_PASS is empty string."""
    os.environ["EMAIL_USER"] = "test@example.com"
    os.environ["EMAIL_PASS"] = ""
    os.environ["ENABLE_SIGNUP_EMAIL_NOTIFICATIONS"] = "true"
    
    report = get_rico_env_report()
    
    assert report.ready_for_email_notifications is False


def test_email_env_vars_in_checks():
    """Email env vars are included in the checks list."""
    os.environ["EMAIL_USER"] = "test@example.com"
    os.environ["EMAIL_PASS"] = "test_password"
    os.environ["ENABLE_SIGNUP_EMAIL_NOTIFICATIONS"] = "true"
    os.environ["ADMIN_SIGNUP_NOTIFICATION_EMAIL"] = "admin@example.com"
    
    report = get_rico_env_report()
    
    check_names = [check.name for check in report.checks]
    assert "EMAIL_USER" in check_names
    assert "EMAIL_PASS" in check_names
    assert "ENABLE_SIGNUP_EMAIL_NOTIFICATIONS" in check_names
    assert "ADMIN_SIGNUP_NOTIFICATION_EMAIL" in check_names


def test_email_readiness_in_to_dict():
    """ready_for_email_notifications is included in to_dict output."""
    os.environ["EMAIL_USER"] = "test@example.com"
    os.environ["EMAIL_PASS"] = "test_password"
    os.environ["ENABLE_SIGNUP_EMAIL_NOTIFICATIONS"] = "true"
    
    report = get_rico_env_report()
    report_dict = report.to_dict()
    
    assert "ready_for_email_notifications" in report_dict
    assert report_dict["ready_for_email_notifications"] is True


def test_env_bool_true_variants():
    """env_bool returns True for various true-like values."""
    for value in ["1", "true", "yes", "on", "TRUE", "YES", "ON"]:
        assert env_bool("TEST_VAR", default=False) is False  # unset
        os.environ["TEST_VAR"] = value
        assert env_bool("TEST_VAR", default=False) is True
        os.environ.pop("TEST_VAR", None)


def test_env_bool_false_variants():
    """env_bool returns False for various false-like values."""
    for value in ["0", "false", "no", "off", "FALSE", "NO", "OFF"]:
        os.environ["TEST_VAR"] = value
        assert env_bool("TEST_VAR", default=True) is False
        os.environ.pop("TEST_VAR", None)


def test_env_bool_default():
    """env_bool returns default when env var is unset."""
    os.environ.pop("TEST_VAR", None)
    assert env_bool("TEST_VAR", default=True) is True
    assert env_bool("TEST_VAR", default=False) is False
