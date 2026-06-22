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

    def fake_handle(*, user_id, action, job=None, job_key=None, source=None):
        captured.update(action=action, job=job, job_key=job_key)
        return _Result(ok=True)

    monkeypatch.setattr("src.rico_chat_api.agent_runtime.handle_action", fake_handle)

    r = _run(api, "Save the second job to my pipeline")
    assert r["type"] == "save_job"
    assert captured["action"] == "save"
    # The SECOND job was resolved from recent context.
    assert captured["job"]["title"] == "Product Owner"
    assert captured["job"]["company"] == "Globex"
    # Canonical link field used.
    assert captured["job"]["apply_url"] == "https://globex.com/jobs/2"
    # Confirmation only after success.
    assert "saved" in r["message"].lower() and "pipeline" in r["message"].lower()


def test_save_first_job_arabic(api, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "src.rico_chat_api.agent_runtime.handle_action",
        lambda **kw: captured.update(kw) or _Result(ok=True),
    )
    r = _run(api, "احفظ أول وظيفة")
    assert r["type"] == "save_job"
    assert captured["job"]["title"] == "Technical Product Owner"


def test_save_failure_does_not_claim_success(api, monkeypatch):
    monkeypatch.setattr(
        "src.rico_chat_api.agent_runtime.handle_action",
        lambda **kw: _Result(ok=False, error="db down"),
    )
    r = _run(api, "Save the second job to my pipeline")
    assert r["type"] == "save_job_error"
    assert "couldn't save" in r["message"].lower() or "could not" in r["message"].lower()
    assert "saved" not in r["message"].lower().replace("couldn't save", "")


def test_save_persistence_exception_reports_failure(api, monkeypatch):
    def boom(**kw):
        raise RuntimeError("boom")
    monkeypatch.setattr("src.rico_chat_api.agent_runtime.handle_action", boom)
    r = _run(api, "Save the second job to my pipeline")
    assert r["type"] == "save_job_error"


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
