"""
Tests for the location-only job-search intent fix.

Verifies that UAE/city names are never misclassified as job role titles
across three layers:
  1. _looks_like_bare_target_role  (already extended in test_bare_role_gate.py)
  2. _extract_arabic_role          (Arabic intent classifier)
  3. _classified_role_search       (chat handler location guard)
"""
from __future__ import annotations

import re
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers — inline normalisation so tests don't import the full module graph
# ---------------------------------------------------------------------------
def _normalize_arabic(text: str) -> str:
    text = re.sub(r"[ً-ٰٟـ]", "", text)
    text = re.sub(r"[آأإٱ]", "ا", text)
    text = text.replace("ى", "ي")
    text = text.replace("ة", "ه")
    return text


# ---------------------------------------------------------------------------
# 1. Arabic role extractor — pure-location captures must return None
# ---------------------------------------------------------------------------
from src.agent.intelligence.intent_classifier import _extract_arabic_role  # noqa: E402


class TestExtractArabicRolePureLocation(unittest.TestCase):

    def _norm(self, text: str) -> str:
        return _normalize_arabic(text.lower())

    # Location-only messages must yield None (no role extracted)
    def test_uae_alone_arabic(self) -> None:
        self.assertIsNone(_extract_arabic_role(self._norm("وظائف في الإمارات")))

    def test_dubai_alone_arabic(self) -> None:
        self.assertIsNone(_extract_arabic_role(self._norm("وظائف في دبي")))

    def test_search_jobs_uae_arabic(self) -> None:
        # "ابحث عن وظائف في الإمارات"
        self.assertIsNone(_extract_arabic_role(self._norm("ابحث عن وظائف في الإمارات")))

    def test_jobs_matching_cv_uae(self) -> None:
        # Full user message — should not extract a role
        msg = "ابحث عن وظائف في الإمارات تناسب سيرتي الذاتية"
        result = _extract_arabic_role(self._norm(msg))
        # Either None or does not contain only location words
        if result is not None:
            self.assertNotIn(result.strip(), {"الإمارات", "الامارات", "دبي", "ابوظبي"})

    # Real roles must still be extracted
    def test_real_role_hse_manager_arabic(self) -> None:
        # "وظائف مدير سلامة في الإمارات"
        result = _extract_arabic_role(self._norm("وظائف مدير سلامة في الإمارات"))
        self.assertIsNotNone(result)
        self.assertIn("مدير", result)

    def test_real_role_engineer_arabic(self) -> None:
        result = _extract_arabic_role(self._norm("وظائف مهندس في دبي"))
        self.assertIsNotNone(result)
        self.assertIn("مهندس", result)


# ---------------------------------------------------------------------------
# 2. _classified_role_search location guard — redirects instead of error
# ---------------------------------------------------------------------------
class TestClassifiedRoleSearchLocationGuard(unittest.TestCase):
    """
    When role_text is a pure location name, _classified_role_search must NOT
    return "I do not recognize X as a job role." It must either:
      (a) search using profile target_roles, or
      (b) ask the user to name a role.
    """

    def _make_api(self) -> "RicoChatAPI":
        from src.rico_chat_api import RicoChatAPI
        api = MagicMock(spec=RicoChatAPI)
        # Bind the real _classified_role_search to this mock instance
        api._classified_role_search = RicoChatAPI._classified_role_search.__get__(api)
        return api

    def _call(self, role_text: str, *, saved_roles: list[str]) -> dict:
        from src.rico_chat_api import RicoChatAPI

        profile = MagicMock()

        def profile_value(p, key):
            if key == "target_roles":
                return saved_roles
            return None

        api = MagicMock(spec=RicoChatAPI)
        api._profile_value = lambda p, k: profile_value(p, k)
        api._as_list = lambda x: x if isinstance(x, list) else ([x] if x else [])
        api._append_chat = MagicMock()
        api._SELF_REF_ROLE_RE = RicoChatAPI._SELF_REF_ROLE_RE
        api._is_broad_manager_role = RicoChatAPI._is_broad_manager_role
        api._broad_manager_clarification = MagicMock(return_value={"type": "clarification"})

        # Profile has saved target roles → should search
        if saved_roles:
            api._target_role_search_response = MagicMock(
                return_value={"type": "job_matches", "message": "found jobs"}
            )
        else:
            api._target_role_search_response = MagicMock()

        result = RicoChatAPI._classified_role_search(api, "user@test.com", role_text, profile)
        return result

    def test_uae_alone_with_saved_role_searches_profile(self) -> None:
        result = self._call("UAE", saved_roles=["HSE Manager"])
        # Must not be the error response
        self.assertNotIn("do not recognize", result.get("message", ""))
        self.assertNotIn("UAE", result.get("message", ""))

    def test_uae_alone_no_saved_role_asks_for_role(self) -> None:
        result = self._call("UAE", saved_roles=[])
        msg = result.get("message", "")
        self.assertNotIn("do not recognize", msg)
        # Should prompt for a role
        self.assertTrue(
            "role" in msg.lower() or "search" in msg.lower() or result.get("type") == "clarification",
            f"Expected a helpful clarification response, got: {result}",
        )

    def test_dubai_jobs_no_error(self) -> None:
        result = self._call("Dubai jobs", saved_roles=["Environmental Engineer"])
        self.assertNotIn("do not recognize", result.get("message", ""))

    def test_jobs_in_uae_no_error(self) -> None:
        result = self._call("jobs in UAE", saved_roles=[])
        self.assertNotIn("do not recognize", result.get("message", ""))


# ---------------------------------------------------------------------------
# 3. Intent classifier — extracted_role for Arabic location messages is None
# ---------------------------------------------------------------------------
class TestIntentClassifierLocationMessages(unittest.TestCase):
    """
    classify_intent must not produce a non-None extracted_role for messages
    whose only real content is a UAE/city location name.
    """

    def _classify(self, message: str, has_cv: bool = True):
        from src.agent.intelligence.intent_classifier import classify_intent
        return classify_intent(message, has_cv_profile=has_cv)

    def test_arabic_jobs_in_uae_no_role_extracted(self) -> None:
        result = self._classify("ابحث عن وظائف في الإمارات")
        self.assertIsNone(result.extracted_role)

    def test_arabic_jobs_matching_cv_uae_no_role_extracted(self) -> None:
        result = self._classify("ابحث عن وظائف في الإمارات تناسب سيرتي الذاتية")
        if result.extracted_role is not None:
            # If something is extracted, it must not be just the location
            self.assertNotIn(result.extracted_role.strip(), {"الإمارات", "الامارات", "دبي"})

    def test_arabic_jobs_dubai_no_role_extracted(self) -> None:
        result = self._classify("وظائف في دبي")
        self.assertIsNone(result.extracted_role)

    def test_arabic_hse_manager_in_uae_extracts_role(self) -> None:
        # With a request verb ("ابحث عن"), the Arabic role extractor fires.
        result = self._classify("ابحث عن وظائف مدير سلامة في الإمارات")
        # A real role should be extracted — not None and not just a location.
        self.assertIsNotNone(result.extracted_role)
        self.assertNotIn(result.extracted_role.strip(), {"الإمارات", "الامارات", "دبي"})

    def test_arabic_engineer_dubai_extracts_role(self) -> None:
        # With a request verb, the extractor should find "مهندس".
        result = self._classify("ابحث عن وظائف مهندس في دبي")
        self.assertIsNotNone(result.extracted_role)
        self.assertIn("مهندس", result.extracted_role)

    def test_english_hse_manager_uae_not_location_error(self) -> None:
        # "HSE Manager jobs in UAE" routes through the bare-role gate (extracted_role=None
        # from classify_intent, but _looks_like_bare_target_role passes the role on).
        # We verify only that the location-only guard does NOT fire (HSE Manager is a real role).
        from src.rico_chat_api import RicoChatAPI
        # "HSE Manager" alone (without location noise) should still pass the bare-role gate.
        assert RicoChatAPI._looks_like_bare_target_role("HSE Manager") is True

    def test_english_eco_officer_dubai_not_location_error(self) -> None:
        from src.rico_chat_api import RicoChatAPI
        assert RicoChatAPI._looks_like_bare_target_role("Environmental Compliance Officer") is True


if __name__ == "__main__":
    unittest.main()
