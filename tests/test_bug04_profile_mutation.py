"""
tests/test_bug04_profile_mutation.py

Regression tests for BUG-04 — unauthorized profile mutation.

Problem:
  Rico persisted profile changes that were inferred from casual conversation
  or job searches, without explicit user consent. Smoke evidence:
  ``preferred_cities = "Dubai"`` was written autonomously after the user merely
  mentioned Dubai in chat.

Three distinct mutation paths were closed:

  Fix A — the ``profile_update`` intent used to "persist them, THEN confirm".
          It now stashes the extracted preferences and ASKS first; the DB write
          happens only on an explicit affirmative (the ``confirm_profile_update``
          branch of ``_resolve_pending_field``).

  Fix B — ``_target_role_search_response`` used to auto-append the searched role
          to ``target_roles`` and persist it. Searching is no longer consent to
          mutate the profile; the role is used for the current search only.

  Fix C — the agent ``ProfileContextResolver`` hydrated the profile from chat via
          spaCy NER and persisted the result. Chat-inferred values now enrich the
          in-memory profile for the current request only and are stripped from
          the DB write.

These tests must NOT touch the live database — every persistence call is mocked.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


# ===========================================================================
# Fix A — profile_update consent gate (_resolve_pending_field)
# ===========================================================================

class TestProfileUpdateConsentGate:
    """A pending profile update must persist only on explicit confirmation."""

    def _run(self, message: str, prefs):
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI()
        ctx = {
            "_pending_field": "confirm_profile_update",
            "_pending_profile_update": prefs,
        }
        mock_profile = MagicMock()

        with patch.object(api, "_get_recent_context", return_value=ctx), \
             patch.object(api, "_store_recent_context"), \
             patch.object(api, "_append_chat"), \
             patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._resolve_pending_field(
                user_id="test@example.com",
                message=message,
                profile=mock_profile,
            )
        return result, mock_upsert, ctx

    def test_yes_persists_pending_update(self):
        result, mock_upsert, ctx = self._run("yes", {"preferred_cities": ["Dubai"]})
        assert result is not None
        assert result["type"] == "preferences_updated"
        mock_upsert.assert_called_once_with(
            user_id="test@example.com",
            updates={"preferred_cities": ["Dubai"]},
        )
        # One-shot: pending state must be cleared after confirmation.
        assert "_pending_field" not in ctx
        assert "_pending_profile_update" not in ctx

    def test_no_cancels_without_persisting(self):
        result, mock_upsert, ctx = self._run("no", {"preferred_cities": ["Dubai"]})
        assert result is not None
        assert result["type"] == "info"
        mock_upsert.assert_not_called()
        assert "_pending_field" not in ctx
        assert "_pending_profile_update" not in ctx

    def test_unrelated_reply_does_not_persist_and_falls_through(self):
        """A new command instead of yes/no cancels the pending write and routes on."""
        result, mock_upsert, ctx = self._run(
            "find HSE Manager jobs in Dubai", {"preferred_cities": ["Dubai"]}
        )
        # Returns None so the new message routes normally through intent classification.
        assert result is None
        mock_upsert.assert_not_called()
        # Pending must still be cleared so it can never apply on a later turn.
        assert "_pending_field" not in ctx
        assert "_pending_profile_update" not in ctx

    def test_yes_with_empty_pending_does_not_persist(self):
        result, mock_upsert, _ = self._run("yes", {})
        mock_upsert.assert_not_called()

    def test_arabic_yes_persists(self):
        result, mock_upsert, _ = self._run("نعم", {"preferred_cities": ["Dubai"]})
        assert result is not None
        assert result["type"] == "preferences_updated"
        mock_upsert.assert_called_once()


class TestProfileUpdateHelper:
    """The shared label formatter underpins both the ask and the acknowledgement."""

    def test_format_pref_changes_labels_and_salary(self):
        from src.rico_chat_api import RicoChatAPI

        lines = RicoChatAPI._format_pref_changes(
            {"preferred_cities": ["Dubai", "Abu Dhabi"], "salary_expectation_aed": 18000}
        )
        joined = "\n".join(lines)
        assert "**Preferred city** → Dubai, Abu Dhabi" in joined
        assert "**Salary expectation** → AED 18,000/month" in joined

    def test_format_pref_changes_empty(self):
        from src.rico_chat_api import RicoChatAPI

        assert RicoChatAPI._format_pref_changes({}) == []


# ===========================================================================
# Fix B — searching a role must not persist it to target_roles
# ===========================================================================

class TestSearchDoesNotPersistRole:

    def _profile(self):
        return SimpleNamespace(
            user_id="roben@example.com",
            has_cv=True,
            target_roles=["HSE Manager"],
            skills=["ISO 14001"],
            certifications=[],
            years_experience=10,
            industries=[],
            preferred_cities=["Dubai"],
            current_role="HSE Officer",
        )

    def _api(self, monkeypatch):
        from src.rico_chat_api import RicoChatAPI
        from src.jsearch_client import FetchResult

        api = RicoChatAPI(persist=False)
        api.memory = MagicMock()
        api.system = MagicMock()
        api.system.run_for_profile.return_value = {"matches": []}
        api.openai_agent = MagicMock()

        monkeypatch.setattr(api, "_search_jsearch_meta", lambda *a, **k: FetchResult(items=[]))
        monkeypatch.setattr(api, "_enrich_with_role_intelligence", lambda *a, **k: None)
        monkeypatch.setattr(
            api, "_begin_job_search_operation", lambda _u, _r: {"operation_id": "op-test"}
        )
        monkeypatch.setattr("src.rico_chat_api.mark_completed", lambda *a, **k: None)
        monkeypatch.setattr("src.rico_chat_api.mark_failed", lambda *a, **k: None)
        return api

    def test_searching_new_role_does_not_upsert(self, monkeypatch):
        api = self._api(monkeypatch)
        with patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            # "Data Analyst" is NOT in target_roles → previously auto-persisted.
            api._target_role_search_response("roben@example.com", "Data Analyst", self._profile())
        mock_upsert.assert_not_called()

    def test_searching_existing_role_does_not_upsert(self, monkeypatch):
        api = self._api(monkeypatch)
        with patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            api._target_role_search_response("roben@example.com", "HSE Manager", self._profile())
        mock_upsert.assert_not_called()


# ===========================================================================
# Fix C — agent resolver must not persist chat-NER-inferred preferences
# ===========================================================================

class TestResolverDoesNotPersistChatInference:

    def _resolver_with_mocks(self, base_profile, monkeypatch):
        """Build a ProfileContextResolver with all DB/NLP dependencies mocked."""
        import src.agent.context.resolver as resolver_mod
        from src.agent.context.resolver import ProfileContextResolver

        resolver = ProfileContextResolver()

        # Force the chat-hydration branch to run (it is gated on `_nlp`).
        monkeypatch.setattr(resolver_mod, "_nlp", object())
        monkeypatch.setattr(resolver_mod, "get_profile", lambda _uid: base_profile)

        # Keep action hydration and audit lookups out of the DB. Production's
        # _hydrate_from_actions always sets behavior_signals (read later by
        # resolve()), so the mock mirrors that to stay faithful.
        def _fake_actions(p, _uid):
            p.behavior_signals = {}
            return p

        monkeypatch.setattr(resolver, "_hydrate_from_actions", _fake_actions)
        monkeypatch.setattr(resolver, "_load_question_history", lambda _uid: {})
        monkeypatch.setattr(resolver, "_load_behavior_signals", lambda _uid: {})
        return resolver, resolver_mod

    def test_chat_inferred_city_not_persisted_but_cv_city_kept(self, monkeypatch):
        from src.rico_agent import RicoProfile

        base = RicoProfile(user_id="test@example.com")
        base.preferred_cities = []

        resolver, resolver_mod = self._resolver_with_mocks(base, monkeypatch)

        # CV hydration sets a legitimate city; chat NER then "infers" Dubai.
        def fake_cv(profile, _cv):
            profile.preferred_cities = ["Abu Dhabi"]
            return profile

        def fake_chat(profile, _history):
            profile.preferred_cities.append("Dubai")  # NER inference from chat
            return profile

        monkeypatch.setattr(resolver, "_hydrate_from_cv", fake_cv)
        monkeypatch.setattr(resolver, "_hydrate_from_chat", fake_chat)

        captured = {}
        monkeypatch.setattr(
            resolver_mod, "upsert_profile",
            lambda user_id, updates: captured.update(updates) or base,
        )

        ctx = resolver.resolve(
            "test@example.com",
            cv_data={"some": "cv"},
            chat_history=[{"role": "user", "content": "jobs in Dubai please"}],
            force_refresh=True,
        )

        # The DB write must keep the CV city and DROP the chat-inferred city.
        assert "preferred_cities" in captured
        assert "Dubai" not in captured["preferred_cities"], (
            f"chat-inferred city must not be persisted: {captured['preferred_cities']!r}"
        )
        assert captured["preferred_cities"] == ["Abu Dhabi"]

        # …but the in-memory profile for THIS request keeps the enrichment.
        assert "Dubai" in ctx.profile.preferred_cities
        assert "Abu Dhabi" in ctx.profile.preferred_cities

    def test_chat_only_city_never_reaches_db(self, monkeypatch):
        from src.rico_agent import RicoProfile

        base = RicoProfile(user_id="test@example.com")
        base.preferred_cities = []

        resolver, resolver_mod = self._resolver_with_mocks(base, monkeypatch)

        def fake_chat(profile, _history):
            profile.preferred_cities = ["Dubai"]  # the smoke-evidence case
            return profile

        monkeypatch.setattr(resolver, "_hydrate_from_chat", fake_chat)

        captured = {}
        called = {"n": 0}

        def fake_upsert(user_id, updates):
            called["n"] += 1
            captured.update(updates)
            return base

        monkeypatch.setattr(resolver_mod, "upsert_profile", fake_upsert)

        ctx = resolver.resolve(
            "test@example.com",
            chat_history=[{"role": "user", "content": "I want to work in Dubai"}],
            force_refresh=True,
        )

        # Even if a write happens for other reasons, Dubai must not be in it.
        assert "Dubai" not in captured.get("preferred_cities", [])
        # In-memory enrichment is preserved for the current request.
        assert ctx.profile.preferred_cities == ["Dubai"]

    def test_chat_inferred_role_not_persisted(self, monkeypatch):
        from src.rico_agent import RicoProfile

        base = RicoProfile(user_id="test@example.com")
        base.target_roles = []

        resolver, resolver_mod = self._resolver_with_mocks(base, monkeypatch)

        def fake_chat(profile, _history):
            profile.target_roles = ["Pilot"]  # casually mentioned in chat
            return profile

        monkeypatch.setattr(resolver, "_hydrate_from_chat", fake_chat)

        captured = {}
        monkeypatch.setattr(
            resolver_mod, "upsert_profile",
            lambda user_id, updates: captured.update(updates) or base,
        )

        resolver.resolve(
            "test@example.com",
            chat_history=[{"role": "user", "content": "maybe i could be a Pilot"}],
            force_refresh=True,
        )

        assert "Pilot" not in captured.get("target_roles", [])


# ===========================================================================
# Regression — legitimate, explicit-consent paths must still persist
# ===========================================================================

class TestLegitimatePathsStillPersist:
    """BUG-04 fixes must not break writes that DO carry explicit user consent."""

    def test_explicit_pending_telegram_answer_still_persists(self):
        """Answering Rico's 'what is your Telegram?' prompt is consent → still saves."""
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI()
        ctx = {"_pending_field": "telegram_username"}
        mock_profile = MagicMock()

        with patch.object(api, "_get_recent_context", return_value=ctx), \
             patch.object(api, "_store_recent_context"), \
             patch.object(api, "_append_chat"), \
             patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            result = api._resolve_pending_field(
                user_id="test@example.com", message="@Robin_amg", profile=mock_profile,
            )

        assert result is not None
        assert result["type"] == "preferences_updated"
        mock_upsert.assert_called_once_with(
            user_id="test@example.com", updates={"telegram_username": "@Robin_amg"},
        )
