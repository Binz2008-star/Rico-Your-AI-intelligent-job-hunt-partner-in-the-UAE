# -*- coding: utf-8 -*-
"""BUG-02 regression — corrupted preferred_cities value sanitized at read time.

Production showed preferred_cities=['Summarize this document for me.'] stored
in the DB from a prior session. This test confirms that profile_repo strips
corrupted values on read so the /settings page never surfaces them, without
any DB migration or backfill.
"""
from __future__ import annotations

from unittest.mock import patch

from src.repositories.profile_repo import _sanitize_cities_safe


# ── _sanitize_cities_safe unit tests ─────────────────────────────────────────

def test_sanitize_strips_chat_command():
    assert _sanitize_cities_safe(["Summarize this document for me."]) == []


def test_sanitize_keeps_valid_uae_city():
    result = _sanitize_cities_safe(["Dubai"])
    assert "Dubai" in result or "dubai" in result.lower() if result else False
    assert result  # non-empty


def test_sanitize_mixed_list():
    result = _sanitize_cities_safe(["Dubai", "Summarize this document for me.", "Abu Dhabi"])
    lowered = [c.lower() for c in result]
    assert any("dubai" in c for c in lowered)
    assert any("abu dhabi" in c for c in lowered)
    assert not any("summarize" in c.lower() for c in result)


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
