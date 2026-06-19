"""Regression tests for the P0 trust fixes.

P0-1  Settings excluded-keyword vs target-role conflict (contextual filtering).
P0-2  Profile-update must never claim a write that did not happen.
P0-3  "show/list my applications" must itemize rows, never dead-end with
      "Ask me to list my applications".
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


# ── P0-1: contextual exclusion filtering ──────────────────────────────────────

class TestExclusionRoleConflict:
    def test_excluded_token_overlapping_target_role_is_suppressed(self):
        from src.scoring import _role_conflicting_excludes

        suppressed = _role_conflicting_excludes(
            ["manager"], ["Environmental Manager"], "Environmental Manager - Dubai"
        )
        assert suppressed == {"manager"}

    def test_unrelated_job_keeps_exclusion(self):
        from src.scoring import _role_conflicting_excludes

        # "manager" overlaps the target role text, but this job title does NOT
        # match that role, so the exclusion must still apply.
        suppressed = _role_conflicting_excludes(
            ["manager"], ["Environmental Manager"], "Sales Manager - Dubai"
        )
        assert suppressed == set()

    def test_exclusion_not_part_of_role_is_kept(self):
        from src.scoring import _role_conflicting_excludes

        suppressed = _role_conflicting_excludes(
            ["contract"], ["Environmental Manager"], "Environmental Manager"
        )
        assert suppressed == set()

    def test_multiword_exclude_phrase_in_role(self):
        from src.scoring import _role_conflicting_excludes

        suppressed = _role_conflicting_excludes(
            ["sales manager"], ["Regional Sales Manager"], "Regional Sales Manager"
        )
        assert suppressed == {"sales manager"}

    def test_score_job_keeps_target_role_despite_exclusion(self, monkeypatch):
        import src.scoring as scoring

        monkeypatch.setenv("EXCLUDE_KEYWORDS", "manager")
        monkeypatch.setattr(scoring, "get_target_roles", lambda: ["Environmental Manager"])
        job = {"title": "Environmental Manager", "description": "environmental hse compliance role"}
        score = scoring.score_job(job)
        assert score > 0
        assert "ENV exclude" not in (job.get("hard_reject_reason") or "")

    def test_score_job_still_excludes_unrelated_manager(self, monkeypatch):
        import src.scoring as scoring

        monkeypatch.setenv("EXCLUDE_KEYWORDS", "manager")
        monkeypatch.setattr(scoring, "get_target_roles", lambda: ["Environmental Manager"])
        job = {"title": "Restaurant Manager", "description": "managing a restaurant team"}
        score = scoring.score_job(job)
        assert score == 0
        assert "ENV exclude" in (job.get("hard_reject_reason") or "")


# ── P0-2: profile update never fakes a write ──────────────────────────────────

def _profile():
    return SimpleNamespace(
        user_id="test@example.com",
        has_cv=True,
        target_roles=["Compliance Manager"],
        skills=["ISO 14001"],
        certifications=[],
        years_experience=8,
        industries=[],
        preferred_cities=["Dubai"],
        current_role="Senior Compliance Officer",
        name="Test User",
        email="test@example.com",
        phone=None,
        telegram_username=None,
        nationality=None,
        languages=[],
        education=None,
        cv_text="Sample CV text",
        pasted_cv_text=None,
        uploaded_documents=[],
        onboarding_state="completed",
        subscription_tier="free",
        visa_status=None,
        job_search_status=None,
        profile_strength=None,
    )


def _profile_update_api(monkeypatch, prefs):
    import src.rico_chat_api as mod
    from src.rico_chat_api import RicoChatAPI

    route = SimpleNamespace(
        tool_name=None,
        entities={},
        tool_args={"preferences": prefs} if prefs else {},
        confirmation_prompt=None,
        source="keyword",
    )
    writes: list[dict] = []

    monkeypatch.setattr(mod, "get_profile", lambda uid: _profile())
    monkeypatch.setattr(mod, "_route", lambda *a, **kw: route)
    monkeypatch.setattr(mod, "hf_ok", lambda: False)
    monkeypatch.setattr(
        mod, "upsert_profile",
        lambda user_id, updates: writes.append({"user_id": user_id, "updates": updates}) or _profile(),
    )

    api = RicoChatAPI(persist=False)
    api.memory = MagicMock()
    api.memory.get.return_value = None
    api.openai_agent = MagicMock()
    api.openai_agent.provider_available = False
    monkeypatch.setattr(api, "_resolve_profile", lambda _uid: _profile())
    monkeypatch.setattr(api, "_resolve_pending_field", lambda *a, **kw: None)
    monkeypatch.setattr(api, "_append_chat", lambda *a, **kw: None)
    return api, writes


@pytest.mark.parametrize("message", ["update my profile", "edit my profile", "تحديث ملفي"])
def test_bare_profile_update_does_not_fake_success(monkeypatch, message):
    api, writes = _profile_update_api(monkeypatch, prefs=None)
    response = api._handle_active_user("test@example.com", message)

    assert response["type"] == "profile_edit"
    assert response.get("route") == "/profile"
    assert writes == [], "no DB write may happen for a bare profile-update request"
    lowered = response["message"].lower()
    for claim in ("updated", "saved", "applied", "changed your", "done"):
        assert claim not in lowered, f"must not claim '{claim}' without a real write"


def test_concrete_profile_update_asks_before_persisting(monkeypatch):
    # BUG-04: profile updates must ask for confirmation BEFORE writing to DB.
    # The old behavior ("persists then confirms") was the bug being fixed.
    api, writes = _profile_update_api(monkeypatch, prefs={"target_roles": ["Data Analyst"]})
    monkeypatch.setattr(api, "_get_recent_context", lambda *a, **kw: {})
    monkeypatch.setattr(api, "_store_recent_context", lambda *a, **kw: None)
    response = api._handle_active_user("test@example.com", "update my profile")

    # Must ask for confirmation — no write may happen yet
    assert response["type"] == "clarification"
    assert writes == [], "no DB write may happen before user confirms"
    assert "Data Analyst" in response["message"]
    assert "yes" in response["message"].lower() or "confirm" in response["message"].lower() or "save" in response["message"].lower()


# ── P0-3: applications listing itemizes, never dead-ends ───────────────────────

class TestApplicationsTrackingMessage:
    def _api(self):
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI(persist=False)
        api.memory = MagicMock()
        return api

    def test_itemizes_rows_with_url_and_date(self):
        api = self._api()
        apps = api._enrich_applications([
            {
                "job_id": "j1",
                "title": "HSE Manager",
                "company": "ADNOC",
                "status": "applied",
                "date_applied": "2026-05-01T10:00:00+00:00",
                "date_updated": "2026-05-01T10:00:00+00:00",
                "apply_url": "https://jobs.example.com/hse-manager",
            }
        ])
        msg = api._build_tracking_message(apps, {"total": 1})
        assert "HSE Manager" in msg
        assert "ADNOC" in msg
        assert "https://jobs.example.com/hse-manager" in msg
        assert "2026-05-01" in msg
        assert "list my applications" not in msg.lower()

    def test_summary_only_routes_to_applications_page(self):
        api = self._api()
        # No detailed rows, but stats say applications exist → be honest, route out.
        msg = api._build_tracking_message([], {"total": 4})
        assert "4 tracked applications" in msg
        assert "Applications" in msg
        assert "no tracked applications" not in msg.lower()

    def test_truly_empty_says_no_applications(self):
        api = self._api()
        msg = api._build_tracking_message([], {"total": 0})
        assert "no tracked applications" in msg.lower()
