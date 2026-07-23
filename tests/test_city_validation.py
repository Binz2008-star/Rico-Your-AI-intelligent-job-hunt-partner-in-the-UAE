"""Profile location-field hygiene (preferred_cities).

Production showed corrupted profiles where chat commands were stored as cities:
``Summarize this document for me.`` and, later, ``ابحث عن وظيفه``. These tests
pin the bilingual validation that prevents those values from poisoning search
location and the AI context.

Pure/deterministic — no I/O, no DB, no LLM.
"""
from __future__ import annotations

import pytest

from src.services.city_validation import is_plausible_city, sanitize_cities


# ── Real cities accepted ──────────────────────────────────────────────────────

def test_known_uae_cities_accepted():
    for c in ["Dubai", "Abu Dhabi", "Sharjah", "Ras Al Khaimah", "Umm Al Quwain", "Al Ain"]:
        assert is_plausible_city(c), c


def test_known_arabic_cities_accepted():
    for c in ["دبي", "أبوظبي", "ابوظبي", "الشارقة", "الشارقه", "رأس الخيمة", "راس الخيمه"]:
        assert is_plausible_city(c), c


def test_unlisted_but_plausible_city_accepted():
    # A real city not in the known set should still pass (short, no intent words).
    assert is_plausible_city("Doha")
    assert is_plausible_city("Salalah")


# ── Production corruption rejected ───────────────────────────────────────────

def test_document_action_sentence_rejected():
    assert not is_plausible_city("Summarize this document for me.")
    assert not is_plausible_city("Describe what's in this image.")
    assert not is_plausible_city("Extract the most important information from this document.")


@pytest.mark.parametrize("command", [
    "ابحث عن وظيفه",
    "ابحث عن وظيفة",
    "أبحث عن وظيفة",
    "دورلي على شغل",
    "اريد عمل",
    "أريد وظائف",
    "اعرضلي شواغر",
    "ساعدني في ايجاد وظيفة",
])
def test_arabic_job_search_commands_rejected(command):
    assert not is_plausible_city(command), command


@pytest.mark.parametrize("cv_status_text", [
    "لديك سيرتي الذاتيه",
    "لديك سيرتي الذاتية",
    "عندك سيرتي الذاتية",
    "السيرة الذاتية مرفوعة",
    "السيره الذاتيه مرفوعه",
])
def test_arabic_cv_status_text_rejected(cv_status_text):
    """Exact production correction and common variants are not city values."""
    assert not is_plausible_city(cv_status_text), cv_status_text


def test_intent_and_affirmation_rejected():
    assert not is_plausible_city("find software engineer jobs")
    assert not is_plausible_city("yes")
    assert not is_plausible_city("no")


def test_sentences_and_junk_rejected():
    assert not is_plausible_city("where should I look?")          # trailing ?
    assert not is_plausible_city("I want to work in finance.")    # trailing . + intent
    assert not is_plausible_city("12345")                          # digits
    assert not is_plausible_city("a really long free text answer that is clearly not a city")
    assert not is_plausible_city("")


# ── sanitize_cities: neutralize stored corruption on read ─────────────────────

def test_sanitize_drops_corrupted_value():
    assert sanitize_cities(["Summarize this document for me."]) == []


def test_sanitize_drops_arabic_search_command():
    assert sanitize_cities(["ابحث عن وظيفه"]) == []


def test_sanitize_drops_arabic_cv_status_text():
    assert sanitize_cities(["لديك سيرتي الذاتيه"]) == []


def test_sanitize_keeps_valid_drops_invalid():
    assert sanitize_cities(["Dubai", "ابحث عن وظيفه", "Abu Dhabi"]) == ["Dubai", "Abu Dhabi"]


def test_sanitize_keeps_valid_drops_cv_status_text():
    assert sanitize_cities(["دبي", "لديك سيرتي الذاتيه", "أبوظبي"]) == ["دبي", "أبوظبي"]


def test_sanitize_dedups_case_insensitive_preserving_order():
    assert sanitize_cities(["Dubai", "dubai", "Sharjah"]) == ["Dubai", "Sharjah"]


def test_sanitize_empty_and_none_safe():
    assert sanitize_cities([]) == []
    assert sanitize_cities(None) == []


# ── Integration: AI context + search read ─────────────────────────────────────

def test_build_openai_context_drops_corrupted_city():
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI(persist=False)
    profile = {
        "skills": ["leadership"], "years_experience": 10,
        "preferred_cities": ["Summarize this document for me."],
        "target_roles": ["Developer"],
    }
    ctx = api._build_openai_context(profile, user_id=None)
    # The corrupted city must not reach the model context.
    assert "preferred_cities" not in ctx


def test_build_openai_context_drops_arabic_search_command():
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI(persist=False)
    ctx = api._build_openai_context(
        {"skills": ["iso 14001"], "preferred_cities": ["ابحث عن وظيفه"]},
        user_id=None,
    )
    assert "preferred_cities" not in ctx


def test_build_openai_context_drops_arabic_cv_status_text():
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI(persist=False)
    ctx = api._build_openai_context(
        {"skills": ["iso 14001"], "preferred_cities": ["لديك سيرتي الذاتيه"]},
        user_id=None,
    )
    assert "preferred_cities" not in ctx


def test_build_openai_context_keeps_real_city():
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI(persist=False)
    ctx = api._build_openai_context({"skills": ["x"], "preferred_cities": ["Dubai"]}, user_id=None)
    assert ctx.get("preferred_cities") == ["Dubai"]
