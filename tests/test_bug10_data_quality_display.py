"""
tests/test_bug10_data_quality_display.py

Regression tests for BUG-10 — data-quality display bugs found in the
2026-06-30 smoke test: "30.0 years experience displayed" and a salary
inconsistency.

Two distinct un-rounded-float bugs, both in src/rico_chat_api.py:

  Fix A — ``_target_role_search_response`` interpolated the raw
          ``years_experience`` profile value (a float from the DB, e.g.
          ``30.0``) straight into the user-facing search-confirmation
          message instead of rounding it like every other call site in
          this file does (``int(float(years))``). Users saw
          "~30.0 years experience" instead of "~30 years experience".

  Fix B — ``_format_pref_changes`` (the shared BUG-04 profile-update
          consent/acknowledgement formatter) rendered
          ``salary_expectation_aed`` with a bare ``str(value)`` fallback, so a
          float salary (e.g. ``18000.0``) rendered as "AED 18000.0/month" —
          no thousands separator and a stray ``.0`` — inconsistent with the
          clean "AED 18,000/month" format used everywhere else (e.g. the
          salary readback handler and the profile summary).

These tests must NOT touch the live database — every persistence/search
call is mocked.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


class TestYearsExperienceDisplayRounded:
    """~30.0 years experience must never reach the user verbatim."""

    def _profile(self, years_experience):
        return SimpleNamespace(
            user_id="roben@example.com",
            has_cv=True,
            target_roles=["HSE Manager"],
            skills=["ISO 14001"],
            certifications=[],
            years_experience=years_experience,
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

    def test_float_years_experience_rounded_in_search_message(self, monkeypatch):
        api = self._api(monkeypatch)
        result = api._target_role_search_response(
            "roben@example.com", "HSE Manager", self._profile(30.0)
        )
        assert "30.0" not in result["message"]
        assert "~30 years experience" in result["message"]

    def test_integer_years_experience_unaffected(self, monkeypatch):
        api = self._api(monkeypatch)
        result = api._target_role_search_response(
            "roben@example.com", "HSE Manager", self._profile(8)
        )
        assert "~8 years experience" in result["message"]

    def test_missing_years_experience_omits_basis_clause(self, monkeypatch):
        api = self._api(monkeypatch)
        result = api._target_role_search_response(
            "roben@example.com", "HSE Manager", self._profile(None)
        )
        assert "years experience" not in result["message"]


class TestSalaryDisplayConsistent:
    """A float salary must render the same clean AED format everywhere."""

    def test_format_pref_changes_rounds_float_salary(self):
        from src.rico_chat_api import RicoChatAPI

        lines = RicoChatAPI._format_pref_changes({"salary_expectation_aed": 18000.0})
        joined = "\n".join(lines)
        assert "AED 18000.0" not in joined
        assert "**Salary expectation** → AED 18,000/month" in joined

    def test_format_pref_changes_handles_integer_salary(self):
        from src.rico_chat_api import RicoChatAPI

        lines = RicoChatAPI._format_pref_changes({"salary_expectation_aed": 18000})
        joined = "\n".join(lines)
        assert "**Salary expectation** → AED 18,000/month" in joined
