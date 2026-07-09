"""Tests for signup attribution sanitization and source formatting (issue #922).

Covers:
  - sanitize_attribution: unknown keys dropped, control chars stripped,
    length caps, non-dict/non-string input, empty values
  - format_signup_source: UTM chain, referrer host extraction, internal
    referrer ignored, landing-path-only and empty input degrade to
    "direct / unknown" (never a fake "website")
"""
from __future__ import annotations

from src.services.signup_source import (
    SIGNUP_SOURCE_FALLBACK,
    format_signup_source,
    sanitize_attribution,
)


class TestSanitizeAttribution:
    def test_keeps_known_fields_only(self):
        cleaned = sanitize_attribution({
            "utm_source": "google",
            "utm_medium": "cpc",
            "evil_field": "dropme",
            "password": "nope",
        })
        assert cleaned == {"utm_source": "google", "utm_medium": "cpc"}

    def test_non_dict_input_returns_empty(self):
        assert sanitize_attribution(None) == {}
        assert sanitize_attribution("google") == {}
        assert sanitize_attribution(["utm_source"]) == {}
        assert sanitize_attribution(42) == {}

    def test_non_string_values_dropped(self):
        assert sanitize_attribution({"utm_source": 123, "referrer": None}) == {}

    def test_control_chars_stripped(self):
        cleaned = sanitize_attribution({"utm_source": "goo\x00gle\r\n", "utm_medium": "\x1bcpc"})
        assert cleaned == {"utm_source": "google", "utm_medium": "cpc"}

    def test_whitespace_only_values_dropped(self):
        assert sanitize_attribution({"utm_source": "   ", "utm_campaign": "\n\t"}) == {}

    def test_overlong_values_capped(self):
        cleaned = sanitize_attribution({"utm_source": "x" * 1000})
        assert len(cleaned["utm_source"]) == 300

    def test_all_fields_accepted(self):
        raw = {
            "utm_source": "linkedin",
            "utm_medium": "social",
            "utm_campaign": "launch",
            "utm_content": "post-1",
            "utm_term": "uae jobs",
            "referrer": "https://www.linkedin.com/feed/",
            "landing_path": "/",
        }
        assert sanitize_attribution(raw) == raw


class TestFormatSignupSource:
    def test_empty_and_none_fall_back(self):
        assert format_signup_source(None) == SIGNUP_SOURCE_FALLBACK
        assert format_signup_source({}) == SIGNUP_SOURCE_FALLBACK
        assert SIGNUP_SOURCE_FALLBACK == "direct / unknown"

    def test_utm_full_chain(self):
        source = format_signup_source({
            "utm_source": "google",
            "utm_medium": "cpc",
            "utm_campaign": "brand-uae",
        })
        assert source == "google / cpc / brand-uae"

    def test_utm_source_only(self):
        assert format_signup_source({"utm_source": "telegram"}) == "telegram"

    def test_utm_beats_referrer(self):
        source = format_signup_source({
            "utm_source": "newsletter",
            "referrer": "https://www.google.com/",
        })
        assert source == "newsletter"

    def test_external_referrer_host(self):
        source = format_signup_source({"referrer": "https://www.linkedin.com/feed/update/x"})
        assert source == "referrer: www.linkedin.com"

    def test_referrer_without_scheme(self):
        assert format_signup_source({"referrer": "news.ycombinator.com/item"}) == (
            "referrer: news.ycombinator.com"
        )

    def test_internal_referrer_falls_back(self):
        for internal in ("https://ricohunt.com/", "https://www.ricohunt.com/pricing", "http://localhost:3000/"):
            assert format_signup_source({"referrer": internal}) == SIGNUP_SOURCE_FALLBACK

    def test_landing_path_only_falls_back(self):
        # A landing path alone is not attribution — degrade safely, never "website".
        source = format_signup_source({"landing_path": "/signup"})
        assert source == SIGNUP_SOURCE_FALLBACK
        assert "website" not in source

    def test_summary_length_capped(self):
        source = format_signup_source({
            "utm_source": "a" * 300,
            "utm_medium": "b" * 300,
        })
        assert len(source) <= 200
