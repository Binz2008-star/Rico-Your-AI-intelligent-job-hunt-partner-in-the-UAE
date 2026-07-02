"""Pipeline/application save + count correctness after the #747 trust gate.

Covers:
  a. a source-backed job save increments the user-scoped count once
  b. a duplicate save is idempotent (no double count)
  c. an LLM/recent_context job_id alone never yields a trusted apply URL
  d. a failed save returns a user-safe message (no raw error / stack trace leak)
  e. the count endpoint reflects the actually-persisted user-scoped records

DB and the agent runtime are mocked — no live Neon, no provider calls.
"""
from __future__ import annotations

from unittest.mock import patch

from src.rico_chat_api import RicoChatAPI
from src.services.job_save import resolve_save_decision


# ── Pure helper: trust + identity decision ────────────────────────────────────

def test_recent_context_job_id_alone_no_trusted_url():
    """(c) job_id from chat/LLM context never becomes a trusted apply URL, and is
    never used as the save key."""
    job = {
        "job_id": "llm-abc123",
        "external_url": "https://linkedin.com/jobs/view/55",  # sequential → untrusted anyway
        "title": "Backend Engineer",
        "company": "Acme",
    }
    d = resolve_save_decision(job, origin="recent_context")
    assert d.apply_url is None
    assert d.verified is False
    assert d.save_key != "llm-abc123"
    assert "llm-abc123" not in d.save_key


def test_source_backed_identity_is_preferred():
    """(a/identity) a real source identifier is used as the save key."""
    job = {"job_id": "llm-1", "source_job_id": "JS-999", "title": "X", "company": "Y"}
    assert resolve_save_decision(job, origin="recent_context").save_key == "source_job_id:JS-999"


def test_fallback_identity_is_deterministic():
    """Same title+company → same key (idempotent), independent of ephemeral job_id."""
    a = resolve_save_decision({"job_id": "a", "title": "Eng", "company": "Acme"}, origin="recent_context")
    b = resolve_save_decision({"job_id": "b", "title": "Eng", "company": "Acme"}, origin="recent_context")
    assert a.save_key == b.save_key
    assert a.save_key.startswith("tc:")


def test_trusted_db_job_yields_apply_url():
    """A DB-backed record from a trusted origin keeps its apply URL."""
    job = {
        "persisted_job_id": 42,
        "external_url": "https://careers.acme.ae/job/42",
        "title": "X",
        "company": "Y",
    }
    d = resolve_save_decision(job, origin=None)
    assert d.apply_url == "https://careers.acme.ae/job/42"
    assert d.verified is True
    assert d.save_key == "persisted_job_id:42"


# ── Wiring: ordinal save persists to the counted store ────────────────────────

class _FakeStore:
    """In-memory stand-in for applications_repo (rico_job_recommendations)."""

    def __init__(self) -> None:
        self.rows: dict[tuple, dict] = {}
        self.create_calls = 0

    def create(self, job_id, title, company, location="", url="", status="opened",
               source="manual", user_id=None):
        self.create_calls += 1
        self.rows[(user_id, job_id)] = {  # upsert keyed on (user_id, job_id)
            "title": title, "company": company, "link": url, "status": status,
        }
        return True

    def get_stats(self, user_id=None):
        saved = sum(
            1 for (u, _), r in self.rows.items()
            if u == user_id and r["status"] == "saved"
        )
        return {"total": len([k for k in self.rows if k[0] == user_id]), "saved": saved}


def _api() -> RicoChatAPI:
    return RicoChatAPI(persist=False)


_LINK = {"apply_url": "", "source_url": "", "alt_link": "", "verification_status": "unverified"}


def _run_ordinal_save(api, store, match, *, user_id="u@test", create_side_effect=None):
    create = create_side_effect or store.create
    with (
        patch.object(api, "_recent_search_matches", return_value=[match]),
        patch("src.services.job_link.resolve_job_link", return_value=dict(_LINK)),
        patch("src.repositories.applications_repo.create", side_effect=create),
        patch("src.rico_chat_api.agent_runtime.handle_action", return_value=None),
        patch.object(api, "_append_chat", lambda *a, **k: None),
        patch.object(api, "_finalize", lambda resp, *a, **k: resp),
    ):
        return api._save_job_by_ordinal(user_id, 1, profile=None)


def test_source_backed_save_increments_count_once():
    """(a) + (e): one save of a source-backed job → one persisted saved record."""
    api, store = _api(), _FakeStore()
    match = {"source_job_id": "JS-1", "title": "Backend Engineer", "company": "Acme"}
    res = _run_ordinal_save(api, store, match)
    assert res["type"] == "save_job"
    assert store.create_calls == 1
    assert store.get_stats("u@test")["saved"] == 1
    # No trusted apply link from recent_context → must not claim a verified one.
    assert res["verified_apply_link"] is False
    assert "verified apply link" in res["message"].lower()


def test_duplicate_save_is_idempotent():
    """(b): saving the same job twice upserts on the trusted key → count stays 1."""
    api, store = _api(), _FakeStore()
    match = {"source_job_id": "JS-1", "title": "Backend Engineer", "company": "Acme"}
    _run_ordinal_save(api, store, match)
    _run_ordinal_save(api, store, match)
    assert store.create_calls == 2          # both attempts ran
    assert len(store.rows) == 1             # but only one row exists (upsert)
    assert store.get_stats("u@test")["saved"] == 1


def test_failed_save_returns_user_safe_message():
    """(d): a persistence failure surfaces a safe message — no raw error/stack trace,
    and never a false success."""
    api, store = _api(), _FakeStore()

    def _boom(*a, **k):
        raise RuntimeError("psycopg2.OperationalError: connection refused at 127.0.0.1:5432")

    match = {"source_job_id": "JS-1", "title": "Backend Engineer", "company": "Acme"}
    res = _run_ordinal_save(api, store, match, create_side_effect=_boom)
    assert res["type"] == "save_job_error"
    assert "couldn't save" in res["message"].lower()
    assert "psycopg2" not in res["message"]
    assert "Traceback" not in res["message"]
    assert "OperationalError" not in res["message"]


def test_subscription_limit_message_is_surfaced_safely():
    """(d): a gate HTTPException-style error surfaces its user-facing detail message."""
    api, store = _api(), _FakeStore()

    class _Gate(Exception):
        def __init__(self):
            self.detail = {"message": "You've reached your saved-jobs limit on the free plan."}

    def _gate(*a, **k):
        raise _Gate()

    match = {"source_job_id": "JS-1", "title": "Backend Engineer", "company": "Acme"}
    res = _run_ordinal_save(api, store, match, create_side_effect=_gate)
    assert res["type"] == "save_job_error"
    assert res["message"] == "You've reached your saved-jobs limit on the free plan."


def test_count_endpoint_reflects_persisted_records():
    """(e): get_stats over the same store reflects exactly the persisted saved rows."""
    api, store = _api(), _FakeStore()
    _run_ordinal_save(api, store, {"source_job_id": "JS-1", "title": "Eng A", "company": "Acme"})
    _run_ordinal_save(api, store, {"source_job_id": "JS-2", "title": "Eng B", "company": "Beta"})
    stats = store.get_stats("u@test")
    assert stats["saved"] == 2
    assert stats["total"] == 2
    # A different user sees none of these records.
    assert store.get_stats("other@test")["saved"] == 0
