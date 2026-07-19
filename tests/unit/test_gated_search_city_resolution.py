"""
tests/unit/test_gated_search_city_resolution.py

Regression tests for the "city slot loop" exposed by a real Rico conversation:

  * User: "Find me Senior HSE Manager jobs in Dubai and Abu Dhabi." — the cities
    named inline were never persisted, so later job requests hit the
    minimum-profile gate and looped forever asking for the preferred city.
  * User answered the gate with a bare city ("Ajman") — instead of running the
    search, Rico saved the city and diverted into an unrelated CV draft
    ("Here is your CV draft, Vip Relationship Manager").

The fixes (all global / data-driven, no per-user special casing):

  1. `_extract_uae_cities` pulls UAE cities named inline in any message.
  2. The minimum-profile gate persists those cities and re-evaluates before
     downgrading, so a city already provided is never re-asked.
  3. The pending-city resolver routes by WHY the city was requested: the CV
     builder sets `_pending_cv_generate` (→ CV draft); a gated job search does
     not (→ resume the search via a `_redispatch_message` marker).
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


def _profile(**kw):
    defaults = dict(
        name="Roben Edwan",
        email="roben@example.com",
        phone="+971502233989",
        skills=["ISO 14001", "audit", "compliance"],
        years_experience=10.0,
        target_roles=["Environmental Manager", "Compliance Manager"],
        certifications=[],
        preferred_cities=[],
        industries=[],
        current_role="",
        has_cv=True,
        work_experience=[],
        education=[],
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# 1. _extract_uae_cities
# ---------------------------------------------------------------------------

class TestExtractUAECities:
    @pytest.fixture(autouse=True)
    def _api(self):
        from src.rico_chat_api import RicoChatAPI
        self.api = RicoChatAPI.__new__(RicoChatAPI)

    def test_two_cities_in_search_request(self):
        cities = self.api._extract_uae_cities(
            "Find me Senior HSE Manager jobs in Dubai and Abu Dhabi."
        )
        assert cities == ["Dubai", "Abu Dhabi"]

    def test_single_bare_city(self):
        assert self.api._extract_uae_cities("Ajman") == ["Ajman"]

    def test_multiword_city_titlecased(self):
        assert self.api._extract_uae_cities("jobs in ras al khaimah") == [
            "Ras Al Khaimah"
        ]

    def test_uae_scope_normalised(self):
        assert self.api._extract_uae_cities("any jobs across UAE") == ["UAE"]

    def test_no_city_returns_empty(self):
        assert self.api._extract_uae_cities("find jobs that match my CV") == []

    def test_dedup_order_preserving(self):
        assert self.api._extract_uae_cities("Dubai, Dubai and Sharjah") == [
            "Dubai",
            "Sharjah",
        ]

    def test_arabic_city(self):
        assert self.api._extract_uae_cities("وظائف في دبي") == ["دبي"]


# ---------------------------------------------------------------------------
# 2. Pending-city resolver routes by flow (search vs CV builder)
# ---------------------------------------------------------------------------

class TestPendingCityFlowRouting:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.rico_chat_api import RicoChatAPI
        self.api = RicoChatAPI.__new__(RicoChatAPI)
        self.api._persist = False
        self.api._store_recent_context = MagicMock()
        self.api._append_chat = MagicMock()
        self.api._has_cv_profile = MagicMock(return_value=True)
        self.api._profile_value = lambda p, k: getattr(p, k, None)
        self.api._as_list = lambda v: list(v) if isinstance(v, list) else ([v] if v else [])
        self.api._resolve_profile = MagicMock(return_value=_profile(preferred_cities=["Ajman"]))

    def test_search_flow_city_resumes_search_not_cv(self):
        """City requested by a gated search (no `_pending_cv_generate`) → the
        resolver returns a re-dispatch marker, NEVER a CV draft."""
        ctx = {"_pending_field": "preferred_cities",
               "_pending_search_message": "find me a job"}
        self.api._get_recent_context = MagicMock(return_value=dict(ctx))
        cv_spy = MagicMock(return_value={"type": "cv_draft", "message": "draft"})
        self.api._handle_cv_generate_from_profile = cv_spy

        with patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = self.api._resolve_pending_field(
                "roben@example.com", "Ajman", _profile()
            )

        assert result is not None
        assert result.get("_redispatch_message") == "find me a job"
        assert result.get("type") != "cv_draft"
        cv_spy.assert_not_called()
        saved = mock_upsert.call_args[1]["updates"]
        assert saved["preferred_cities"] == ["Ajman"]

    def test_search_flow_without_stored_message_defaults_to_profile_match(self):
        """Inference path (role-suggestion "which city?") has no stored search
        message — it must still resume a profile-match search, not a CV draft."""
        ctx = {"_pending_field": "preferred_cities"}
        self.api._get_recent_context = MagicMock(return_value=dict(ctx))
        cv_spy = MagicMock(return_value={"type": "cv_draft", "message": "draft"})
        self.api._handle_cv_generate_from_profile = cv_spy

        with patch("src.rico_chat_api.upsert_profile"):
            result = self.api._resolve_pending_field(
                "roben@example.com", "Ajman", _profile()
            )

        assert result.get("_redispatch_message") == "find matching jobs"
        cv_spy.assert_not_called()

    def test_cv_builder_flow_still_returns_cv_draft(self):
        """CV builder sets `_pending_cv_generate` → the resolver must still build
        the CV draft (regression guard for the existing CV-continuity flow)."""
        ctx = {"_pending_field": "preferred_cities", "_pending_cv_generate": True}
        self.api._get_recent_context = MagicMock(return_value=dict(ctx))
        cv_spy = MagicMock(return_value={"type": "cv_draft", "message": "draft"})
        self.api._handle_cv_generate_from_profile = cv_spy

        with patch("src.rico_chat_api.upsert_profile"):
            result = self.api._resolve_pending_field(
                "roben@example.com", "Ajman", _profile()
            )

        assert result == {"type": "cv_draft", "message": "draft"}
        cv_spy.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Gate persists inline cities and never downgrades when a city is present
# ---------------------------------------------------------------------------

class TestGatePersistsInlineCity:
    def _make_api(self):
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI.__new__(RicoChatAPI)
        api.memory = MagicMock()
        api.agent = MagicMock()
        api.system = MagicMock()
        return api

    def test_inline_city_persisted_and_search_runs(self):
        """A completed user missing only preferred_cities who names a city in the
        search request must have it persisted and the search must run — no
        onboarding downgrade."""
        from src.rico_agent import RicoProfile

        api = self._make_api()
        partial = RicoProfile(
            user_id="roben@example.com",
            target_roles=["Senior HSE Manager"],
            years_experience=10.0,
            skills=["NEBOSH"],
            # preferred_cities intentionally absent
        )

        # Stateful upsert: writing preferred_cities is reflected on the next
        # get_profile read, exactly as the real repo behaves.
        def _apply_upsert(*, user_id, updates):
            for k, v in (updates or {}).items():
                setattr(partial, k, v)
            return partial

        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch("src.rico_chat_api.get_profile", return_value=partial), \
             patch("src.rico_chat_api.set_onboarding_status") as mock_set, \
             patch("src.rico_chat_api.upsert_profile",
                   side_effect=_apply_upsert) as mock_upsert, \
             patch.object(api, "_handle_active_user",
                          return_value={"type": "job_matches", "matches": []}) as mock_active:
            response = api.process_message(
                "roben@example.com",
                "Find me Senior HSE Manager jobs in Dubai and Abu Dhabi.",
            )

        # City persisted from the inline mention
        assert mock_upsert.called
        saved = mock_upsert.call_args[1]["updates"]
        assert saved["preferred_cities"] == ["Dubai", "Abu Dhabi"]
        # Gate passed → search ran, no downgrade
        assert response["type"] != "onboarding"
        mock_active.assert_called_once()
        mock_set.assert_not_called()

    def test_no_inline_city_still_downgrades_and_arms_pending(self):
        """A search request with NO city still downgrades (unchanged) and arms
        the pending-city marker so the next reply resolves the search."""
        from src.rico_agent import RicoProfile

        api = self._make_api()
        stored_ctx: dict = {}
        api._get_recent_context = MagicMock(side_effect=lambda uid: dict(stored_ctx))
        api._store_recent_context = MagicMock(
            side_effect=lambda uid, ctx: stored_ctx.update(ctx)
        )
        partial = RicoProfile(
            user_id="roben@example.com",
            target_roles=["Senior HSE Manager"],
            years_experience=10.0,
            skills=["NEBOSH"],
        )

        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch("src.rico_chat_api.get_profile", return_value=partial), \
             patch("src.rico_chat_api.set_onboarding_status"), \
             patch("src.rico_chat_api.upsert_profile") as mock_upsert, \
             patch.object(api, "_handle_active_user") as mock_active:
            response = api.process_message("roben@example.com", "find me a job")

        assert response["type"] == "onboarding"
        assert "preferred_cities" in response.get("missing_fields", [])
        # No city → no city persisted
        assert not mock_upsert.called
        # Pending marker armed for the follow-up reply
        assert stored_ctx.get("_pending_field") == "preferred_cities"
        assert stored_ctx.get("_pending_search_message") == "find me a job"
        mock_active.assert_not_called()
