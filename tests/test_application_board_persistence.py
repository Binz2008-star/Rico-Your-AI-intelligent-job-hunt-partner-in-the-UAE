"""Canonical persistence contract for src.services.application_board.

Covers the required regression matrix for chat Save/Prepare board visibility:

  1. Chat Save writes to applications_repo (status=saved).
  2. Saved job appears in GET /applications (get_page read-back).
  3. Chat Prepare writes status=prepared.
  4. Prepared job appears in GET /applications.
  5. Correct authenticated user_id is preserved.
  6. User A's saved job is invisible to User B.
  7. Repeated Save is idempotent (one row, one quota unit).
  8. Save then Prepare transitions the SAME canonical record.
  9. Prepare then Save follows the no-downgrade transition policy.
 10. Quota is enforced for a NEW saved record.
 11. Existing-record update does not consume duplicate quota.
 12. Canonical write failure returns an honest failure.
 13. Canonical read-back failure does not report success.
 14. Secondary user_job_context is untouched here, so its failure can never
     erase a verified canonical save (property holds by construction).
 15. Source/apply URL preserved where the board schema supports it.
 16. EN/AR is a handler concern; the service is language-agnostic and truthful.
 17. No external application-submission is performed.
 18. No production DML / live-account smoke — an in-memory fake DB backs the
     real applications_repo code so the write→read-back round-trip is genuine.

The fake DB mirrors exactly the RicoDB methods applications_repo calls, so the
tests exercise the real repo (quota gate, user provisioning, upsert semantics)
against isolated storage.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.services.application_board import persist_job_action, BoardResult


# ── In-memory fake RicoDB ─────────────────────────────────────────────────────

class FakeAppsDB:
    def __init__(self):
        self.available = True
        self._exact_auth_lookup_enabled = False
        self.rows: dict[tuple, dict] = {}

    def get_user_bundle(self, uid):
        # Distinct db user id per app user_id → real user isolation.
        return {"id": f"uuid-{uid}"}

    def upsert_recommendation(self, user_id, job_key, job_data, status):
        self.rows[(user_id, job_key)] = {
            "job_id": job_key,
            "title": job_data.get("title", ""),
            "company": job_data.get("company", ""),
            "location": job_data.get("location", ""),
            "link": job_data.get("link", ""),
            "status": status,
        }
        return True

    def update_recommendation_status(self, user_id, job_key, status, notes=""):
        row = self.rows.get((user_id, job_key))
        if not row:
            return False
        row["status"] = status
        return True

    def find_recommendation(self, user_id, job_key):
        return self.rows.get((user_id, job_key))

    def count_applications(self, user_id, status=None):
        return len([
            1 for (u, _), v in self.rows.items()
            if u == user_id and (status is None or v["status"] == status)
        ])

    def get_applications_page(self, user_id, status=None, limit=50, offset=0):
        items = [
            v for (u, _), v in self.rows.items()
            if u == user_id and (status is None or v["status"] == status)
        ]
        return items[offset:offset + limit]

    def get_application_stats(self, user_id):
        by: dict[str, int] = {}
        for (u, _), v in self.rows.items():
            if u == user_id:
                by[v["status"]] = by.get(v["status"], 0) + 1
        return {"total": sum(by.values()), **by}


@pytest.fixture()
def db(monkeypatch):
    store = FakeAppsDB()
    monkeypatch.setattr("src.repositories.applications_repo._db", lambda: store)
    # Default: quota allows the save. Individual tests override to test the gate.
    monkeypatch.setattr(
        "src.services.subscription_gating.enforce_saved_job_allowed",
        lambda user_id: None,
    )
    return store


def _job(title="Data Engineer", company="Acme", **extra):
    base = {"title": title, "company": company, "location": "Dubai",
            "apply_url": "https://careers.acme.com/1"}
    base.update(extra)
    return base


KEY = "job-key-acme-de"


# ── 1,3,5,15: canonical write + fields ────────────────────────────────────────

def test_save_writes_saved_status_with_user_and_fields(db):
    res = persist_job_action("u-a", _job(), "saved", save_key=KEY)
    assert res.ok and res.created and res.status == "saved"
    row = db.rows[("uuid-u-a", KEY)]
    assert row["status"] == "saved"
    assert row["title"] == "Data Engineer" and row["company"] == "Acme"
    assert row["link"] == "https://careers.acme.com/1"   # apply/source URL preserved


def test_prepare_writes_prepared_status(db):
    res = persist_job_action("u-a", _job(), "prepared", save_key=KEY)
    assert res.ok and res.status == "prepared"
    assert db.rows[("uuid-u-a", KEY)]["status"] == "prepared"


# ── 2,4: GET /applications read-back ──────────────────────────────────────────

def test_saved_job_visible_via_get_page(db):
    persist_job_action("u-a", _job(), "saved", save_key=KEY)
    from src.repositories import applications_repo
    page = applications_repo.get_page("u-a", status="saved")
    assert page["total"] == 1
    assert page["applications"][0]["status"] == "saved"


def test_prepared_job_visible_via_get_page(db):
    persist_job_action("u-a", _job(), "prepared", save_key=KEY)
    from src.repositories import applications_repo
    page = applications_repo.get_page("u-a", status="prepared")
    assert page["total"] == 1


# ── 6: user isolation ─────────────────────────────────────────────────────────

def test_user_b_cannot_see_user_a_saved_job(db):
    persist_job_action("u-a", _job(), "saved", save_key=KEY)
    from src.repositories import applications_repo
    assert applications_repo.find_by_job_id(KEY, user_id="u-b") is None
    assert applications_repo.get_page("u-b", status="saved")["total"] == 0


# ── 7,11: idempotency + no duplicate quota ────────────────────────────────────

def test_repeated_save_is_idempotent(db, monkeypatch):
    calls = {"n": 0}

    def _count_gate(user_id):
        calls["n"] += 1  # only invoked when a NEW saved row is attempted

    monkeypatch.setattr(
        "src.services.subscription_gating.enforce_saved_job_allowed", _count_gate
    )
    r1 = persist_job_action("u-a", _job(), "saved", save_key=KEY)
    r2 = persist_job_action("u-a", _job(), "saved", save_key=KEY)
    assert r1.ok and r2.ok
    assert r1.created is True and r2.created is False   # second is a no-op
    assert db.count_applications("uuid-u-a", status="saved") == 1
    assert calls["n"] == 1   # quota consulted once, not twice


# ── 8,9: transitions ──────────────────────────────────────────────────────────

def test_save_then_prepare_transitions_same_record(db):
    persist_job_action("u-a", _job(), "saved", save_key=KEY)
    res = persist_job_action("u-a", _job(), "prepared", save_key=KEY)
    assert res.ok and res.status == "prepared"
    # Same key → one row, now prepared (not two rows).
    assert db.count_applications("uuid-u-a") == 1
    assert db.rows[("uuid-u-a", KEY)]["status"] == "prepared"


def test_prepare_then_save_does_not_downgrade(db):
    persist_job_action("u-a", _job(), "prepared", save_key=KEY)
    res = persist_job_action("u-a", _job(), "saved", save_key=KEY)
    # No downgrade: board stays prepared, and the save is still truthfully "ok"
    # because the board holds at least the saved tier.
    assert res.ok
    assert db.rows[("uuid-u-a", KEY)]["status"] == "prepared"


# ── 10: quota enforced for a NEW saved record ─────────────────────────────────

def test_quota_blocks_new_saved_record(db, monkeypatch):
    def _blocked(user_id):
        raise HTTPException(status_code=402, detail={"message": "Saved-jobs limit reached."})

    monkeypatch.setattr(
        "src.services.subscription_gating.enforce_saved_job_allowed", _blocked
    )
    res = persist_job_action("u-a", _job(), "saved", save_key=KEY)
    assert res.ok is False and res.error == "quota_exceeded"
    assert res.quota_message == "Saved-jobs limit reached."
    assert ("uuid-u-a", KEY) not in db.rows   # nothing persisted


# ── 12,13: honest failure ─────────────────────────────────────────────────────

def test_write_failure_reports_honest_failure(db, monkeypatch):
    monkeypatch.setattr(
        "src.repositories.applications_repo.create", lambda **kw: False
    )
    # find_by_job_id still returns None (nothing was written).
    res = persist_job_action("u-a", _job(), "saved", save_key=KEY)
    assert res.ok is False and res.error == "readback_failed"


def test_readback_failure_does_not_report_success(db, monkeypatch):
    # create claims success but the read-back cannot see it → NOT ok.
    monkeypatch.setattr(
        "src.repositories.applications_repo.create", lambda **kw: True
    )
    monkeypatch.setattr(
        "src.repositories.applications_repo.find_by_job_id",
        lambda job_id, user_id: None,
    )
    res = persist_job_action("u-a", _job(), "saved", save_key=KEY)
    assert res.ok is False and res.error == "readback_failed"


def test_persist_exception_is_honest_failure(db, monkeypatch):
    def _boom(**kw):
        raise RuntimeError("db exploded")

    monkeypatch.setattr("src.repositories.applications_repo.create", _boom)
    res = persist_job_action("u-a", _job(), "saved", save_key=KEY)
    assert res.ok is False and res.error == "persist_failed"


# ── input validation / guardrails ─────────────────────────────────────────────

@pytest.mark.parametrize("status", ["applied", "opened_external", "", "SAVED "])
def test_only_saved_and_prepared_are_accepted(db, status):
    res = persist_job_action("u-a", _job(), status, save_key=KEY)
    if status.strip().lower() == "saved":
        assert res.ok  # "SAVED " normalizes to saved
    else:
        assert res.ok is False and res.error == "bad_status"


def test_missing_user_is_rejected(db):
    assert persist_job_action("", _job(), "saved", save_key=KEY).error == "no_user"


def test_missing_save_key_is_rejected(db):
    assert persist_job_action("u-a", _job(), "saved", save_key="").error == "bad_job"


def test_result_is_board_result_type(db):
    assert isinstance(persist_job_action("u-a", _job(), "saved", save_key=KEY), BoardResult)
