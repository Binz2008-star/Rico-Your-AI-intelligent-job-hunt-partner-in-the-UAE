# -*- coding: utf-8 -*-
"""Regression coverage for corrupted ``preferred_cities`` values.

Production first showed ``['Summarize this document for me.']`` and later the
Arabic job-search command ``['ابحث عن وظيفه']`` stored in the DB from prior
sessions. These tests confirm that profile_repo strips both values on read so
settings, job search, and model context never consume them.
"""
from __future__ import annotations

from unittest.mock import patch

from src.repositories.profile_repo import _sanitize_cities_safe


# ── _sanitize_cities_safe unit tests ─────────────────────────────────────────

def test_sanitize_strips_chat_command():
    assert _sanitize_cities_safe(["Summarize this document for me."]) == []


def test_sanitize_strips_arabic_job_search_command():
    assert _sanitize_cities_safe(["ابحث عن وظيفه"]) == []


def test_sanitize_keeps_valid_uae_city():
    result = _sanitize_cities_safe(["Dubai"])
    assert "Dubai" in result or "dubai" in result.lower() if result else False
    assert result  # non-empty


def test_sanitize_keeps_valid_arabic_uae_city():
    assert _sanitize_cities_safe(["عجمان"]) == ["عجمان"]


def test_sanitize_mixed_list():
    result = _sanitize_cities_safe(["Dubai", "ابحث عن وظيفه", "Abu Dhabi"])
    lowered = [c.lower() for c in result]
    assert any("dubai" in c for c in lowered)
    assert any("abu dhabi" in c for c in lowered)
    assert "ابحث عن وظيفه" not in result


def test_sanitize_empty_list():
    assert _sanitize_cities_safe([]) == []


def test_sanitize_confirmation_words_stripped():
    assert _sanitize_cities_safe(["تمام"]) == []
    assert _sanitize_cities_safe(["yes"]) == []


def test_sanitize_never_raises_on_bad_input():
    # Should not raise even if city_validation import fails.
    with patch("src.services.city_validation.sanitize_cities", side_effect=RuntimeError("boom")):
        result = _sanitize_cities_safe(["Dubai"])
        # Falls back to returning input unchanged rather than crashing.
        assert result == ["Dubai"]


# ── Profile read-time sanitization (integration) ─────────────────────────────

def test_bundle_to_profile_sanitizes_corrupted_city():
    """_bundle_to_profile must strip corrupted preferred_cities at read time."""
    from src.repositories.profile_repo import _bundle_to_profile

    corrupted_bundle = {
        "external_user_id": "u-test",
        "name": "Test",
        "email": "test@example.com",
        "phone": None,
        "telegram_username": None,
        "telegram_chat_id": None,
        "profile": {"preferred_cities": ["Summarize this document for me."]},
        "settings": {},
    }

    profile = _bundle_to_profile(corrupted_bundle)
    assert profile is not None
    assert "Summarize this document for me." not in (profile.preferred_cities or [])
    assert profile.preferred_cities == []


def test_bundle_to_profile_sanitizes_exact_arabic_production_value():
    """The exact 2026-07-23 production corruption must be neutralized."""
    from src.repositories.profile_repo import _bundle_to_profile

    corrupted_bundle = {
        "external_user_id": "u-test",
        "name": "Test",
        "email": "test@example.com",
        "phone": None,
        "telegram_username": None,
        "telegram_chat_id": None,
        "profile": {"preferred_cities": ["ابحث عن وظيفه"]},
        "settings": {},
    }

    profile = _bundle_to_profile(corrupted_bundle)
    assert profile is not None
    assert profile.preferred_cities == []


def test_bundle_to_profile_keeps_valid_city():
    """_bundle_to_profile must preserve valid UAE city values."""
    from src.repositories.profile_repo import _bundle_to_profile

    bundle = {
        "external_user_id": "u-test",
        "name": "Test",
        "email": "test@example.com",
        "phone": None,
        "telegram_username": None,
        "telegram_chat_id": None,
        "profile": {"preferred_cities": ["Dubai", "Abu Dhabi"]},
        "settings": {},
    }

    profile = _bundle_to_profile(bundle)
    assert profile is not None
    assert profile.preferred_cities  # non-empty
    lowered = [c.lower() for c in profile.preferred_cities]
    assert any("dubai" in c for c in lowered)
    assert any("abu dhabi" in c for c in lowered)
