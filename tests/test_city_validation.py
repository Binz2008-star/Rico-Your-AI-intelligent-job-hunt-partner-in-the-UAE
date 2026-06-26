"""Profile location-field hygiene (preferred_cities).

Production showed a corrupted profile: preferred_cities=['Summarize this document
for me.'] — a misfiled chat message stored as a city, poisoning search location
and the AI context. These tests pin the validation that prevents the write and
neutralizes the stored value on read.

Pure/deterministic — no I/O, no DB, no LLM.
"""
from __future__ import annotations

from src.services.city_validation import is_plausible_city, sanitize_cities


# ── Real cities accepted ──────────────────────────────────────────────────────

def test_known_uae_cities_accepted():
    for c in ["Dubai", "Abu Dhabi", "Sharjah", "Ras Al Khaimah", "Umm Al Quwain", "Al Ain"]:
        assert is_plausible_city(c), c


def test_known_arabic_cities_accepted():
    for c in ["دبي", "أبوظبي", "الشارقة", "رأس الخيمة"]:
        assert is_plausible_city(c), c


def test_unlisted_but_plausible_city_accepted():
    # A real city not in the known set should still pass (short, no intent words).
    assert is_plausible_city("Doha")
    assert is_plausible_city("Salalah")


# ── The production corruption rejected ────────────────────────────────────────

def test_document_action_sentence_rejected():
    assert not is_plausible_city("Summarize this document for me.")
    assert not is_plausible_city("Describe what's in this image.")
    assert not is_plausible_city("Extract the most important information from this document.")


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


def test_sanitize_keeps_valid_drops_invalid():
    assert sanitize_cities(["Dubai", "Summarize this document for me.", "Abu Dhabi"]) == ["Dubai", "Abu Dhabi"]


def test_sanitize_dedups_case_insensitive_preserving_order():
    assert sanitize_cities(["Dubai", "dubai", "Sharjah"]) == ["Dubai", "Sharjah"]


def test_sanitize_empty_and_none_safe():
    assert sanitize_cities([]) == []
    assert sanitize_cities(None) == []


# ── Integration: write boundary + AI context + search read ────────────────────

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


def test_build_openai_context_keeps_real_city():
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI(persist=False)
    ctx = api._build_openai_context({"skills": ["x"], "preferred_cities": ["Dubai"]}, user_id=None)
    assert ctx.get("preferred_cities") == ["Dubai"]
