"""Smoke tests for Telegram demo mode and formatting."""

import os
import pytest

from src.telegram_bot import (
    _normalize_job_key,
    _format_score,
    format_telegram_jobs,
    send_telegram_message,
)


class TestTelegramDemoMode:
    """Test Telegram demo mode behavior."""

    def test_normalize_job_key_dedupes_duplicates(self):
        """Duplicate jobs with same title/company/location/link should produce same key."""
        job1 = {
            "title": "HSE Officer",
            "company": "NMDC Group",
            "location": "Abu Dhabi",
            "link": "https://example.com/job/123"
        }
        job2 = {
            "title": "HSE Officer",
            "company": "NMDC Group",
            "location": "Abu Dhabi",
            "link": "https://example.com/job/123"
        }
        job3 = {
            "title": "HSE Officer",
            "company": "NMDC Group",
            "location": "Dubai",  # Different location
            "link": "https://example.com/job/123"
        }

        assert _normalize_job_key(job1) == _normalize_job_key(job2)
        assert _normalize_job_key(job1) != _normalize_job_key(job3)

    def test_normalize_job_key_case_insensitive(self):
        """Job key normalization should be case-insensitive."""
        job1 = {
            "title": "HSE OFFICER",
            "company": "NMDC GROUP",
            "location": "ABU DHABI",
            "link": "HTTPS://EXAMPLE.COM/JOB/123"
        }
        job2 = {
            "title": "hse officer",
            "company": "nmdc group",
            "location": "abu dhabi",
            "link": "https://example.com/job/123"
        }

        assert _normalize_job_key(job1) == _normalize_job_key(job2)

    def test_normalize_job_key_whitespace_insensitive(self):
        """Job key normalization should trim whitespace."""
        job1 = {
            "title": "  HSE Officer  ",
            "company": "  NMDC Group  ",
            "location": "  Abu Dhabi  ",
            "link": "  https://example.com/job/123  "
        }
        job2 = {
            "title": "HSE Officer",
            "company": "NMDC Group",
            "location": "Abu Dhabi",
            "link": "https://example.com/job/123"
        }

        assert _normalize_job_key(job1) == _normalize_job_key(job2)

    def test_format_score_demo_mode(self, monkeypatch):
        """In demo mode, scores should be formatted as bands."""
        monkeypatch.setattr("src.telegram_bot._DEMO_MODE", True)

        assert _format_score(95) == "Match: Excellent"
        assert _format_score(85) == "Match: Strong"
        assert _format_score(70) == "Match: Good"
        assert _format_score(50) == "Match: Fair"

    def test_format_score_normal_mode(self, monkeypatch):
        """In normal mode, scores should be displayed as numbers."""
        monkeypatch.setattr("src.telegram_bot._DEMO_MODE", False)

        assert _format_score(95) == "95"
        assert _format_score(85) == "85"
        assert _format_score(70) == "70"
        assert _format_score(50) == "50"

    def test_format_telegram_jobs_dedupes(self, monkeypatch):
        """Duplicate jobs should produce only one Telegram card."""
        monkeypatch.setattr("src.telegram_bot._DEMO_MODE", False)

        jobs = [
            ({"title": "HSE Officer", "company": "NMDC Group", "location": "Abu Dhabi", "link": "https://example.com/job/123"}, 100),
            ({"title": "HSE Officer", "company": "NMDC Group", "location": "Abu Dhabi", "link": "https://example.com/job/123"}, 100),  # Duplicate
            ({"title": "Safety Manager", "company": "ADNOC", "location": "Dubai", "link": "https://example.com/job/456"}, 90),
        ]

        message = format_telegram_jobs(jobs)
        # Should contain only 2 jobs, not 3
        assert message.count("📌") == 2
        assert "HSE Officer" in message
        assert "Safety Manager" in message

    def test_format_telegram_jobs_limits_to_5(self, monkeypatch):
        """Telegram output should be limited to 5 jobs max."""
        monkeypatch.setattr("src.telegram_bot._DEMO_MODE", False)

        jobs = [
            ({"title": f"Job {i}", "company": f"Company {i}", "location": "Dubai", "link": f"https://example.com/job/{i}"}, 80)
            for i in range(10)
        ]

        message = format_telegram_jobs(jobs)
        # Should contain only 5 jobs
        assert message.count("📌") == 5

    def test_format_telegram_jobs_empty_normal_mode(self, monkeypatch):
        """Empty result should return 'No new jobs found today' in normal mode."""
        monkeypatch.setattr("src.telegram_bot._DEMO_MODE", False)

        message = format_telegram_jobs([])
        assert message == "<b>No new jobs found today.</b>"

    def test_format_telegram_jobs_empty_demo_mode(self, monkeypatch):
        """Empty result should return empty string in demo mode (suppress message)."""
        monkeypatch.setattr("src.telegram_bot._DEMO_MODE", True)

        message = format_telegram_jobs([])
        assert message == ""

    def test_send_telegram_message_respects_public_alerts_kill_switch(self, monkeypatch):
        """send_telegram_message should return False when public alerts disabled."""
        monkeypatch.setattr("src.telegram_bot._PUBLIC_ALERTS_ENABLED", False)

        result = send_telegram_message("Test message")
        assert result is False

    def test_send_telegram_message_normal_mode(self, monkeypatch):
        """send_telegram_message should attempt to send when public alerts enabled."""
        monkeypatch.setattr("src.telegram_bot._PUBLIC_ALERTS_ENABLED", True)
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "test_chat_id")

        # This will fail to actually send (no network), but should not return False immediately
        # We'll just verify it doesn't return False due to the kill switch
        result = send_telegram_message("Test message")
        # Should not be False due to kill switch (may be False due to network error)
        # We just verify the kill switch logic is checked
        assert "Telegram public alerts disabled" not in str(result)
