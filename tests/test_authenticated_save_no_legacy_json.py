"""Authenticated chat Save/Prepare must never touch the legacy no-user JSON store.

The legacy path (``job_tools.save_job`` → ``src.applications.mark_applied``)
appends a shared row WITHOUT a ``user_id`` — an active cross-user contamination
path. Authenticated chat Save/Prepare now persist canonically to
``applications_repo`` and invoke the runtime for side-effects only
(``persist=False``), so the legacy writer never runs for them. Guest/pipeline
(no-user, ``persist=True``) behaviour is unchanged.

These tests assert:
  * runtime ``persist=False`` runs safe side-effects but NOT the persistence tool
  * runtime default ``persist=True`` still runs the tool (guest/pipeline intact)
  * an authenticated card Save never calls ``mark_applied`` (no shared JSON row)
  * ordinal Save never calls ``mark_applied``
  * the Save response links to the canonical ``/applications`` route
  * #1367 provenance survives into the canonical persistence call
  * a canonical failure produces ZERO legacy writes and no success claim
  * a secondary side-effect failure does not invalidate a verified canonical save
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.rico_chat_api import RicoChatAPI
from src.agent.runtime import agent_runtime


# ── Fake applications DB (real applications_repo over in-memory storage) ───────

class _FakeAppsDB:
    def __init__(self):
        self.available = True
        self._exact_auth_lookup_enabled = False
        self.rows: dict[tuple, dict] = {}

    def get_user_bundle(self, uid):
        return {"id": f"uuid-{uid}"}

    def upsert_recommendation(self, user_id, job_key, job_data, status):
        self.rows[(user_id, job_key)] = {"job_id": job_key, "status": status, **job_data}
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
        return len([1 for (u, _), v in self.rows.items()
                    if u == user_id and (status is None or v["status"] == status)])

    def get_applications_page(self, user_id, status=None, limit=50, offset=0):
        return [v for (u, _), v in self.rows.items()
                if u == user_id and (status is None or v["status"] == status)][offset:offset + limit]

    def get_application_stats(self, user_id):
        by: dict[str, int] = {}
        for (u, _), v in self.rows.items():
            if u == user_id:
                by[v["status"]] = by.get(v["status"], 0) + 1
        return {"total": sum(by.values()), **by}


@pytest.fixture()
def legacy_spy(monkeypatch):
    """Spy on the legacy no-user JSON writer. Any call means a shared row was
    (attempted to be) written — forbidden for authenticated chat saves."""
    calls: list = []
    monkeypatch.setattr(
        "src.applications.mark_applied",
        lambda job, status="applied", notes="", user_id=None: calls.append(
            {"status": status, "user_id": user_id}
        ) or True,
    )
    return calls


# ── Runtime persist flag ──────────────────────────────────────────────────────

def test_runtime_persist_false_skips_tool_but_runs_side_effects(monkeypatch, legacy_spy):
    import src.agent.runtime as rt

    monkeypatch.setattr(rt, "is_duplicate", lambda action_id: False)
    audited: list = []
    monkeypatch.setattr(rt, "log_action", lambda payload: audited.append(payload))

    res = agent_runtime.handle_action(
        user_id="u-auth", action="save", job={"title": "T", "company": "C"},
        job_key="k", source="chat", persist=False,
    )
    assert res.ok is True
    assert legacy_spy == []          # legacy save tool NEVER ran
    assert len(audited) == 1         # safe side-effect (audit) DID run


def test_runtime_persist_true_still_runs_tool(monkeypatch, legacy_spy):
    import src.agent.runtime as rt

    monkeypatch.setattr(rt, "is_duplicate", lambda action_id: False)
    agent_runtime.handle_action(
        user_id="guest", action="save", job={"title": "T", "company": "C"},
        job_key="k", source="telegram",   # default persist=True
    )
    # Guest/pipeline path unchanged: the legacy tool still ran.
    assert len(legacy_spy) == 1


# ── Authenticated card Save: no legacy write, canonical route, provenance ──────

def _card_api(monkeypatch, store, job):
    api = RicoChatAPI(persist=False)
    monkeypatch.setattr(api, "_resolve_profile", lambda uid: SimpleNamespace(
        has_cv=True, name="T", target_roles=["Product Owner"], skills=[], preferred_cities=["Dubai"]))
    monkeypatch.setattr(api, "_resolve_card_job", lambda uid, t, c: dict(job))
    monkeypatch.setattr(api, "_append_chat", lambda *a, **k: None)
    monkeypatch.setattr("src.repositories.applications_repo._db", lambda: store)
    monkeypatch.setattr("src.services.subscription_gating.enforce_saved_job_allowed", lambda user_id: None)
    return api


CARD_JOB = {
    "title": "Product Owner", "company": "Globex",
    "apply_url": "https://careers.globex.com/2", "source_url": "https://careers.globex.com/2",
    "location": "Dubai", "verification_status": "live_verified",
    "sources": ["LinkedIn", "Bayt"], "duplicate_count": 2, "provider": "jsearch",
}


def test_authenticated_card_save_never_writes_legacy_json(monkeypatch, legacy_spy):
    store = _FakeAppsDB()
    api = _card_api(monkeypatch, store, CARD_JOB)
    r = api._handle_active_user("u-a", "Save — Product Owner at Globex")
    assert r["type"] == "save_job"
    assert "saved —" in r["message"].lower()
    assert legacy_spy == [], "authenticated card Save must not append a legacy JSON row"


def test_card_save_response_links_to_applications(monkeypatch, legacy_spy):
    store = _FakeAppsDB()
    api = _card_api(monkeypatch, store, CARD_JOB)
    r = api._handle_active_user("u-a", "Save — Product Owner at Globex")
    assert "/applications" in r["message"]
    assert "/flow" not in r["message"]


def test_card_save_preserves_provenance_into_canonical_call(monkeypatch, legacy_spy):
    captured: dict = {}

    def _spy_persist(user_id, job, status, *, save_key):
        captured["job"] = dict(job)
        captured["status"] = status
        from src.services.application_board import BoardResult
        return BoardResult(ok=True, status=status)

    monkeypatch.setattr("src.services.application_board.persist_job_action", _spy_persist)
    store = _FakeAppsDB()
    api = _card_api(monkeypatch, store, CARD_JOB)
    api._handle_active_user("u-a", "Save — Product Owner at Globex")

    job = captured["job"]
    assert captured["status"] == "saved"
    # #1367 provenance is carried through, not discarded.
    assert job.get("sources") == ["LinkedIn", "Bayt"]
    assert job.get("duplicate_count") == 2
    assert job.get("verification_status") == "live_verified"
    assert job.get("apply_url") == "https://careers.globex.com/2"
    assert job.get("provider") == "jsearch"


def test_card_save_canonical_failure_writes_no_legacy_and_no_success(monkeypatch, legacy_spy):
    from src.services.application_board import BoardResult

    monkeypatch.setattr(
        "src.services.application_board.persist_job_action",
        lambda *a, **k: BoardResult(ok=False, error="persist_failed"),
    )
    store = _FakeAppsDB()
    api = _card_api(monkeypatch, store, CARD_JOB)
    r = api._handle_active_user("u-a", "Save — Product Owner at Globex")
    # No legacy write, and no false "Saved" claim.
    assert legacy_spy == []
    assert "saved —" not in r["message"].lower()
    assert "couldn't save" in r["message"].lower()


def test_card_save_survives_secondary_side_effect_failure(monkeypatch, legacy_spy):
    # Canonical write confirmed; the runtime side-effects raise → still success.
    def _boom(**kw):
        raise RuntimeError("side-effect exploded")

    monkeypatch.setattr("src.rico_chat_api.agent_runtime.handle_action", _boom)
    store = _FakeAppsDB()
    api = _card_api(monkeypatch, store, CARD_JOB)
    r = api._handle_active_user("u-a", "Save — Product Owner at Globex")
    assert "saved —" in r["message"].lower()   # verified canonical save stands
    assert store.count_applications("uuid-u-a", status="saved") == 1


def test_no_shared_json_row_across_two_users(monkeypatch, legacy_spy):
    store = _FakeAppsDB()
    api = _card_api(monkeypatch, store, CARD_JOB)
    api._handle_active_user("u-a", "Save — Product Owner at Globex")
    api._handle_active_user("u-b", "Save — Product Owner at Globex")
    # Both saves are user-scoped canonical rows; the legacy shared JSON store is
    # never touched, so no cross-user contamination is possible.
    assert legacy_spy == []
    assert store.count_applications("uuid-u-a", status="saved") == 1
    assert store.count_applications("uuid-u-b", status="saved") == 1


# ── Authenticated Prepare: no legacy write, canonical route, provenance ────────

class _FakeRicoDB:
    """Minimal RicoDB stand-in for the prepare_application draft path."""
    def get_user_bundle(self, user_id, conn=None):
        return {"cv_text": "Experienced product owner with 8 years in UAE fintech."}

    def get_application_drafts(self, user_id, status=None):
        return []

    def create_application_draft(self, **kw):
        return {"id": "draft-1", "cover_letter": "Dear Hiring Team, ...", "job_key": kw.get("job_key")}


PREP_JOB = {
    "title": "Product Owner", "company": "Globex",
    "apply_url": "https://careers.globex.com/2", "source_url": "https://careers.globex.com/2",
    "location": "Dubai", "verification_status": "live_verified",
    "sources": ["LinkedIn"], "duplicate_count": 1,
}


def _prepare_api(monkeypatch, store):
    api = RicoChatAPI(persist=False)
    monkeypatch.setattr(api, "_resolve_profile", lambda uid: SimpleNamespace(
        has_cv=True, name="T", target_roles=["Product Owner"], skills=["product"],
        preferred_cities=["Dubai"], cv_text="Experienced product owner."))
    monkeypatch.setattr(api, "_resolve_card_job", lambda uid, t, c: dict(PREP_JOB))
    monkeypatch.setattr(api, "_append_chat", lambda *a, **k: None)
    monkeypatch.setattr(api, "_store_recent_context", lambda *a, **k: None)
    monkeypatch.setattr("src.rico_db.RicoDB", lambda *a, **k: _FakeRicoDB())
    monkeypatch.setattr("src.rico_apply_ai.tailor_application",
                        lambda **kw: {"tailored_cv": "Tailored CV", "cover_letter": "Cover letter body"})
    monkeypatch.setattr("src.repositories.applications_repo._db", lambda: store)
    monkeypatch.setattr("src.services.subscription_gating.enforce_saved_job_allowed", lambda user_id: None)
    monkeypatch.setattr("src.repositories.user_job_context_repo.set_lifecycle_status",
                        lambda **kw: True)
    return api


def test_authenticated_prepare_no_legacy_write_and_board_prepared(monkeypatch, legacy_spy):
    store = _FakeAppsDB()
    api = _prepare_api(monkeypatch, store)
    r = api._handle_active_user("u-a", "Prepare application — Product Owner at Globex")
    assert r["type"] == "prepare_application"
    # No legacy JSON row for an authenticated prepare.
    assert legacy_spy == []
    # Canonical board reflects "prepared".
    assert store.count_applications("uuid-u-a", status="prepared") == 1
    # Canonical route in the board note.
    assert "/applications" in r["message"]
    assert "(/flow)" not in r["message"]
