"""
tests/test_bug08_city_declaration.py

Regression tests for BUG-08 — "My favorite city is Dubai" was silently
ignored, returning "I haven't changed anything yet".

Three bugs combined to cause the failure:

  Bug A — intent_classifier.py: _PROFILE_UPDATE_RE required an
           update/change/set/modify/adjust verb, so "My favorite city is
           Dubai" was never classified as profile_update.

  Bug B — rico_intent_router.py: _PREFS_PATTERNS had the same verb
           requirement, so _route() classified the message as unknown
           and returned empty tool_args even when the intent gate
           was bypassed.

  Bug C — rico_intent_router.py _build_tool_args: extracted city was
           stored as prefs["preferred_city"] (singular string), but the
           canonical DB field is preferred_cities (List[str]).
           upsert_profile silently dropped the unknown key because it
           was not in the _PROFILE_FIELDS whitelist.

All three tests must NOT touch the live database.
"""
from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


# ===========================================================================
# Bug A — intent_classifier must recognise declarative city statements
# ===========================================================================

class TestCityDeclarationIntentClassification:

    def _classify(self, msg: str) -> str:
        from src.agent.intelligence.intent_classifier import classify_intent
        return classify_intent(msg).intent

    def test_my_favorite_city_is_dubai(self):
        assert self._classify("My favorite city is Dubai") == "profile_update"

    def test_my_city_is_abu_dhabi(self):
        assert self._classify("My city is Abu Dhabi") == "profile_update"

    def test_my_preferred_city_is_sharjah(self):
        assert self._classify("My preferred city is Sharjah") == "profile_update"

    def test_i_live_in_dubai(self):
        assert self._classify("I live in Dubai") == "profile_update"

    def test_i_am_based_in_abu_dhabi(self):
        assert self._classify("I am based in Abu Dhabi") == "profile_update"

    def test_existing_verb_form_still_works(self):
        """The original regex path (verb + city) must still classify correctly."""
        assert self._classify("update my city to Dubai") == "profile_update"
        assert self._classify("change my location to Abu Dhabi") == "profile_update"


# ===========================================================================
# Bug B — intent router must extract city from declarative statements
# ===========================================================================

class TestCityDeclarationRouterExtraction:

    def _route(self, msg: str):
        from src.rico_intent_router import route
        return route(msg)

    def test_my_favorite_city_routes_to_update_preferences(self):
        result = self._route("My favorite city is Dubai")
        assert result.intent == "update_preferences"

    def test_city_entity_extracted(self):
        result = self._route("My favorite city is Dubai")
        assert result.entities.get("city") == "Dubai"

    def test_preferences_dict_has_preferred_cities(self):
        result = self._route("My favorite city is Dubai")
        prefs = result.tool_args.get("preferences", {})
        assert "preferred_cities" in prefs

    def test_preferred_cities_is_list(self):
        result = self._route("My favorite city is Dubai")
        prefs = result.tool_args.get("preferences", {})
        assert isinstance(prefs["preferred_cities"], list)
        assert prefs["preferred_cities"] == ["Dubai"]

    def test_i_live_in_abu_dhabi_extracts_city(self):
        result = self._route("I live in Abu Dhabi")
        prefs = result.tool_args.get("preferences", {})
        assert prefs.get("preferred_cities") == ["Abu Dhabi"]


# ===========================================================================
# Bug C — preferred_cities (list) must not be silently dropped by upsert_profile
# ===========================================================================

class TestPreferredCitiesFieldIsWhitelisted:

    def test_preferred_cities_is_valid_profile_field(self):
        """preferred_cities must be in the _PROFILE_FIELDS whitelist."""
        from src.repositories.profile_repo import _PROFILE_FIELDS
        assert "preferred_cities" in _PROFILE_FIELDS

    def test_preferred_city_singular_is_not_a_valid_field(self):
        """preferred_city (old singular key) is not a valid profile field."""
        from src.repositories.profile_repo import _PROFILE_FIELDS
        assert "preferred_city" not in _PROFILE_FIELDS


# ===========================================================================
# End-to-end: _route() output feeds correctly into the confirmation flow
# ===========================================================================

class TestCityDeclarationEndToEndPrefs:
    """Simulate the profile_update handler receiving the routed prefs."""

    def test_prefs_nonempty_so_handler_does_not_return_no_change_message(self):
        """prefs must be non-empty so the handler presents a confirmation
        instead of the 'I haven't changed anything yet' fallback."""
        from src.rico_intent_router import route
        result = route("My favorite city is Dubai")
        prefs = result.tool_args.get("preferences", {})
        assert prefs, (
            "prefs was empty — handler would have returned 'I haven't changed anything'"
        )
        assert "preferred_cities" in prefs
        assert prefs["preferred_cities"] == ["Dubai"]

    def test_format_pref_changes_renders_city_correctly(self):
        """_format_pref_changes must render preferred_cities (plural key) properly."""
        from src.rico_chat_api import RicoChatAPI
        prefs = {"preferred_cities": ["Dubai"]}
        lines = RicoChatAPI._format_pref_changes(prefs)
        assert any("Dubai" in line for line in lines)
        assert any("Preferred city" in line for line in lines)
