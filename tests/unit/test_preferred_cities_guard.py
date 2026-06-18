"""Unit tests for preferred_cities yes/no input guard.

Tests two guard points:
  1. _as_city_list() in src/rico_jotform_webhook.py (Jotform path)
  2. _CITY_REJECT_WORDS filter in rico_chat_api.py pending-field handler (chat path)

All pure-function; no DB, no network, no external services.
"""
import pytest
from src.rico_jotform_webhook import _as_city_list


class TestAsCityList:
    def test_returns_none_for_none(self):
        assert _as_city_list(None) is None

    def test_returns_none_for_empty_string(self):
        assert _as_city_list("") is None

    def test_returns_none_for_empty_list(self):
        assert _as_city_list([]) is None

    def test_arabic_yes_rejected(self):
        assert _as_city_list("نعم") is None

    def test_arabic_no_rejected(self):
        assert _as_city_list("لا") is None

    def test_english_yes_rejected(self):
        assert _as_city_list("yes") is None

    def test_english_yes_case_insensitive(self):
        assert _as_city_list("Yes") is None

    def test_english_no_rejected(self):
        assert _as_city_list("no") is None

    def test_ok_rejected(self):
        assert _as_city_list("ok") is None

    def test_valid_city_string_accepted(self):
        result = _as_city_list("Dubai")
        assert result == ["Dubai"]

    def test_valid_arabic_city_accepted(self):
        result = _as_city_list("دبي")
        assert result == ["دبي"]

    def test_comma_separated_cities_accepted(self):
        result = _as_city_list("Dubai, Abu Dhabi")
        assert result == ["Dubai", "Abu Dhabi"]

    def test_list_of_valid_cities_accepted(self):
        result = _as_city_list(["Dubai", "Sharjah"])
        assert result == ["Dubai", "Sharjah"]

    def test_mixed_valid_and_yes_no_filtered(self):
        result = _as_city_list(["Dubai", "نعم"])
        assert result == ["Dubai"]

    def test_all_yes_no_in_list_returns_none(self):
        assert _as_city_list(["yes", "no"]) is None

    def test_non_list_non_string_returns_none(self):
        assert _as_city_list(42) is None
        assert _as_city_list(True) is None


class TestChatHandlerCityRejectWords:
    """Verify the _CITY_REJECT_WORDS constant rejects the same set of words."""

    def _get_reject_words(self):
        from src.rico_chat_api import RicoChatAPI
        return RicoChatAPI._CITY_REJECT_WORDS

    def test_arabic_yes_in_reject_set(self):
        assert "نعم" in self._get_reject_words()

    def test_arabic_no_in_reject_set(self):
        assert "لا" in self._get_reject_words()

    def test_english_yes_in_reject_set(self):
        assert "yes" in self._get_reject_words()

    def test_english_no_in_reject_set(self):
        assert "no" in self._get_reject_words()

    def test_valid_city_not_in_reject_set(self):
        reject = self._get_reject_words()
        assert "dubai" not in reject
        assert "دبي" not in reject
        assert "sharjah" not in reject
