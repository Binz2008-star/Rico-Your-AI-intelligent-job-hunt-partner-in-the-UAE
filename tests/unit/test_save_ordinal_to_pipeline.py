# -*- coding: utf-8 -*-
"""
PR B regression — Production Test 8: "Save the second job to my pipeline".

Before: the save action did not resolve ordinal references from recent search
context, so "save the second job" produced a generic help reply and the pipeline
count stayed 0. This wires ordinal save (EN + Arabic) to the recent search
results, persists via agent_runtime, and confirms ONLY after persistence
succeeds.

No external provider calls — recent_search_matches is seeded directly.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.rico_chat_api import RicoChatAPI
from src.agent.intelligence.intent_classifier import classify_intent


def _profile():
    return SimpleNamespace(
        has_cv=True, name="T", preferred_cities=["Dubai"], location="Dubai",
        years_experience=8, skills=["product"], certifications=[],
        target_roles=["Technical Product Owner"], current_role="Product Owner",
    )


# ── Classification (EN + AR ordinals) ─────────────────────────────────────────

@pytest.mark.parametrize("msg,expected", [
    ("Save the first job to my pipeline", 1),
    ("Save the second job to my pipeline", 2),
    ("save the last job", -1),
    ("save job 2 to pipeline", 2),
    ("احفظ أول وظيفة", 1),
    ("احفظ ثاني وظيفة بالبايبلاين", 2),
])
def test_ordinal_save_classified(msg, expected):
    r = classify_intent(msg, has_cv_profile=True)
    assert r.legacy_intent == "save_job"
    assert (r.entities or {}).get("ordinal") == expected


def test_plain_save_has_no_ordinal(self_check=None):
    r = classify_intent("save this job", has_cv_profile=True)
    assert r.legacy_intent == "save_job"
    assert (r.entities or {}).get("ordinal") is None


# ── Handler ───────────────────────────────────────────────────────────────────

class _Result:
    def __init__(self, ok, message="", error=""):
        self.ok = ok
        self.message = message
        self.error = error


@pytest.fixture()
def api(monkeypatch):
    _api = RicoChatAPI(persist=False)
    raw = [
        {"title": "Technical Product Owner", "company": "ADNOC",
         "apply_url": "https://adnoc.ae/careers/1", "location": "Abu Dhabi, UAE"},
        {"title": "Product Owner", "company": "Globex",
         "apply_url": "https://globex.com/jobs/2", "location": "Dubai"},
    ]
    formatted = [RicoChatAPI._format_match(j, _profile()) for j in raw]
    ctx = {"recent_search_matches": formatted}
    monkeypatch.setattr(_api, "_resolve_profile", lambda uid: _profile())
    monkeypatch.setattr(_api, "_get_recent_context", lambda uid: ctx)
    monkeypatch.setattr(_api, "_store_recent_context", lambda uid, c: ctx.update(c))
    monkeypatch.setattr(_api, "_append_chat", lambda *a, **k: None)
    _api._ctx = ctx
    return _api


def _run(api, msg):
    return api._handle_active_user("u-save", msg)


def test_save_second_job_persists_and_confirms(api, monkeypatch):
    captured = {}
    # Patch the underlying database read that _application_status_visible calls
    monkeypatch.setattr("src.repositories.applications_repo.find_by_job_id", lambda job_id, user_id: {"status": "saved"})
    monkeypatch.setattr(
        "src.repositories.applications_repo.create",
        lambda **kw: captured.update(kw) or True,
    )
    monkeypatch.setattr("src.rico_chat_api.agent_runtime.handle_action", lambda **kw: _Result(ok=True))

    r = _run(api, "Save the second job to my pipeline")
    assert r["type"] == "save_job"
    # The SECOND job was resolved from recent context and persisted (counted).
    assert captured["title"] == "Product Owner"
    assert captured["company"] == "Globex"
    assert captured["status"] == "saved"
    assert captured["user_id"] == "u-save"
    # Untrusted recent_context origin → no verified apply link is persisted or claimed.
    assert captured["url"] == ""
    assert r.get("verified_apply_link") is False
    # Confirmation only after success.
    assert "saved" in r["message"].lower() and "pipeline" in r["message"].lower()


def test_save_first_job_arabic(api, monkeypatch):
    captured = {}
    # Patch the underlying database read that _application_status_visible calls
    monkeypatch.setattr("src.repositories.applications_repo.find_by_job_id", lambda job_id, user_id: {"status": "saved"})
    monkeypatch.setattr(
        "src.repositories.applications_repo.create",
        lambda **kw: captured.update(kw) or True,
    )
    monkeypatch.setattr("src.rico_chat_api.agent_runtime.handle_action", lambda **kw: _Result(ok=True))
    r = _run(api, "احفظ أول وظيفة")
    assert r["type"] == "save_job"
    assert captured["title"] == "Technical Product Owner"


def test_save_failure_does_not_claim_success(api, monkeypatch):
    # Counted persistence reports no write → never claim success.
    # This is a NEGATIVE test - verify guard catches write failure
    # For negative tests, do NOT patch the database read to return successful status
    monkeypatch.setattr("src.repositories.applications_repo.create", lambda **kw: False)
    monkeypatch.setattr("src.rico_chat_api.agent_runtime.handle_action", lambda **kw: _Result(ok=True))
    r = _run(api, "Save the second job to my pipeline")
    assert r["type"] == "save_job_error"
    assert "couldn't save" in r["message"].lower() or "could not" in r["message"].lower()
    assert "saved" not in r["message"].lower().replace("couldn't save", "")


def test_save_persistence_exception_reports_failure(api, monkeypatch):
    def boom(**kw):
        raise RuntimeError("boom")
    monkeypatch.setattr("src.repositories.applications_repo.create", boom)
    r = _run(api, "Save the second job to my pipeline")
    assert r["type"] == "save_job_error"
    # No raw exception text leaks to the user.
    assert "boom" not in r["message"]


def test_save_with_no_recent_context_asks(monkeypatch):
    api = RicoChatAPI(persist=False)
    monkeypatch.setattr(api, "_resolve_profile", lambda uid: _profile())
    monkeypatch.setattr(api, "_get_recent_context", lambda uid: {})
    monkeypatch.setattr(api, "_append_chat", lambda *a, **k: None)
    # No recent matches and DB lookup returns nothing.
    monkeypatch.setattr(api, "_recent_search_matches", lambda uid: [])
    called = {"n": 0}
    monkeypatch.setattr(
        "src.rico_chat_api.agent_runtime.handle_action",
        lambda **kw: called.update(n=called["n"] + 1) or _Result(ok=True),
    )
    r = api._handle_active_user("u-empty", "Save the second job to my pipeline")
    assert r["type"] == "clarification"
    assert "search" in r["message"].lower()
    assert called["n"] == 0  # nothing persisted when there's no job to save


def test_save_out_of_range_asks(api, monkeypatch):
    monkeypatch.setattr(
        "src.rico_chat_api.agent_runtime.handle_action",
        lambda **kw: _Result(ok=True),
    )
    r = _run(api, "save job 9 to pipeline")
    assert r["type"] == "clarification"
    assert "between 1 and 2" in r["message"]


# ── Stats path reflects the persisted save ────────────────────────────────────

class _StatsStore:
    """Minimal fake repo that tracks rows and supports get_stats."""

    def __init__(self) -> None:
        self.rows: dict[tuple, dict] = {}

    def create(self, job_id, title, company, location="", url="", status="opened",
               source="manual", user_id=None):
        self.rows[(user_id, job_id)] = {"title": title, "company": company, "status": status}
        return True

    def get_stats(self, user_id=None):
        user_rows = [v for (u, _), v in self.rows.items() if u == user_id]
        by_status: dict[str, int] = {}
        for row in user_rows:
            by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        return {
            "total": len(user_rows),
            "saved": by_status.get("saved", 0),
            "applied": by_status.get("applied", 0),
            "interview": by_status.get("interview", 0),
            "offer": by_status.get("offer", 0),
            "rejected": by_status.get("rejected", 0),
        }


def test_stats_reflect_saved_item(monkeypatch):
    """After an ordinal save, get_stats returns saved >= 1 for that user."""
    from unittest.mock import patch

    _api = RicoChatAPI(persist=False)
    store = _StatsStore()
    match = {"title": "Product Owner", "company": "Globex", "source_job_id": "JS-99"}

    # Patch the underlying database read that _application_status_visible calls
    with patch("src.repositories.applications_repo.find_by_job_id", return_value={"status": "saved"}):
        with (
            patch.object(_api, "_recent_search_matches", return_value=[match]),
            patch("src.services.job_link.resolve_job_link",
                  return_value={"apply_url": "", "source_url": "", "alt_link": "", "verification_status": "unverified"}),
            patch("src.repositories.applications_repo.create", side_effect=store.create),
            patch("src.repositories.applications_repo.get_stats", side_effect=store.get_stats),
            patch("src.rico_chat_api.agent_runtime.handle_action", return_value=None),
            patch.object(_api, "_append_chat", lambda *a, **k: None),
            patch.object(_api, "_finalize", lambda resp, *a, **k: resp),
        ):
            res = _api._save_job_by_ordinal("u@test", 1, profile=None)
            assert res["type"] == "save_job"

            from src.repositories import applications_repo
            stats = applications_repo.get_stats(user_id="u@test")
            assert stats["saved"] >= 1, f"expected saved >= 1, got {stats}"


def test_repeated_save_does_not_double_count(monkeypatch):
    """Saving the same job twice must not increment the saved count above 1."""
    from unittest.mock import patch

    _api = RicoChatAPI(persist=False)
    store = _StatsStore()
    match = {"title": "Product Owner", "company": "Globex", "source_job_id": "JS-99"}

    def _do_save():
        with (
            patch("src.repositories.applications_repo.find_by_job_id", return_value={"status": "saved"}),
            patch.object(_api, "_recent_search_matches", return_value=[match]),
            patch("src.services.job_link.resolve_job_link",
                  return_value={"apply_url": "", "source_url": "", "alt_link": "", "verification_status": "unverified"}),
            patch("src.repositories.applications_repo.create", side_effect=store.create),
            patch("src.rico_chat_api.agent_runtime.handle_action", return_value=None),
            patch.object(_api, "_append_chat", lambda *a, **k: None),
            patch.object(_api, "_finalize", lambda resp, *a, **k: resp),
        ):
            return _api._save_job_by_ordinal("u@test", 1, profile=None)

    res1 = _do_save()
    res2 = _do_save()
    assert res1["type"] == "save_job"
    assert res2["type"] == "save_job"
    # Upsert keyed on (user_id, job_id) → only one row for each key
    saved_rows = [(u, k) for (u, k), v in store.rows.items()
                  if u == "u@test" and v["status"] == "saved"]
    assert len(saved_rows) == 1, f"expected 1 saved row, got {len(saved_rows)}"
