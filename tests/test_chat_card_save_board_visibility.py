"""Reproduction + regression for the chat card-Save → /applications board gap.

Defect (pre-fix, current main):
    A card-originated Save ("Save — {title} at {company}", the classifier's
    card-save form) reaches the ``save_job`` handler in rico_chat_api.py, which
    persists ONLY through ``agent_runtime.handle_action(action="save")`` →
    ``job_tools.save_job`` → ``mark_applied`` (the legacy JSON file, with NO
    user_id). It never writes to ``applications_repo`` — the store the
    ``/applications`` board (and its GET endpoint) reads from. So the job never
    appears on the board, and — worst — the handler still reports "Saved —"
    because it gates the message on the legacy runtime result, not on the
    canonical board write.

    By contrast ``_save_job_by_ordinal`` ("save the second job") and the
    Prepare-application flow already write to ``applications_repo`` with a
    read-back confirmation. The card-Save path was the outlier.

The first test in ``TestCardSaveReachesBoard`` FAILS on current main (it asserts
``applications_repo.create`` is invoked for the card save) and passes once the
handler routes through the canonical store. The remaining tests pin the
GET /applications read-back and honest-failure behaviour.

No external providers, no live DB — ``applications_repo`` is backed by an
in-memory fake so the write→read-back round-trip is real but isolated.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.rico_chat_api import RicoChatAPI


def _profile():
    return SimpleNamespace(
        has_cv=True, name="T", preferred_cities=["Dubai"], location="Dubai",
        years_experience=8, skills=["product"], certifications=[],
        target_roles=["Product Owner"], current_role="Product Owner",
    )


class _Runtime:
    """Stand-in for agent_runtime.handle_action — records calls, always 'ok'.

    Isolates the board write: even when the legacy runtime path reports success,
    the board must be populated independently for the save to be truthful.
    """

    def __init__(self):
        self.calls = []

    def handle_action(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(ok=True, message="Saved.", error="")


@pytest.fixture()
def api(monkeypatch):
    _api = RicoChatAPI(persist=False)
    job = {
        "title": "Product Owner",
        "company": "Globex",
        "apply_url": "https://careers.globex.com/jobs/2",
        "source_url": "https://careers.globex.com/jobs/2",
        "location": "Dubai",
    }
    monkeypatch.setattr(_api, "_resolve_profile", lambda uid: _profile())
    monkeypatch.setattr(_api, "_resolve_card_job", lambda uid, t, c: dict(job))
    monkeypatch.setattr(_api, "_append_chat", lambda *a, **k: None)
    # Neutralise the legacy runtime path so the test observes ONLY the canonical
    # board write. A no-op success here is the worst case for the defect: the
    # runtime "succeeds" yet nothing reaches the board unless the fix is present.
    rt = _Runtime()
    monkeypatch.setattr("src.rico_chat_api.agent_runtime", rt)
    _api._runtime_spy = rt
    return _api


class TestCardSaveReachesBoard:
    def test_card_save_writes_to_applications_repo(self, api, monkeypatch):
        """FAILS on main: the card-Save handler must persist to applications_repo
        (status=saved, correct user_id) — not only the legacy runtime path."""
        created = {}
        monkeypatch.setattr(
            "src.repositories.applications_repo.create",
            lambda **kw: created.update(kw) or True,
        )
        # Read-back returns the just-written record so the mutation guard confirms.
        monkeypatch.setattr(
            "src.repositories.applications_repo.find_by_job_id",
            lambda job_id, user_id: {"status": "saved", "job_id": job_id} if created else None,
        )

        r = api._handle_active_user("u-card", "Save — Product Owner at Globex")

        assert r["type"] == "save_job"
        assert created, "card-Save did not write to applications_repo (board store)"
        assert created["status"] == "saved"
        assert created["user_id"] == "u-card"
        assert created["title"] == "Product Owner"
        assert created["company"] == "Globex"
        assert "saved" in r["message"].lower()

    def test_saved_job_appears_in_get_applications_readback(self, api, monkeypatch):
        """After a card Save, GET /applications (get_page) shows the saved row."""
        store = _FakeAppsDB()
        with _patch_repo_db(monkeypatch, store):
            r = api._handle_active_user("u-card", "Save — Product Owner at Globex")
            assert r["type"] == "save_job"

            from src.repositories import applications_repo
            page = applications_repo.get_page("u-card", status="saved")
            assert page["total"] == 1
            row = page["applications"][0]
            assert row["title"] == "Product Owner"
            assert row["status"] == "saved"

    def test_card_save_honest_failure_when_board_write_fails(self, api, monkeypatch):
        """Canonical write fails → never claim the job was saved."""
        monkeypatch.setattr("src.repositories.applications_repo.create", lambda **kw: False)
        monkeypatch.setattr(
            "src.repositories.applications_repo.find_by_job_id",
            lambda job_id, user_id: None,
        )
        r = api._handle_active_user("u-card", "Save — Product Owner at Globex")
        assert "saved —" not in r["message"].lower()
        assert "couldn't save" in r["message"].lower() or "could not" in r["message"].lower()


# ── In-memory fake applications DB (mirrors the RicoDB methods applications_repo
#    calls) so a real write→read-back round-trip runs without a live database. ──

class _FakeAppsDB:
    def __init__(self):
        self.available = True
        self._exact_auth_lookup_enabled = False
        self.rows: dict[tuple, dict] = {}

    def get_user_bundle(self, uid):
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
        by = {}
        for (u, _), v in self.rows.items():
            if u == user_id:
                by[v["status"]] = by.get(v["status"], 0) + 1
        return {"total": sum(by.values()), **by}


def _patch_repo_db(monkeypatch, store):
    """Context manager patching applications_repo._db to the in-memory store and
    disabling the saved-jobs quota (limit behaviour is covered separately)."""
    from contextlib import contextmanager

    @contextmanager
    def _cm():
        monkeypatch.setattr("src.repositories.applications_repo._db", lambda: store)
        monkeypatch.setattr(
            "src.services.subscription_gating.enforce_saved_job_allowed",
            lambda user_id: None,
        )
        yield store

    return _cm()
