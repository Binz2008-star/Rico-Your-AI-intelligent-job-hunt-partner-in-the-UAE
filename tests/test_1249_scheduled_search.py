"""
Tests for Issue #1249 Phase A — scheduled saved searches (backend, inert).

Covers the acceptance criteria that belong to this phase:
- AR/EN natural-language parsing (Dubai, AED 10k+, daily cadence).
- Canonicalization: repeating the command reuses ONE canonical search.
- Deterministic intent routing (create/pause/resume/delete/status) without
  swallowing plain one-shot searches.
- Honest salary behaviour: stated-below-minimum excluded, unknown salary kept
  and labeled, never fabricated.
- Cross-run dedup and lifecycle exclusions; every job carries a real link.
- Kill switch (default OFF) and dry-run semantics of the sweep.
- Cron endpoint auth (X-Cron-Secret) and the authenticated status endpoint's
  JWT-only identity (cross-user isolation).
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.services import scheduled_search_service as sss


AR_CMD = "ابحث يوميًا عن وظائف مناسبة في دبي براتب 10,000+ درهم"
EN_CMD = "search daily for jobs in Dubai with salary 10,000+ AED"


# ── Parsing ──────────────────────────────────────────────────────────────────

class TestParsing:
    def test_arabic_command_parses_city_salary_cadence(self):
        p = sss.parse_scheduled_search_command(AR_CMD)
        assert p == {"cadence": "daily", "city": "Dubai", "min_salary_aed": 10000}

    def test_english_command_parses_city_salary_cadence(self):
        p = sss.parse_scheduled_search_command(EN_CMD)
        assert p == {"cadence": "daily", "city": "Dubai", "min_salary_aed": 10000}

    def test_arabic_indic_digits_parse(self):
        p = sss.parse_scheduled_search_command("ابحث يوميًا عن وظائف في دبي براتب ١٠٠٠٠ درهم")
        assert p is not None and p["min_salary_aed"] == 10000

    def test_10k_shorthand(self):
        p = sss.parse_scheduled_search_command("find jobs daily in Abu Dhabi, 10k AED minimum")
        assert p is not None
        assert p["city"] == "Abu Dhabi"
        assert p["min_salary_aed"] == 10000

    def test_no_currency_marker_means_no_salary_constraint(self):
        p = sss.parse_scheduled_search_command("search daily for 10000 jobs in Dubai")
        assert p is not None
        assert p["min_salary_aed"] is None  # number without AED/درهم is not a salary

    def test_no_city_is_allowed(self):
        p = sss.parse_scheduled_search_command("ابحث يوميا عن وظائف براتب 8,000 درهم")
        assert p is not None and p["city"] is None and p["min_salary_aed"] == 8000

    def test_plain_search_is_not_scheduled(self):
        # No cadence marker → must stay a normal one-shot search.
        assert sss.parse_scheduled_search_command("ابحث عن وظائف مدير سلامة في دبي") is None
        assert sss.parse_scheduled_search_command("find me HSE jobs in Dubai") is None

    def test_arabic_today_is_not_daily(self):
        # اليوم ("today") must not be read as a daily cadence.
        assert sss.parse_scheduled_search_command("ابحث عن وظائف اليوم في دبي") is None

    def test_daily_without_search_verb_is_not_scheduled(self):
        assert sss.parse_scheduled_search_command("daily paid jobs in Dubai") is None

    def test_management_commands(self):
        assert sss.parse_management_command("أوقف البحث اليومي") == "pause"
        assert sss.parse_management_command("pause my daily search") == "pause"
        assert sss.parse_management_command("استأنف البحث اليومي") == "resume"
        assert sss.parse_management_command("resume the daily search") == "resume"
        assert sss.parse_management_command("احذف البحث اليومي") == "delete"
        assert sss.parse_management_command("delete my daily search") == "delete"
        assert sss.parse_management_command("ما حالة البحث اليومي") == "status"
        assert sss.parse_management_command("show my daily search status") == "status"

    def test_management_requires_search_noun(self):
        assert sss.parse_management_command("stop showing me jobs") is None


# ── Canonicalization ─────────────────────────────────────────────────────────

class TestCanonicalization:
    def test_same_params_same_canonical_query_across_languages(self):
        ar = sss.parse_scheduled_search_command(AR_CMD)
        en = sss.parse_scheduled_search_command(EN_CMD)
        assert sss.canonical_query(ar) == sss.canonical_query(en)

    def test_repeat_command_upserts_single_canonical_row(self):
        """Repeating the command targets the SAME query key (DB UNIQUE upserts)."""
        saved_queries = []

        def fake_save(user_id, query, filters, search_id=None):
            saved_queries.append(query)
            return "id-1"

        with patch("src.repositories.profile_repo.save_search", side_effect=fake_save), \
             patch("src.repositories.profile_repo.list_saved_searches", return_value=[]):
            r1 = sss.create_or_update_scheduled_search("alice@rico.ai", AR_CMD)
            r2 = sss.create_or_update_scheduled_search("alice@rico.ai", EN_CMD)
        assert r1["outcome"] == "created" and r2["outcome"] == "created"
        assert saved_queries[0] == saved_queries[1]  # one canonical identity

    def test_update_preserves_run_history_and_dedup_memory(self):
        params = sss.parse_scheduled_search_command(EN_CMD)
        query = sss.canonical_query(params)
        existing_row = {
            "id": "42", "query": query,
            "filters": {"schedule": {
                "enabled": True, "cadence": "daily", "city": "Dubai",
                "min_salary_aed": 10000, "created_at": "2026-07-01T00:00:00+00:00",
                "last_run_at": "2026-07-19T05:00:00+00:00", "last_run_new": 3,
                "delivered_keys": ["k1", "k2"], "last_results": [{"title": "X"}],
            }},
        }
        captured = {}

        def fake_save(user_id, q, filters, search_id=None):
            captured.update(filters["schedule"])
            return "42"

        with patch("src.repositories.profile_repo.save_search", side_effect=fake_save), \
             patch("src.repositories.profile_repo.list_saved_searches", return_value=[existing_row]):
            r = sss.create_or_update_scheduled_search("alice@rico.ai", AR_CMD)
        assert r["outcome"] == "updated"
        assert captured["delivered_keys"] == ["k1", "k2"]
        assert captured["last_run_at"] == "2026-07-19T05:00:00+00:00"
        assert captured["created_at"] == "2026-07-01T00:00:00+00:00"


# ── Intent routing ───────────────────────────────────────────────────────────

class TestIntentRouting:
    def test_create_commands_classify(self):
        from src.agent.intelligence.intent_classifier import classify_intent

        for cmd in (AR_CMD, EN_CMD, "find me jobs every day in Sharjah"):
            r = classify_intent(cmd)
            assert r.intent == "scheduled_search_create", f"{cmd!r} → {r.intent!r}"

    def test_management_commands_classify(self):
        from src.agent.intelligence.intent_classifier import classify_intent

        assert classify_intent("أوقف البحث اليومي").intent == "scheduled_search_pause"
        assert classify_intent("delete my daily search").intent == "scheduled_search_delete"
        assert classify_intent("resume my daily search").intent == "scheduled_search_resume"
        assert classify_intent("show my daily search status").intent == "scheduled_search_status"

    def test_plain_searches_not_swallowed(self):
        from src.agent.intelligence.intent_classifier import classify_intent

        assert not classify_intent("ابحث عن وظائف مدير سلامة في دبي").intent.startswith("scheduled_search")
        assert not classify_intent("find me Senior HSE Manager jobs in Dubai").intent.startswith("scheduled_search")


# ── Honest salary extraction ─────────────────────────────────────────────────

class TestSalaryExtraction:
    def test_missing_salary_is_unknown_never_invented(self):
        known, amount = sss.extract_salary_aed({"title": "X", "company": "Y"})
        assert known is False and amount is None

    def test_numeric_salary_field(self):
        assert sss.extract_salary_aed({"salary_min": 12000}) == (True, 12000)

    def test_string_salary_parses(self):
        known, amount = sss.extract_salary_aed({"salary": "AED 9,500 per month"})
        assert known is True and amount == 9500


# ── Constrained matching ─────────────────────────────────────────────────────

def _engine_result(matches):
    return {"status": "completed", "matches": matches}


_BASE_MATCH = {
    "title": "HSE Manager", "company": "ACME", "location": "Dubai, AE",
    "link": "https://jobs.example.com/1", "score": 90, "rico_explanation": "fit",
}


class TestConstrainedMatching:
    def _run(self, matches, schedule, excluded=None):
        system = MagicMock()
        system.run_for_profile.return_value = _engine_result(matches)
        with patch("src.rico_repo_adapter.RicoSystem", return_value=system), \
             patch.object(sss, "_excluded_pair_keys", return_value=excluded or set()), \
             patch.object(sss, "_min_score_for", return_value=60):
            return sss.find_constrained_matches({"p": 1}, "alice@rico.ai", schedule)

    def test_known_salary_below_minimum_excluded(self):
        low = {**_BASE_MATCH, "salary_min": 8000}
        out = self._run([low], {"city": "Dubai", "min_salary_aed": 10000})
        assert out == []

    def test_unknown_salary_kept_and_labeled(self):
        out = self._run([dict(_BASE_MATCH)], {"city": "Dubai", "min_salary_aed": 10000})
        assert len(out) == 1
        assert out[0]["salary_known"] is False
        assert out[0]["salary_aed"] is None  # never fabricated

    def test_known_salary_above_minimum_kept(self):
        good = {**_BASE_MATCH, "salary_min": 12000}
        out = self._run([good], {"city": "Dubai", "min_salary_aed": 10000})
        assert len(out) == 1 and out[0]["salary_aed"] == 12000 and out[0]["salary_known"] is True

    def test_city_constraint_enforced(self):
        abu = {**_BASE_MATCH, "location": "Abu Dhabi, AE"}
        out = self._run([abu], {"city": "Dubai", "min_salary_aed": None})
        assert out == []

    def test_lifecycle_exclusions(self):
        out = self._run([dict(_BASE_MATCH)], {"city": None, "min_salary_aed": None},
                        excluded={"hse manager|acme"})
        assert out == []

    def test_delivered_dedup_across_runs(self):
        from src.applications import get_job_id

        key = get_job_id({"title": "HSE Manager", "company": "ACME",
                          "location": "Dubai, AE", "link": "https://jobs.example.com/1"})
        out = self._run([dict(_BASE_MATCH)], {"city": None, "min_salary_aed": None,
                                              "delivered_keys": [key]})
        assert out == []

    def test_job_without_link_never_surfaced(self):
        nolink = {**_BASE_MATCH, "link": ""}
        out = self._run([nolink], {"city": None, "min_salary_aed": None})
        assert out == []


# ── Sweep: kill switch + dry run ─────────────────────────────────────────────

class TestSweep:
    def test_kill_switch_default_off_no_op(self, monkeypatch):
        monkeypatch.delenv("RICO_ENABLE_SCHEDULED_SEARCHES", raising=False)
        with patch("src.repositories.profile_repo.list_enabled_scheduled_searches") as roster:
            summary = sss.run_scheduled_search_sweep()
        assert summary["status"] == "disabled"
        roster.assert_not_called()

    def test_dry_run_evaluates_without_persisting(self, monkeypatch):
        monkeypatch.delenv("RICO_ENABLE_SCHEDULED_SEARCHES", raising=False)
        row = {"id": "7", "query": "q", "external_user_id": "alice@rico.ai",
               "filters": {"schedule": {"enabled": True, "city": None, "min_salary_aed": None}}}
        with patch("src.repositories.profile_repo.list_enabled_scheduled_searches", return_value=[row]), \
             patch("src.repositories.profile_repo.get_profile", return_value={"p": 1}), \
             patch("src.repositories.profile_repo.save_search") as save, \
             patch.object(sss, "find_constrained_matches", return_value=[{"job_key": "k",
                                                                          "title": "T"}]):
            summary = sss.run_scheduled_search_sweep(dry_run=True)
        assert summary["status"] == "ok"
        assert summary["new_results"] == 1
        assert summary["dry_run"] is True
        save.assert_not_called()  # dry run must not write anything

    def test_enabled_run_persists_results_and_dedup_keys(self, monkeypatch):
        monkeypatch.setenv("RICO_ENABLE_SCHEDULED_SEARCHES", "true")
        row = {"id": "7", "query": "q", "external_user_id": "alice@rico.ai",
               "filters": {"schedule": {"enabled": True, "city": None, "min_salary_aed": None,
                                        "delivered_keys": ["old"]}}}
        saved = {}

        def fake_save(user_id, query, filters, search_id=None):
            saved.update(filters["schedule"])
            return "7"

        with patch("src.repositories.profile_repo.list_enabled_scheduled_searches", return_value=[row]), \
             patch("src.repositories.profile_repo.get_profile", return_value={"p": 1}), \
             patch("src.repositories.profile_repo.save_search", side_effect=fake_save), \
             patch.object(sss, "find_constrained_matches",
                          return_value=[{"job_key": "new-key", "title": "T"}]):
            summary = sss.run_scheduled_search_sweep()
        assert summary["status"] == "ok" and summary["new_results"] == 1
        assert saved["last_run_new"] == 1
        assert saved["delivered_keys"] == ["old", "new-key"]
        assert saved["last_results"] == [{"job_key": "new-key", "title": "T"}]
        assert saved["last_run_at"]

    def test_no_matches_keeps_previous_results_visible(self, monkeypatch):
        monkeypatch.setenv("RICO_ENABLE_SCHEDULED_SEARCHES", "true")
        prev = [{"job_key": "old", "title": "Old"}]
        row = {"id": "7", "query": "q", "external_user_id": "alice@rico.ai",
               "filters": {"schedule": {"enabled": True, "city": None, "min_salary_aed": None,
                                        "last_results": prev}}}
        saved = {}

        def fake_save(user_id, query, filters, search_id=None):
            saved.update(filters["schedule"])
            return "7"

        with patch("src.repositories.profile_repo.list_enabled_scheduled_searches", return_value=[row]), \
             patch("src.repositories.profile_repo.get_profile", return_value={"p": 1}), \
             patch("src.repositories.profile_repo.save_search", side_effect=fake_save), \
             patch.object(sss, "find_constrained_matches", return_value=[]):
            summary = sss.run_scheduled_search_sweep()
        assert summary["new_results"] == 0
        assert saved["last_results"] == prev  # no noisy reset on a no-match day


# ── Chat handler guardrails ──────────────────────────────────────────────────

class TestChatHandler:
    def test_public_identity_gets_signin_prompt_and_never_persists(self):
        with patch("src.repositories.profile_repo.save_search") as save:
            resp = sss.handle_chat_intent("public-session-abc", "scheduled_search_create", EN_CMD)
        assert resp["action"] == "signin_required"
        save.assert_not_called()

    def test_create_returns_structured_confirmation(self):
        with patch("src.repositories.profile_repo.save_search", return_value="id-1"), \
             patch("src.repositories.profile_repo.list_saved_searches", return_value=[]), \
             patch("src.repositories.profile_repo.get_profile", return_value={"target_roles": ["HSE Manager"]}):
            resp = sss.handle_chat_intent("alice@rico.ai", "scheduled_search_create", AR_CMD, arabic=True)
        assert resp["type"] == "scheduled_search"
        assert resp["action"] == "created"
        assert resp["schedule"]["city"] == "Dubai"
        assert resp["schedule"]["min_salary_aed"] == 10000
        assert "دبي" in resp["message"] or "Dubai" in resp["message"]

    def test_delete_reports_affected_count(self):
        items = [{"id": "1", "query": "q", "schedule": {"enabled": True}}]
        with patch.object(sss, "get_user_schedules", return_value=items), \
             patch("src.repositories.profile_repo.delete_search", return_value=True):
            resp = sss.handle_chat_intent("alice@rico.ai", "scheduled_search_delete", "delete my daily search")
        assert resp["action"] == "deleted" and resp["affected"] == 1


# ── Endpoints ────────────────────────────────────────────────────────────────

class TestEndpoints:
    def _client(self):
        from fastapi.testclient import TestClient
        from src.api.app import app

        return TestClient(app, raise_server_exceptions=False)

    def test_cron_endpoint_fails_closed_without_secret_configured(self, monkeypatch):
        monkeypatch.delenv("RICO_CRON_SECRET", raising=False)
        r = self._client().post("/api/v1/pipeline/scheduled-searches")
        assert r.status_code == 503

    def test_cron_endpoint_rejects_wrong_secret(self, monkeypatch):
        monkeypatch.setenv("RICO_CRON_SECRET", "s3cret")
        r = self._client().post("/api/v1/pipeline/scheduled-searches",
                                headers={"X-Cron-Secret": "wrong"})
        assert r.status_code == 403

    def test_cron_endpoint_runs_sweep_with_secret(self, monkeypatch):
        monkeypatch.setenv("RICO_CRON_SECRET", "s3cret")
        with patch("src.services.scheduled_search_service.run_scheduled_search_sweep",
                   return_value={"status": "disabled", "searches": 0, "users": 0,
                                 "new_results": 0, "skipped": 0, "failed": 0,
                                 "dry_run": True}) as sweep:
            r = self._client().post("/api/v1/pipeline/scheduled-searches?dry_run=true",
                                    headers={"X-Cron-Secret": "s3cret"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "disabled"
        sweep.assert_called_once_with(dry_run=True)

    def test_status_endpoint_requires_auth(self):
        r = self._client().get("/api/v1/rico/scheduled-searches")
        assert r.status_code in (401, 403)

    def test_status_endpoint_uses_jwt_identity_only(self):
        """Identity comes from the JWT — the endpoint asks the service for the
        authenticated user's schedules and nothing else (cross-user isolation)."""
        from src.api.auth import create_access_token

        client = self._client()
        client.cookies.set("access_token",
                           create_access_token({"sub": "alice@rico.ai", "role": "user"}))
        with patch("src.services.scheduled_search_service.get_user_schedules",
                   return_value=[{"id": "1", "query": "q",
                                  "schedule": {"enabled": True}}]) as gus:
            r = client.get("/api/v1/rico/scheduled-searches")
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 1
        gus.assert_called_once_with("alice@rico.ai")

    def test_toggle_endpoint_requires_auth(self):
        r = self._client().patch("/api/v1/rico/scheduled-searches/1",
                                 json={"enabled": False})
        assert r.status_code in (401, 403)

    def test_toggle_endpoint_scopes_to_jwt_identity(self):
        from src.api.auth import create_access_token

        client = self._client()
        client.cookies.set("access_token",
                           create_access_token({"sub": "alice@rico.ai", "role": "user"}))
        with patch("src.services.scheduled_search_service.set_schedule_enabled_by_id",
                   return_value=True) as setter:
            r = client.patch("/api/v1/rico/scheduled-searches/42",
                             json={"enabled": False})
        assert r.status_code == 200, r.text
        assert r.json() == {"id": "42", "enabled": False, "status": "updated"}
        setter.assert_called_once_with("alice@rico.ai", "42", False)

    def test_toggle_endpoint_404_for_foreign_or_unknown_id(self):
        """An id outside the caller's own schedules is a plain 404 — ids can't
        be probed or toggled cross-user."""
        from src.api.auth import create_access_token

        client = self._client()
        client.cookies.set("access_token",
                           create_access_token({"sub": "alice@rico.ai", "role": "user"}))
        with patch("src.services.scheduled_search_service.set_schedule_enabled_by_id",
                   return_value=False):
            r = client.patch("/api/v1/rico/scheduled-searches/999",
                             json={"enabled": True})
        assert r.status_code == 404


class TestShouldOfferScheduledSearch:
    """The contextual offer is per-user and scenario-gated: only an
    authenticated user WITHOUT an existing schedule ever sees it."""

    def test_public_identity_never_offered(self):
        assert sss.should_offer_scheduled_search("public-session-x") is False
        assert sss.should_offer_scheduled_search("") is False
        assert sss.should_offer_scheduled_search("e-" + "a" * 40) is False

    def test_user_with_schedule_not_offered(self):
        with patch.object(sss, "get_user_schedules",
                          return_value=[{"id": "1", "query": "q", "schedule": {"enabled": True}}]):
            assert sss.should_offer_scheduled_search("alice@rico.ai") is False

    def test_user_without_schedule_is_offered(self):
        with patch.object(sss, "get_user_schedules", return_value=[]):
            assert sss.should_offer_scheduled_search("alice@rico.ai") is True

    def test_lookup_failure_fails_quiet(self):
        with patch.object(sss, "get_user_schedules", side_effect=RuntimeError("db down")):
            assert sss.should_offer_scheduled_search("alice@rico.ai") is False


class TestSetScheduleEnabledById:
    def test_toggles_only_the_matching_schedule(self):
        items = [
            {"id": "1", "query": "q1", "schedule": {"enabled": True, "cadence": "daily"}},
            {"id": "2", "query": "q2", "schedule": {"enabled": True, "cadence": "daily"}},
        ]
        saved = {}

        def fake_save(user_id, query, filters, search_id=None):
            saved[search_id] = filters["schedule"]["enabled"]
            return search_id

        with patch.object(sss, "get_user_schedules", return_value=items), \
             patch("src.repositories.profile_repo.save_search", side_effect=fake_save):
            assert sss.set_schedule_enabled_by_id("alice@rico.ai", "2", False) is True
        assert saved == {"2": False}  # schedule 1 untouched

    def test_unknown_id_returns_false_without_writes(self):
        with patch.object(sss, "get_user_schedules", return_value=[]), \
             patch("src.repositories.profile_repo.save_search") as save:
            assert sss.set_schedule_enabled_by_id("alice@rico.ai", "404", True) is False
        save.assert_not_called()
