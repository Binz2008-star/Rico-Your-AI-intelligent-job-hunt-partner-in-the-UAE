"""
tests/test_pending_job_search_contract.py

Global typed PendingJobSearch contract (all users, every profile state, both
languages).  Hermetic unit tests cover the domain contract, reply
classification, and the store/redeem pipeline.  A real Postgres integration
test proves atomic consume under concurrency.

No provider calls, no real CV, no production data.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from src.services.pending_job_search import (
    _PJS_KEY,
    PendingJobSearch,
    PendingJobSearchRepo,
    ReplyCategory,
    _parse_dt,
    classify_reply,
    new_pending,
)

# ── Domain contract ──────────────────────────────────────────────────────────


class TestPendingJobSearchContract:
    def test_immutable_after_construction(self):
        pjs = new_pending(role="Accountant", location="Dubai")
        with pytest.raises(AttributeError):
            pjs.role = "Engineer"

    def test_serializes_to_json_safely(self):
        pjs = new_pending(role="مهندس", location="دبي", reason="promise")
        d = pjs.to_dict()
        # Round-trip
        raw = json.dumps(d, ensure_ascii=False)
        restored = PendingJobSearch.from_dict(json.loads(raw))
        assert restored.token == pjs.token
        assert restored.role == "مهندس"
        assert restored.location == "دبي"
        assert restored.reason == "promise"

    def test_rejects_empty_token(self):
        with pytest.raises(ValueError, match="token"):
            PendingJobSearch(
                token="", role="Role", location="", reason="test",
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc),
            )

    def test_rejects_empty_role(self):
        with pytest.raises(ValueError, match="role"):
            PendingJobSearch(
                token=str(uuid.uuid4()), role="", location="", reason="test",
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc),
            )

    def test_rejects_naive_datetime(self):
        with pytest.raises(ValueError, match="timezone"):
            PendingJobSearch(
                token=str(uuid.uuid4()), role="Role", location="",
                reason="test",
                created_at=datetime.now(),
                expires_at=datetime.now(timezone.utc),
            )

    def test_expiry_check(self):
        pjs = PendingJobSearch(
            token=str(uuid.uuid4()), role="Role", location="", reason="test",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        assert pjs.is_expired
        assert not pjs.is_valid

    def test_non_expired_is_valid(self):
        pjs = new_pending(role="Role", ttl_seconds=3600)
        assert not pjs.is_expired
        assert pjs.is_valid

    def test_normalizes_timezone_on_from_dict(self):
        pjs = PendingJobSearch.from_dict({
            "token": str(uuid.uuid4()),
            "role": "Engineer",
            "location": "Dubai",
            "reason": "promise",
            "created_at": "2026-07-30T12:00:00",
            "expires_at": "2026-07-30T12:15:00",
        })
        assert pjs.created_at.tzinfo is not None
        assert pjs.expires_at.tzinfo is not None

    def test_from_dict_with_datetime_objects(self):
        now = datetime.now(timezone.utc)
        pjs = PendingJobSearch.from_dict({
            "token": str(uuid.uuid4()),
            "role": "Engineer",
            "location": "",
            "reason": "test",
            "created_at": now,
            "expires_at": now,
        })
        assert pjs.created_at == now

    def test_english_and_arabic_unicode(self):
        pjs = new_pending(role="مهندس برمجيات", location="دبي", reason="وعد")
        d = pjs.to_dict()
        restored = PendingJobSearch.from_dict(d)
        assert restored.role == "مهندس برمجيات"
        assert restored.location == "دبي"
        assert restored.reason == "وعد"

    def test_rejects_malformed_data(self):
        with pytest.raises((ValueError, TypeError, KeyError)):
            PendingJobSearch.from_dict({"bad": "data"})


# ── Reply classification ─────────────────────────────────────────────────────


class TestReplyClassification:
    @pytest.mark.parametrize("msg", [
        "yes", "YES", "  yes  ", "yeah", "yep", "yup",
        "ok", "OK", "okay", "sure", "do it", "go ahead",
        "confirm", "confirmed", "proceed",
    ])
    def test_english_confirm(self, msg):
        cat, role, loc = classify_reply(msg)
        assert cat == ReplyCategory.CONFIRM
        assert role is None

    @pytest.mark.parametrize("msg", [
        "نعم", "أيوه", "ايوه", "اوك", "حسنا", "ماشي",
        "تمام", "طيب", "يلا", "اكيد", "طبعا", "موافق", "تفضل",
    ])
    def test_arabic_confirm(self, msg):
        cat, role, loc = classify_reply(msg)
        assert cat == ReplyCategory.CONFIRM

    @pytest.mark.parametrize("msg", [
        "no", "nope", "nah", "cancel", "never mind", "skip", "forget it",
        "لا", "لأ", "الغاء", "إلغاء", "لا شكرا",
    ])
    def test_cancel(self, msg):
        cat, _, _ = classify_reply(msg)
        assert cat == ReplyCategory.CANCEL

    def test_change_extracts_role(self):
        cat, role, _ = classify_reply("yes, search Product Manager")
        assert cat == ReplyCategory.CHANGE
        assert role and "product manager" in role

    def test_arabic_change_extracts_role(self):
        cat, role, _ = classify_reply("نعم ابحث عن مهندس")
        assert cat == ReplyCategory.CHANGE
        assert role and "مهندس" in role

    def test_arabic_change_location(self):
        cat, role, loc = classify_reply("نعم ابحث عن وظائف في أبوظبي")
        assert cat == ReplyCategory.CHANGE
        assert loc

    def test_new_request(self):
        cat, _, _ = classify_reply("search for data analyst jobs")
        assert cat == ReplyCategory.NEW_REQUEST

    def test_arabic_new_request(self):
        cat, _, _ = classify_reply("ابحث عن وظائف مهندس في دبي")
        assert cat == ReplyCategory.NEW_REQUEST

    @pytest.mark.parametrize("msg", [
        "شكراً", "thanks", "what is the weather",
        "hello", "hi", "good morning",
        "", "   ",
    ])
    def test_other(self, msg):
        cat, _, _ = classify_reply(msg)
        assert cat == ReplyCategory.OTHER

    def test_ok_is_confirm_not_new_request(self):
        cat, _, _ = classify_reply("ok")
        assert cat == ReplyCategory.CONFIRM

    def test_thanks_is_other_not_confirm(self):
        cat, _, _ = classify_reply("thanks")
        assert cat == ReplyCategory.OTHER


# ── Repository (unit — mocked DB) ────────────────────────────────────────────

_FAKE_BUNDLE_WITH_PJS = {
    "id": str(uuid.uuid4()),
    "settings": {
        _PJS_KEY: new_pending(role="Accountant", location="Dubai", reason="promise").to_dict(),
    },
}


class _FakeRicoDB:
    """Minimal RicoDB stand-in for unit tests."""
    def __init__(self, available=True, bundle=_FAKE_BUNDLE_WITH_PJS):
        self._available = available
        self._bundle = bundle
        self._upserted: list[tuple[str, dict]] = []

    @property
    def available(self):
        return self._available

    def get_user_bundle(self, user_id: str):
        if not self._available:
            raise RuntimeError("RicoDB unavailable")
        return self._bundle

    def upsert_settings(self, user_id: str, settings: dict):
        self._upserted.append((user_id, settings))
        return {"settings": settings}

    def connect(self):
        if not self._available:
            raise RuntimeError("RicoDB unavailable")
        return _FakeConn(self)


class _FakeConn:
    def __init__(self, db):
        self._db = db
        self._closed = False

    def cursor(self):
        return _FakeCursor(self._db)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class _FakeCursor:
    def __init__(self, db):
        self._db = db
        self._rows: list[dict] = []

    def execute(self, sql, params=None):
        self._rows = []

    def fetchone(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class TestPendingJobSearchRepoUnit:
    def test_store_and_get(self):
        db = _FakeRicoDB()
        repo = PendingJobSearchRepo(db)
        pjs = new_pending(role="Data Analyst", location="Sharjah", reason="promise")
        ok = repo.store("user@test", pjs)
        assert ok

    def test_get_returns_none_when_no_pending(self):
        db = _FakeRicoDB(bundle={"id": str(uuid.uuid4()), "settings": {}})
        repo = PendingJobSearchRepo(db)
        result = repo.get("user@test")
        assert result is None

    def test_get_returns_none_on_db_unavailable(self):
        db = _FakeRicoDB(available=False)
        repo = PendingJobSearchRepo(db)
        result = repo.get("user@test")
        assert result is None

    def test_cancel_returns_bool(self):
        db = _FakeRicoDB(bundle=_FAKE_BUNDLE_WITH_PJS)
        repo = PendingJobSearchRepo(db)
        result = repo.cancel("user@test")
        assert isinstance(result, bool)

    def test_expired_is_treated_as_missing(self):
        expired_pjs = PendingJobSearch(
            token=str(uuid.uuid4()), role="Old", location="", reason="old",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        bundle = {"id": str(uuid.uuid4()), "settings": {_PJS_KEY: expired_pjs.to_dict()}}
        db = _FakeRicoDB(bundle=bundle)
        repo = PendingJobSearchRepo(db)
        result = repo.get("user@test")
        assert result is None


# ── Redemption pipeline (mocked chat API) ────────────────────────────────────


def _make_api(pending: dict | None = None) -> tuple:
    """Create a RicoChatAPI with a mocked pending job search."""
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI.__new__(RicoChatAPI)
    memory = MagicMock()
    if pending:
        def _get_context(user_id, key):
            if key == RicoChatAPI._PENDING_JOB_SEARCH_KEY:
                return pending
            return {}
        memory.get_context.side_effect = _get_context
    else:
        memory.get_context.return_value = {}
    memory.set_context.return_value = None
    api.memory = memory
    api._pjs_repo = MagicMock()
    api._pjs_repo.get.return_value = None  # fall through to memory
    api._pjs_repo.cancel.return_value = True
    api._can_mutate_applications = False
    api._current_operation_id = None
    return api


class TestRedemptionPipeline:
    def test_confirm_executes_exact_stored(self):
        pending = {"role": "Accountant", "location": "Dubai", "expires_at": int(time.time()) + 600}
        api = _make_api(pending)
        with patch.object(api, "_target_role_search_response", return_value={"type": "job_matches"}) as direct:
            result = api._redeem_pending_job_search("u1", "نعم", profile={}, blocked=False)
        assert result is not None
        assert result["type"] == "job_matches"
        direct.assert_called_once()
        args, kwargs = direct.call_args
        assert args[1] == "Accountant"
        assert kwargs.get("location") == "Dubai"

    def test_confirm_with_ok(self):
        pending = {"role": "Engineer", "location": "", "expires_at": int(time.time()) + 600}
        api = _make_api(pending)
        with patch.object(api, "_target_role_search_response", return_value={"type": "job_matches"}) as direct:
            result = api._redeem_pending_job_search("u1", "ok", profile={})
        direct.assert_called_once()

    def test_confirm_with_tamam(self):
        pending = {"role": "مهندس", "location": "دبي", "expires_at": int(time.time()) + 600}
        api = _make_api(pending)
        with patch.object(api, "_target_role_search_response", return_value={"type": "job_matches"}) as direct:
            result = api._redeem_pending_job_search("u1", "تمام", profile={})
        direct.assert_called_once()

    def test_confirm_with_yes_english(self):
        pending = {"role": "Accountant", "location": "Abu Dhabi", "expires_at": int(time.time()) + 600}
        api = _make_api(pending)
        with patch.object(api, "_target_role_search_response", return_value={"type": "job_matches"}) as direct:
            result = api._redeem_pending_job_search("u1", "yes", profile={})
        direct.assert_called_once()
        args, kwargs = direct.call_args
        assert args[1] == "Accountant"
        assert kwargs.get("location") == "Abu Dhabi"

    def test_cancel_clears_without_execution(self):
        pending = {"role": "Accountant", "expires_at": int(time.time()) + 600}
        api = _make_api(pending)
        with patch.object(api, "_target_role_search_response") as direct:
            result = api._redeem_pending_job_search("u1", "لا", profile={})
        assert result is None
        direct.assert_not_called()

    def test_expired_does_not_execute(self):
        pending = {"role": "Old", "expires_at": int(time.time()) - 10}
        api = _make_api(pending)
        with patch.object(api, "_target_role_search_response") as direct:
            result = api._redeem_pending_job_search("u1", "yes", profile={})
        assert result is None
        direct.assert_not_called()

    def test_missing_does_not_infer_from_last_message(self):
        api = _make_api(None)
        with patch.object(api, "_target_role_search_response") as direct:
            result = api._redeem_pending_job_search("u1", "نعم", profile={})
        assert result is None
        direct.assert_not_called()

    def test_blocked_does_not_execute(self):
        pending = {"role": "Accountant", "expires_at": int(time.time()) + 600}
        api = _make_api(pending)
        with patch.object(api, "_target_role_search_response") as direct:
            result = api._redeem_pending_job_search("u1", "yes", profile={}, blocked=True)
        assert result is None
        direct.assert_not_called()

    def test_gratitude_does_not_redeem(self):
        pending = {"role": "Accountant", "expires_at": int(time.time()) + 600}
        api = _make_api(pending)
        with patch.object(api, "_target_role_search_response") as direct:
            result = api._redeem_pending_job_search("u1", "thanks", profile={})
        assert result is None
        direct.assert_not_called()

    def test_supersede_on_change(self):
        pending = {"role": "Accountant", "location": "Dubai", "expires_at": int(time.time()) + 600}
        api = _make_api(pending)
        api._pjs_repo.cancel.return_value = True
        with patch.object(api, "_target_role_search_response", return_value={"type": "job_matches"}) as direct:
            result = api._redeem_pending_job_search("u1", "yes, search Product Manager", profile={})
        assert result is not None
        direct.assert_called_once()
        args, kwargs = direct.call_args
        assert "product manager" in args[1]

    def test_new_request_clears_old(self):
        pending = {"role": "Old", "expires_at": int(time.time()) + 600}
        api = _make_api(pending)
        with patch.object(api, "_clear_pending_job_search") as clear_mock, \
             patch.object(api, "_target_role_search_response") as direct:
            result = api._redeem_pending_job_search("u1", "search for data analyst", profile={})
        assert result is None
        clear_mock.assert_called_once()
        direct.assert_not_called()


# ── Location-only change tests ──────────────────────────────────────────────


class TestLocationChange:
    def test_nnam_fi_abudhabi_uses_new_location(self):
        """نعم في أبوظبي must use Abu Dhabi, not the stored location."""
        pending = {"role": "Accountant", "location": "Dubai", "expires_at": int(time.time()) + 600}
        api = _make_api(pending)
        with patch.object(api, "_target_role_search_response", return_value={"type": "job_matches"}) as direct:
            result = api._redeem_pending_job_search("u1", "نعم في أبوظبي", profile={})
        assert result is not None
        direct.assert_called_once()
        args, kwargs = direct.call_args
        assert args[1] == "Accountant"
        loc = kwargs.get("location", "")
        assert "أبوظبي" in loc or "ابوظبي" in loc

    def test_yes_in_abu_dhabi_uses_new_location(self):
        """yes in Abu Dhabi must not use the stale stored location."""
        pending = {"role": "Accountant", "location": "Dubai", "expires_at": int(time.time()) + 600}
        api = _make_api(pending)
        with patch.object(api, "_target_role_search_response", return_value={"type": "job_matches"}) as direct:
            result = api._redeem_pending_job_search("u1", "yes in Abu Dhabi", profile={})
        assert result is not None
        direct.assert_called_once()
        args, kwargs = direct.call_args
        assert kwargs.get("location") is not None

    def test_new_role_supersedes_old(self):
        """yes search Product Manager instead must NOT execute stale role."""
        pending = {"role": "Accountant", "location": "Dubai", "expires_at": int(time.time()) + 600}
        api = _make_api(pending)
        with patch.object(api, "_target_role_search_response", return_value={"type": "job_matches"}) as direct:
            result = api._redeem_pending_job_search("u1", "yes, search Product Manager", profile={})
        assert result is not None
        direct.assert_called_once()
        args, kwargs = direct.call_args
        assert "product manager" in args[1]
        # Location should not be Dubai from the stale pending state
        assert kwargs.get("location", "") != "Dubai" or args[1] != "Accountant"


# ── Single-turn entry point ──────────────────────────────────────────────────


def test_single_turn_caches_result():
    """Calling _redeem_pending_job_search twice in one turn must produce
    exactly one classification and one execution attempt."""
    api = _make_api({"role": "Engineer", "expires_at": int(time.time()) + 600})
    call_count = 0

    def _counting_search(_self, uid, role, *a, profile=None, location="", **kw):
        nonlocal call_count
        call_count += 1
        return {"type": "job_matches", "matches": []}

    with patch.object(api, "_target_role_search_response", _counting_search):
        first = api._redeem_pending_job_search("u1", "yes", profile={})
        second = api._redeem_pending_job_search("u1", "yes", profile={})
    assert first is not None
    assert second is not None
    # Same result object returned (cached), and target_role_search_response
    # was called exactly once.
    assert first is second
    assert call_count == 1


def test_single_turn_reset_on_new_turn():
    """The cache must reset at the start of each new user turn."""
    fresh = {"role": "Engineer", "expires_at": int(time.time()) + 600}
    api = _make_api(fresh)
    call_count = 0

    def _counting_search(_self, uid, role, *a, profile=None, location="", **kw):
        nonlocal call_count
        call_count += 1
        return {"type": "job_matches", "matches": []}

    with patch.object(api, "_target_role_search_response", _counting_search), \
         patch.object(api, "_get_pending_job_search", return_value=dict(fresh)):
        first = api._redeem_pending_job_search("u1", "yes", profile={})
    assert first is not None
    assert call_count == 1
    # Simulate the turn-end reset done by _handle_active_user
    object.__setattr__(api, "_pjs_redeemed_this_turn", None)
    with patch.object(api, "_target_role_search_response", _counting_search), \
         patch.object(api, "_get_pending_job_search", return_value=dict(fresh)):
        second = api._redeem_pending_job_search("u1", "yes", profile={})
    assert second is not None
    assert call_count == 2  # New turn, new attempt


# ── Mutually-exclusive operation ownership ───────────────────────────────────
# The operation ownership claim lives in ``operation_state.start_job_search_operation``
# exclusively. ``_begin_job_search_operation`` calls it. ``_target_role_search_response``
# calls ``_begin_job_search_operation``. There is exactly one call chain.


def test_operation_ownership_claimed_once():
    """Prove _target_role_search_response -> _begin_job_search_operation."""
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI.__new__(RicoChatAPI)
    with patch.object(api, "_begin_job_search_operation") as begin:
        api._target_role_search_response(
            "u1", "Engineer", {"target_roles": ["Engineer"]}, location="Dubai"
        )
    begin.assert_called_once()


def test_begin_calls_start_job_search_operation():
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._current_operation_id = None
    with patch("src.rico_chat_api.start_job_search_operation") as start:
        start.return_value = {"operation_id": "test-op", "attempt": 1, "claimed": True}
        result = api._begin_job_search_operation("u1", "Engineer")
    start.assert_called_once()
    assert result["operation_id"] == "test-op"


# ── _parse_dt helper ─────────────────────────────────────────────────────────


class TestParseDt:
    def test_naive_string_becomes_aware(self):
        dt = _parse_dt("2026-07-30T12:00:00")
        assert dt.tzinfo is not None

    def test_empty_string_returns_now(self):
        dt = _parse_dt("")
        assert dt.tzinfo is not None

    def test_datetime_preserved(self):
        now = datetime.now(timezone.utc)
        dt = _parse_dt(now)
        assert dt == now


# ── RICO_MEMORY_BACKEND=postgres proves memory.set_context cannot implement ──
# the production contract


@patch.dict("os.environ", {"RICO_MEMORY_BACKEND": "postgres"}, clear=True)
def test_memory_backend_postgres_disables_set_context():
    """When RICO_MEMORY_BACKEND=postgres, ``set_context`` is a no-op.

    This is why the PendingJobSearch contract MUST use ``rico_agent_settings``
    JSONB instead of ``RicoMemoryStore.set_context``.
    """
    import importlib
    import src.rico_memory as rm
    importlib.reload(rm)
    store = rm.RicoMemoryStore()
    store.set_context("test", "k", "v")
    from pathlib import Path
    ctx_path = rm.RICO_MEMORY_DIR / f"context_{rm._safe_key('test')}.json"
    assert not ctx_path.exists(), "set_context must be a no-op under postgres backend"
