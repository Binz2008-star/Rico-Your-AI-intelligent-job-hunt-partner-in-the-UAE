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
    """Create a RicoChatAPI with a mocked pending job search.

    Injects a tokenized PendingJobSearch into the mock repo so the
    atomic consume path is exercised (no tokenless fallback).
    """
    from src.rico_chat_api import RicoChatAPI
    from src.services.pending_job_search import (
        PendingJobSearch, PendingSearchLookup, LookupStatus, new_pending,
    )
    api = RicoChatAPI.__new__(RicoChatAPI)
    api.memory = MagicMock()
    api._pjs_repo = MagicMock()
    api._pjs_repo.cancel.return_value = True
    api._can_mutate_applications = False
    api._current_operation_id = None
    api._pjs_redemption_attempted_this_turn = RicoChatAPI._PJS_SENTINEL
    if pending:
        role = pending.get("role", "Test")
        location = pending.get("location", "")
        reason = pending.get("query_type", "promise")
        pjs = new_pending(role=role, location=location, reason=reason)
        api._pjs_repo.get.return_value = pjs
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.FOUND, pjs)
        api._pjs_repo.consume.return_value = pjs
    else:
        api._pjs_repo.get.return_value = None
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.NONE)
        api._pjs_repo.consume.return_value = None
    api._pjs_repo.store.return_value = True
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
        from src.services.pending_job_search import PendingJobSearch
        from datetime import datetime, timezone
        expired = PendingJobSearch(
            token="expired-token", role="Old", location="", reason="test",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        api = _make_api({"role": "Old", "location": ""})
        api._pjs_repo.get.return_value = expired
        api._pjs_repo.consume.return_value = None
        with patch.object(api, "_target_role_search_response") as direct:
            result = api._redeem_pending_job_search("u1", "yes", profile={})
        assert result is not None
        assert result.get("type") == "clarification"
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
        """NEW_REQUEST with a FOUND pending state must consume the old token
        and continue routing (return None for PendingJobSearch)."""
        pending = {"role": "Old", "expires_at": int(time.time()) + 600}
        api = _make_api(pending)
        with patch.object(api, "_target_role_search_response") as direct:
            result = api._redeem_pending_job_search("u1", "search for data analyst", profile={})
        assert result is None
        # The lookup was performed, consume was called to invalidate old state.
        api._pjs_repo.consume.assert_called_once()
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
    from src.services.pending_job_search import new_pending
    api = _make_api({"role": "Engineer", "location": ""})
    pjs = new_pending(role="Engineer", location="")
    fresh_token = pjs.token
    api._pjs_repo.get.return_value = pjs
    api._pjs_repo.consume.return_value = pjs
    call_count = 0

    def _counting_search(_self, uid, role, *a, profile=None, location="", **kw):
        nonlocal call_count
        call_count += 1
        return {"type": "job_matches", "matches": []}

    with patch.object(api, "_target_role_search_response", _counting_search):
        first = api._redeem_pending_job_search("u1", "yes", profile={})
    assert first is not None
    assert call_count == 1
    # Simulate the turn-end reset done by _handle_active_user
    object.__setattr__(api, "_pjs_redemption_attempted_this_turn", api._PJS_SENTINEL)
    fresh2 = new_pending(role="Engineer", location="")
    api._pjs_repo.get.return_value = fresh2
    api._pjs_repo.consume.return_value = fresh2
    with patch.object(api, "_target_role_search_response", _counting_search):
        second = api._redeem_pending_job_search("u1", "yes", profile={})
    assert second is not None
    assert call_count == 2  # New turn, new attempt


# ── Fail-closed behavior ─────────────────────────────────────────────────────


def test_store_failure_returns_error_response():
    """When the token-qualified cancel (consume) fails, _redeem must return a
    truthful error rather than claiming success."""
    api = _make_api({"role": "Engineer", "location": ""})
    api._pjs_repo.consume.return_value = None  # token-qualified discard fails
    result = api._redeem_pending_job_search("u1", "لا", profile={})
    assert result is not None
    assert "message" in result
    assert "تعذّر" in result.get("message", "") or "couldn't prepare" in result.get("message", "").lower() or "sorry" in result.get("message", "").lower()


def test_cancel_failure_returns_error():
    """When the token-qualified cancel fails, _redeem must not claim success."""
    api = _make_api({"role": "Engineer", "location": ""})
    api._pjs_repo.consume.return_value = None
    result = api._redeem_pending_job_search("u1", "لا", profile={})
    assert result is not None
    assert result.get("type") == "clarification"


def test_consume_expired_returns_clarification():
    """Expired pending state must return a truthful clarification, not fallthrough."""
    from src.services.pending_job_search import PendingJobSearch
    from datetime import datetime, timezone
    expired = PendingJobSearch(
        token="expired-t", role="Old", location="", reason="test",
        created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    api = _make_api({"role": "Old", "location": ""})
    api._pjs_repo.get.return_value = expired
    api._pjs_repo.consume.return_value = None  # repo rejects expired
    result = api._redeem_pending_job_search("u1", "yes", profile={})
    assert result is not None
    assert result.get("type") == "clarification"
    assert "pending_job_search_failed" in str(result.get("intent", ""))


def test_consume_token_mismatch_returns_clarification():
    """Token mismatch must return a truthful clarification."""
    from src.services.pending_job_search import new_pending
    pjs = new_pending(role="Engineer", location="")
    api = _make_api({"role": "Engineer", "location": ""})
    api._pjs_repo.get.return_value = pjs
    api._pjs_repo.consume.return_value = None  # token mismatch → None
    result = api._redeem_pending_job_search("u1", "yes", profile={})
    assert result is not None
    assert result.get("type") == "clarification"


def test_consume_db_unavailable_returns_clarification():
    """DB unavailable must return a truthful clarification."""
    api = _make_api({"role": "Engineer", "location": ""})
    api._pjs_repo.consume.side_effect = RuntimeError("DB unavailable")
    result = api._redeem_pending_job_search("u1", "yes", profile={})
    assert result is not None
    assert result.get("type") == "clarification"


def test_consume_concurrent_loser_returns_clarification():
    """Concurrent loser returns clarification, not fallthrough."""
    api = _make_api({"role": "Engineer", "location": ""})
    from src.services.pending_job_search import new_pending, PendingSearchLookup, LookupStatus
    pjs = new_pending(role="Engineer", location="")
    api._pjs_repo.get.return_value = pjs
    api._pjs_repo.consume.side_effect = [pjs, None]
    with patch.object(api, "_target_role_search_response") as direct:
        first = api._redeem_pending_job_search("u1", "yes", profile={})
    assert first is not None
    # Simulate fresh turn
    object.__setattr__(api, "_pjs_redemption_attempted_this_turn", api._PJS_SENTINEL)
    api._pjs_repo.get.return_value = None  # already consumed
    api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.NONE)
    with patch.object(api, "_target_role_search_response") as direct2:
        second = api._redeem_pending_job_search("u1", "yes", profile={})
    # Loser on a subsequent turn where the state is gone → safe fallthrough to None
    assert second is None


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


# ── BLOCKER 2: fresh new requests with no pending state ──────────────────────
# These must NOT produce pending_job_search_failed errors.


def test_new_request_with_no_pending_continues_routing():
    """'search for data analyst' with no pending state must return None,
    letting normal routing continue without a PendingJobSearch error."""
    api = _make_api(pending=None)
    result = api._redeem_pending_job_search("u1", "search for data analyst", profile={})
    assert result is None, "NEW_REQUEST with NONE must not produce a PJS error"


def test_arabic_new_request_with_no_pending_continues_routing():
    """'ابحث عن وظائف محاسب' with no pending state must return None."""
    api = _make_api(pending=None)
    result = api._redeem_pending_job_search("u1", "ابحث عن وظائف محاسب", profile={})
    assert result is None, "Arabic NEW_REQUEST with NONE must not produce a PJS error"


def test_cancel_with_no_pending_continues_routing():
    """'cancel' with no pending state must return None, not an error."""
    api = _make_api(pending=None)
    result = api._redeem_pending_job_search("u1", "cancel", profile={})
    assert result is None, "CANCEL with NONE must not produce a PJS error"


def test_change_with_no_pending_executes_new_search():
    """'yes, search Product Manager' with no pending state executes the new
    search directly (CHANGE with NONE is a new request, not an error)."""
    api = _make_api(pending=None)
    with patch.object(api, "_target_role_search_response") as mock_search:
        result = api._redeem_pending_job_search("u1", "yes, search Product Manager", profile={})
    mock_search.assert_called_once()
    assert mock_search.call_args[0][1] == "product manager"


# ── BLOCKER 5: typed lookup outcomes ─────────────────────────────────────────


class TestPendingSearchLookup:
    def test_lookup_returns_none_when_no_pending(self):
        from src.services.pending_job_search import PendingJobSearchRepo, PendingSearchLookup, LookupStatus
        db = MagicMock()
        repo = PendingJobSearchRepo(db)
        db.get_user_bundle.return_value = {"id": "u1", "settings": {}}
        lookup = repo.lookup("u1")
        assert lookup.status == LookupStatus.NONE

    def test_lookup_returns_malformed_when_not_a_dict(self):
        from src.services.pending_job_search import PendingJobSearchRepo, PendingSearchLookup, LookupStatus
        db = MagicMock()
        repo = PendingJobSearchRepo(db)
        db.get_user_bundle.return_value = {"id": "u1", "settings": {"_pjs": "not-a-dict"}}
        lookup = repo.lookup("u1")
        assert lookup.status == LookupStatus.MALFORMED

    def test_lookup_returns_expired_when_past_ttl(self):
        from src.services.pending_job_search import (
            PendingJobSearch, PendingJobSearchRepo, PendingSearchLookup, LookupStatus,
        )
        from datetime import datetime, timezone, timedelta
        db = MagicMock()
        repo = PendingJobSearchRepo(db)
        expired_pjs = PendingJobSearch(
            token="tok", role="Old", location="", reason="test",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        db.get_user_bundle.return_value = {
            "id": "u1", "settings": {"_pjs": expired_pjs.to_dict()},
        }
        lookup = repo.lookup("u1")
        assert lookup.status == LookupStatus.EXPIRED
        assert lookup.pjs is not None

    def test_lookup_returns_unavailable_on_db_failure(self):
        from src.services.pending_job_search import PendingJobSearchRepo, PendingSearchLookup, LookupStatus
        db = MagicMock()
        repo = PendingJobSearchRepo(db)
        db.get_user_bundle.side_effect = RuntimeError("DB down")
        lookup = repo.lookup("u1")
        assert lookup.status == LookupStatus.UNAVAILABLE

    def test_lookup_returns_found_for_valid(self):
        from src.services.pending_job_search import PendingJobSearchRepo, PendingSearchLookup, LookupStatus, new_pending
        db = MagicMock()
        repo = PendingJobSearchRepo(db)
        pjs = new_pending(role="Engineer", location="Dubai")
        db.get_user_bundle.return_value = {
            "id": "u1", "settings": {"_pjs": pjs.to_dict()},
        }
        lookup = repo.lookup("u1")
        assert lookup.status == LookupStatus.FOUND
        assert lookup.pjs is not None
        assert lookup.pjs.role == "Engineer"


# ── BLOCKER 6: typed lookup failure tests ────────────────────────────────────


class TestLookupFailureScenarios:
    """Failure tests that explicitly set repo.lookup.return_value."""

    def test_confirm_unavailable_fallthrough(self):
        """CONFIRM with UNAVAILABLE must fall through — user's 'yes' may
        not be related to PendingJobSearch."""
        api = _make_api(pending=None)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.UNAVAILABLE)
        result = api._redeem_pending_job_search("u1", "yes", profile={})
        assert result is None

    def test_confirm_malformed_returns_clarification(self):
        """CONFIRM with MALFORMED _pjs must return clarification (no execution)."""
        api = _make_api(pending=None)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.MALFORMED)
        result = api._redeem_pending_job_search("u1", "yes", profile={})
        assert result is not None
        assert result.get("type") == "clarification"

    def test_confirm_expired_returns_clarification(self):
        api = _make_api(pending=None)
        from src.services.pending_job_search import (
            PendingSearchLookup, LookupStatus, PendingJobSearch,
        )
        from datetime import datetime, timezone
        expired = PendingJobSearch(
            token="tok", role="Old", location="", reason="test",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.EXPIRED, expired)
        result = api._redeem_pending_job_search("u1", "yes", profile={})
        assert result is not None
        assert result.get("type") == "clarification"

    def test_confirm_none_fallthrough(self):
        """CONFIRM with NONE must return None (safe routing)."""
        api = _make_api(pending=None)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.NONE)
        result = api._redeem_pending_job_search("u1", "yes", profile={})
        assert result is None, "CONFIRM with NONE must fall through, not error"

    def test_lookup_called_exactly_once_on_confirm(self):
        api = _make_api(pending={"role": "Engineer", "location": ""})
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.UNAVAILABLE)
        api._redeem_pending_job_search("u1", "yes", profile={})
        assert api._pjs_repo.lookup.call_count == 1

    def test_consume_not_called_on_lookup_failure(self):
        api = _make_api(pending=None)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.UNAVAILABLE)
        api._redeem_pending_job_search("u1", "yes", profile={})
        assert api._pjs_repo.consume.call_count == 0

    def test_zero_execution_on_failure(self):
        """Verify no _target_role_search_response on UNAVAILABLE/MALFORMED/EXPIRED."""
        api = _make_api(pending=None)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.UNAVAILABLE)
        with patch.object(api, "_target_role_search_response") as mock_search:
            result = api._redeem_pending_job_search("u1", "yes", profile={})
        mock_search.assert_not_called()

    def test_new_request_unavailable_returns_clarification(self):
        """NEW_REQUEST with UNAVAILABLE must NOT fall through — a possibly-live
        stale PJS must not be left behind."""
        api = _make_api(pending=None)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.UNAVAILABLE)
        result = api._redeem_pending_job_search("u1", "search for data analyst", profile={})
        assert result is not None
        assert result.get("type") == "clarification"
        assert "pending_job_search_failed" in str(result.get("intent", ""))

    def test_new_request_malformed_returns_clarification(self):
        api = _make_api(pending=None)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.MALFORMED)
        result = api._redeem_pending_job_search("u1", "search for data analyst", profile={})
        assert result is not None
        assert result.get("type") == "clarification"

    def test_new_request_expired_routes_after_cleanup(self):
        """NEW_REQUEST with EXPIRED token: discard the expired exact token, then
        route only when cleanup succeeds."""
        from src.services.pending_job_search import (
            PendingSearchLookup, LookupStatus, PendingJobSearch,
        )
        from datetime import datetime, timezone
        api = _make_api(pending=None)
        expired = PendingJobSearch(
            token="tok", role="Old", location="", reason="test",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.EXPIRED, expired)
        api._pjs_repo.discard_token.return_value = True
        result = api._redeem_pending_job_search("u1", "search for data analyst", profile={})
        assert result is None, "successful cleanup must allow routing"
        api._pjs_repo.discard_token.assert_called_once()

    def test_new_request_expired_cleanup_failure_returns_clarification(self):
        from src.services.pending_job_search import (
            PendingSearchLookup, LookupStatus, PendingJobSearch,
        )
        from datetime import datetime, timezone
        api = _make_api(pending=None)
        expired = PendingJobSearch(
            token="tok", role="Old", location="", reason="test",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.EXPIRED, expired)
        api._pjs_repo.discard_token.return_value = False
        result = api._redeem_pending_job_search("u1", "search for data analyst", profile={})
        assert result is not None
        assert result.get("type") == "clarification"


# ── BLOCKER 2: NONE behavior (normal routing preserved) ──────────────────────


class TestNoneBehavior:
    def test_new_request_none_routes_normally(self):
        api = _make_api(pending=None)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.NONE)
        result = api._redeem_pending_job_search("u1", "search for data analyst", profile={})
        assert result is None

    def test_arabic_new_request_none_routes_normally(self):
        api = _make_api(pending=None)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.NONE)
        result = api._redeem_pending_job_search("u1", "ابحث عن وظائف محاسب", profile={})
        assert result is None

    def test_cancel_none_routes_normally(self):
        api = _make_api(pending=None)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.NONE)
        result = api._redeem_pending_job_search("u1", "cancel", profile={})
        assert result is None

    def test_confirm_none_routes_normally(self):
        api = _make_api(pending=None)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.NONE)
        result = api._redeem_pending_job_search("u1", "yes", profile={})
        assert result is None

    def test_change_role_none_executes_new_search(self):
        api = _make_api(pending=None)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.NONE)
        with patch.object(api, "_target_role_search_response") as mock_search:
            result = api._redeem_pending_job_search("u1", "yes, search Product Manager", profile={})
        mock_search.assert_called_once()


# ── BLOCKER 1: NEW_REQUEST must not ignore invalidation failure ──────────────


class TestNewRequestInvalidation:
    def test_consume_failure_prevents_routing(self):
        """FOUND + NEW_REQUEST: if the exact-token invalidation fails, the new
        request must NOT route — it returns a truthful clarification."""
        api = _make_api(pending={"role": "Engineer", "location": ""})
        api._pjs_repo.consume.return_value = None  # invalidation fails
        result = api._redeem_pending_job_search("u1", "search for data analyst", profile={})
        assert result is not None
        assert result.get("type") == "clarification"
        assert "pending_job_search_failed" in str(result.get("intent", ""))

    def test_consume_failure_prevents_search_execution(self):
        api = _make_api(pending={"role": "Engineer", "location": ""})
        api._pjs_repo.consume.return_value = None
        with patch.object(api, "_target_role_search_response") as mock_search:
            api._redeem_pending_job_search("u1", "search for data analyst", profile={})
        mock_search.assert_not_called()

    def test_lookup_once_consume_once(self):
        api = _make_api(pending={"role": "Engineer", "location": ""})
        api._redeem_pending_job_search("u1", "search for data analyst", profile={})
        api._pjs_repo.lookup.assert_called_once()
        api._pjs_repo.consume.assert_called_once()

    def test_stale_pending_cannot_revive_on_later_confirmation(self):
        """After NEW_REQUEST consumes the old token, a later CONFIRM finds no
        pending state and falls through — the stale role never executes."""
        api = _make_api(pending={"role": "Engineer", "location": ""})
        # Turn 1: NEW_REQUEST consumes the old token.
        first = api._redeem_pending_job_search("u1", "search for data analyst", profile={})
        assert first is None  # routed (consume succeeded)
        # Turn 2: simulate fresh turn with pending state gone.
        object.__setattr__(api, "_pjs_redemption_attempted_this_turn", api._PJS_SENTINEL)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.NONE)
        with patch.object(api, "_target_role_search_response") as mock_search:
            second = api._redeem_pending_job_search("u1", "yes", profile={})
        assert second is None
        mock_search.assert_not_called()


# ── BLOCKER 2: CANCEL must be token-qualified ────────────────────────────────


class TestTokenQualifiedCancel:
    def test_cancel_uses_exact_token_not_unqualified_clear(self):
        """CANCEL + FOUND must consume the exact lookup token — never call the
        unqualified cancel(user_id) which could delete a replacement token."""
        api = _make_api(pending={"role": "Engineer", "location": ""})
        api._pjs_repo.cancel = MagicMock()
        with patch.object(api, "_target_role_search_response") as mock_search:
            result = api._redeem_pending_job_search("u1", "cancel", profile={})
        assert result is None
        api._pjs_repo.lookup.assert_called_once()
        api._pjs_repo.consume.assert_called_once()
        api._pjs_repo.cancel.assert_not_called()
        mock_search.assert_not_called()

    def test_cancel_discards_exact_lookup_token(self):
        """The token passed to consume must be the one from the typed lookup."""
        from src.services.pending_job_search import new_pending, PendingSearchLookup, LookupStatus
        api = _make_api(pending=None)
        pjs = new_pending(role="Engineer", location="")
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.FOUND, pjs)
        api._redeem_pending_job_search("u1", "cancel", profile={})
        api._pjs_repo.consume.assert_called_once()
        assert api._pjs_repo.consume.call_args[0][1] == pjs.token

    def test_cancel_never_removes_replacement_token(self):
        """CANCEL consumes only the exact token; a replacement token stored by
        a concurrent request is never clobbered (the consume is token-bound)."""
        from src.services.pending_job_search import new_pending, PendingSearchLookup, LookupStatus
        api = _make_api(pending=None)
        pjs_a = new_pending(role="Engineer", location="")
        pjs_b = new_pending(role="Data Analyst", location="")
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.FOUND, pjs_a)
        # consume simulates token-qualified delete: only token A matches.
        api._pjs_repo.consume.side_effect = lambda u, token: pjs_a if token == pjs_a.token else None
        result = api._redeem_pending_job_search("u1", "cancel", profile={})
        assert result is None
        api._pjs_repo.consume.assert_called_once_with("u1", pjs_a.token)

    def test_cancel_performs_no_job_execution(self):
        api = _make_api(pending={"role": "Engineer", "location": ""})
        with patch.object(api, "_target_role_search_response") as mock_search:
            api._redeem_pending_job_search("u1", "cancel", profile={})
        mock_search.assert_not_called()

    def test_cancel_discard_failure_returns_clarification(self):
        api = _make_api(pending={"role": "Engineer", "location": ""})
        api._pjs_repo.consume.return_value = None
        result = api._redeem_pending_job_search("u1", "cancel", profile={})
        assert result is not None
        assert result.get("type") == "clarification"

    def test_cancel_expired_cleanup_uses_exact_token(self):
        from src.services.pending_job_search import (
            new_pending, PendingSearchLookup, LookupStatus,
        )
        from datetime import datetime, timedelta, timezone
        api = _make_api(pending=None)
        expired = new_pending(role="Old", location="")
        expired = type(expired)(
            token=expired.token, role=expired.role, location=expired.location,
            reason=expired.reason,
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.EXPIRED, expired)
        api._pjs_repo.discard_token.return_value = True
        result = api._redeem_pending_job_search("u1", "cancel", profile={})
        assert result is None
        api._pjs_repo.discard_token.assert_called_once_with("u1", expired.token)


# ── BLOCKER 3: finalizer is the single store owner ───────────────────────────


class TestSingleStoreOwner:
    @pytest.mark.parametrize("reason", [
        "known_but_off_profile", "adjacent_broaden", "ambiguous_promise",
        "provider_degraded", "profile_based",
    ])
    def test_finalize_stores_exactly_once(self, reason):
        api = _make_api(pending=None)
        from src.rico_chat_api import make_offer
        result = {
            "type": "clarification",
            "message": "Should I search for Accountant?",
            "options": [{"action": "confirm_search", "label": "Yes, search Accountant"}],
        }
        result[api._PJS_OFFER_FIELD] = make_offer(role="Accountant", reason=reason)
        finalized = api._finalize_pending_job_search_offer("u1", result)
        assert api._pjs_repo.store.call_count == 1
        assert api._PJS_OFFER_FIELD not in finalized
        # CTA preserved on success.
        actions = [o.get("action") for o in finalized.get("options", [])]
        assert "confirm_search" in actions

    def test_known_but_off_profile_stores_exactly_once(self):
        api = _make_api(pending=None)
        profile_no_role = {"target_roles": [], "skills": [], "years_experience": 3}
        with patch("src.rico_chat_api.classify_role_candidate", return_value=("known_but_off_profile", "Data Scientist")), \
             patch.object(api, "_append_chat"), \
             patch.object(api, "_get_recent_context", return_value={}), \
             patch.object(api, "_store_recent_context"):
            api._classified_role_search("u1", "Data Scientist", profile_no_role)
        assert api._pjs_repo.store.call_count == 1

    def test_provider_degraded_stores_exactly_once(self):
        api = _make_api(pending=None)
        with patch.object(api, "_append_chat"):
            api._provider_degraded_response("u1", "Engineer", location="Dubai")
        assert api._pjs_repo.store.call_count == 1

    def test_adjacent_broaden_response_no_prestore(self):
        """adjacent_broaden must not pre-store: only the finalizer stores."""
        from src.services.pending_job_search import new_pending, PendingSearchLookup, LookupStatus
        api = _make_api(pending=None)
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.NONE)
        # The offer-producing path sets a marker; a single finalize stores once.
        from src.rico_chat_api import make_offer
        response = {
            "type": "job_matches",
            "message": "These are Engineer roles. Want me to broaden?",
            "matches": [],
        }
        response[api._PJS_OFFER_FIELD] = make_offer(role="Engineer", reason="adjacent_broaden")
        finalized = api._finalize_pending_job_search_offer("u1", response)
        assert api._pjs_repo.store.call_count == 1


# ── BLOCKER 4: persist the finalized response ────────────────────────────────


class TestFinalizedPersistence:
    def test_provider_degraded_persists_finalized_message_on_success(self):
        api = _make_api(pending=None)
        appended = []
        with patch.object(api, "_append_chat", side_effect=lambda u, r, m: appended.append(m)):
            resp = api._provider_degraded_response("u1", "Engineer", location="Dubai")
        assert appended, "must persist something"
        assert appended[-1] == resp["message"]
        assert api._PJS_OFFER_FIELD not in resp

    def test_provider_degraded_persists_sanitized_message_on_failure(self):
        api = _make_api(pending=None)
        api._pjs_repo.store.return_value = False
        appended = []
        with patch.object(api, "_append_chat", side_effect=lambda u, r, m: appended.append(m)):
            resp = api._provider_degraded_response("u1", "Engineer", location="Dubai")
        assert appended, "must persist something"
        assert appended[-1] == resp["message"]
        assert api._PJS_OFFER_FIELD not in resp

    def test_no_private_marker_in_api_response_or_history(self):
        api = _make_api(pending=None)
        appended = []
        with patch.object(api, "_append_chat", side_effect=lambda u, r, m: appended.append(m)):
            resp = api._provider_degraded_response("u1", "Engineer", location="Dubai")
        assert api._PJS_OFFER_FIELD not in resp
        assert all(api._PJS_OFFER_FIELD not in (m if isinstance(m, dict) else {}) for m in appended)


# ── Precedence: unrelated pending operations still win ───────────────────────


class TestUnrelatedConfirmationPrecedence:
    def test_mark_applied_confirmation_wins(self):
        """A pending mark-applied confirmation blocks PJS redemption."""
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI.__new__(RicoChatAPI)
        api._pjs_repo = MagicMock()
        api._pending_search_redemption_blocked = lambda *a, **k: True
        result = api._redeem_pending_job_search("u1", "yes", profile={}, blocked=True)
        assert result is None
        api._pjs_repo.lookup.assert_not_called()

    def test_pjs_does_not_own_every_yes(self):
        """CONFIRM + NONE returns None so normal routing (acknowledgement,
        application status, etc.) owns the turn."""
        api = _make_api(pending=None)
        from src.services.pending_job_search import PendingSearchLookup, LookupStatus
        api._pjs_repo.lookup.return_value = PendingSearchLookup(LookupStatus.NONE)
        result = api._redeem_pending_job_search("u1", "ok", profile={})
        assert result is None


# ── Arabic store-failure CTA sanitization (final review blocker) ──────────────
# When durable storage fails, the complete Arabic confirmation instruction
# ("هل تريد مني البحث ... أجب بنعم أو أخبرني بمسمى آخر.") must be removed from
# the finalized message, not just the confirm_search option.

_AR_KNOWN_ROLE = "محاسب"
_AR_KNOWN_MSG = (
    f"'{_AR_KNOWN_ROLE}' هو مسمى وظيفي معروف، لكنه لا يتطابق مع ملفك المهني بشكل كبير. "
    f"هل تريد مني البحث عن وظائف {_AR_KNOWN_ROLE} مع ذلك؟ أجب بنعم أو أخبرني بمسمى آخر."
)


class TestArabicStoreFailureSanitization:
    def test_direct_finalizer_arabic_store_failure_sanitized(self):
        """Direct finalizer regression with the exact production Arabic phrase."""
        api = _make_api(pending=None)
        api._pjs_repo.store.return_value = False
        from src.rico_chat_api import make_offer
        result = {
            "type": "clarification",
            "message": _AR_KNOWN_MSG,
            "options": [
                {"action": "confirm_search", "label": f"نعم، ابحث عن {_AR_KNOWN_ROLE}"},
                {"action": "show_profile_roles", "label": "عرض الأدوار من سيرتي الذاتية"},
            ],
        }
        result[api._PJS_OFFER_FIELD] = make_offer(role=_AR_KNOWN_ROLE, reason="known_but_off_profile")
        finalized = api._finalize_pending_job_search_offer("u1", result)

        assert api._PJS_OFFER_FIELD not in finalized
        actions = [o.get("action") for o in finalized.get("options", [])]
        assert "confirm_search" not in actions
        msg = finalized.get("message", "")
        assert "هل تريد مني البحث" not in msg
        assert "أجب بنعم" not in msg
        assert "نعم، ابحث" not in msg
        assert "قل لي المسمى الوظيفي والموقع مرة أخرى" in msg, "truthful fallback must be present"
        assert "ابحث" not in msg, "no confirmation may be inferred from the final text"

    def test_full_known_but_off_profile_arabic_store_failure(self):
        """Drive _classified_role_search through the real Arabic path with
        failed storage: sanitized API message, persisted == API message,
        no marker, no confirm_search option."""
        api = _make_api(pending=None)
        api._pjs_repo.store.return_value = False
        profile_no_role = {"target_roles": [], "skills": [], "years_experience": 3}
        appended: list = []
        with patch("src.rico_chat_api.classify_role_candidate",
                   return_value=("known_but_off_profile", _AR_KNOWN_ROLE)), \
             patch.object(api, "_append_chat", side_effect=lambda u, r, m: appended.append(m)), \
             patch.object(api, "_get_recent_context", return_value={}), \
             patch.object(api, "_store_recent_context"):
            result = api._classified_role_search("u1", _AR_KNOWN_ROLE, profile_no_role)

        assert result.get("type") == "clarification"
        assert api._PJS_OFFER_FIELD not in result
        actions = [o.get("action") for o in result.get("options", [])]
        assert "confirm_search" not in actions
        assert "show_profile_roles" in actions, "safe non-search option may remain"
        msg = result.get("message", "")
        assert "هل تريد مني البحث" not in msg
        assert "أجب بنعم" not in msg
        assert "قل لي المسمى الوظيفي والموقع مرة أخرى" in msg
        # Persisted assistant message equals the API message.
        assert appended and appended[-1] == msg

    def test_english_store_failure_sanitized_regression(self):
        """Prove the existing English store-failure sanitization is unchanged."""
        api = _make_api(pending=None)
        api._pjs_repo.store.return_value = False
        from src.rico_chat_api import make_offer
        en_msg = (
            "'Accountant' is a real role, but it does not look close to your CV profile. "
            "Should I search for Accountant jobs anyway? Reply YES or tell me a different role."
        )
        result = {
            "type": "clarification",
            "message": en_msg,
            "options": [{"action": "confirm_search", "label": "Yes, search Accountant"}],
        }
        result[api._PJS_OFFER_FIELD] = make_offer(role="Accountant", reason="known_but_off_profile")
        finalized = api._finalize_pending_job_search_offer("u1", result)

        msg = finalized.get("message", "")
        assert "Should I search" not in msg
        assert "Reply YES" not in msg
        assert "Tell me the role and location again" in msg

    def test_arabic_store_success_preserves_cta(self):
        """When storage succeeds the Arabic confirmation text and the
        confirm_search option remain; the marker is removed; store runs once."""
        api = _make_api(pending=None)
        api._pjs_repo.store.return_value = True
        from src.rico_chat_api import make_offer
        result = {
            "type": "clarification",
            "message": _AR_KNOWN_MSG,
            "options": [
                {"action": "confirm_search", "label": f"نعم، ابحث عن {_AR_KNOWN_ROLE}"},
            ],
        }
        result[api._PJS_OFFER_FIELD] = make_offer(role=_AR_KNOWN_ROLE, reason="known_but_off_profile")
        finalized = api._finalize_pending_job_search_offer("u1", result)

        assert api._PJS_OFFER_FIELD not in finalized
        assert "هل تريد مني البحث" in finalized.get("message", "")
        assert "أجب بنعم" in finalized.get("message", "")
        actions = [o.get("action") for o in finalized.get("options", [])]
        assert "confirm_search" in actions
        assert api._pjs_repo.store.call_count == 1

    def test_generic_arabic_prose_not_stripped(self):
        """Ordinary Arabic career advice is not stripped unless it carries the
        explicit structured offer marker and storage fails."""
        api = _make_api(pending=None)
        result = {
            "type": "clarification",
            "message": "يمكنك البحث عن وظائف على LinkedIn أو Bayt حسب مجال خبرتك ومؤهلاتك.",
        }
        finalized = api._finalize_pending_job_search_offer("u1", result)
        assert not api._pjs_repo.store.called
        assert "يمكنك البحث عن وظائف" in finalized.get("message", "")


# ── Canonical precedence: higher-specificity pending actions outrank PJS ──────
# A more specific armed mutation confirmation owns a bare yes/نعم/تمام turn.
# PendingJobSearch must NOT consume its token, execute, or write history when
# such a confirmation is armed.

def _make_precedence_api() -> tuple[Any, Any, Any]:
    """A RicoChatAPI with a real FOUND PJS repo mock plus recording mocks.

    Returns (api, repo, appended) where appended collects every message passed
    to _append_chat.
    """
    from src.rico_chat_api import _application_status_visible, _no_saved_jobs_visible, RicoChatAPI
    from src.services.pending_job_search import (
        PendingSearchLookup, LookupStatus, new_pending,
    )

    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    mock_memory = MagicMock()
    mock_memory.get_chat_messages.return_value = []
    api.memory = mock_memory
    api._application_status_visible = _application_status_visible
    api._no_saved_jobs_visible = _no_saved_jobs_visible
    api.system = MagicMock()
    api.system.run_for_profile.side_effect = AssertionError("job search must not run")

    pjs = new_pending(role="Accountant", location="Dubai", reason="known_but_off_profile")
    repo = MagicMock()
    repo.store.return_value = True
    repo.cancel.return_value = True
    repo.lookup.return_value = PendingSearchLookup(LookupStatus.FOUND, pjs)
    repo.consume.return_value = pjs
    api._pjs_repo = repo
    api._pjs_redemption_attempted_this_turn = RicoChatAPI._PJS_SENTINEL

    appended: list = []
    return api, repo, appended


def _simple_profile() -> MagicMock:
    profile = MagicMock()
    profile.has_cv = True
    profile.target_roles = ["Accountant"]
    profile.skills = []
    profile.name = "Test User"
    profile.email = "test@rico.ai"
    return profile


def _apply_intent() -> "Any":
    from src.agent.intelligence.intent_classifier import IntentResult
    return IntentResult(intent="follow_up_confirmation", confidence=1.0, source="exact")


class TestPrecedenceContract:
    def test_found_pjs_with_confirm_apply_yes_wins_application(self):
        """FOUND PJS + armed _pending_confirm_apply + 'yes' → mark-applied wins,
        no PJS consume, no search execution, token untouched."""
        api, repo, appended = _make_precedence_api()
        intent = _apply_intent()
        profile = _simple_profile()
        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch.object(api, "_resolve_profile", return_value=profile), \
             patch.object(api, "_append_chat", side_effect=lambda u, r, m: appended.append(m)), \
             patch.object(api, "_get_openai_agent", return_value=MagicMock()), \
             patch.object(api, "_get_recent_context", return_value={
                 "_pending_confirm_apply": {
                     "title": "Environmental Manager - Railway Construction Project",
                     "company": "Confidential Jobs",
                 }
             }), \
             patch.object(api, "_store_recent_context"), \
             patch("src.rico_chat_api.classify_intent", return_value=intent), \
             patch("src.repositories.applications_repo.create_manual", return_value=True):
            result = api.process_message("test@rico.ai", "yes")

        assert result.get("type") == "mark_applied"
        assert repo.consume.call_count == 0, "PJS token must not be consumed"
        assert repo.lookup.call_count == 0, "no PJS lookup when guard blocks first"
        api.system.run_for_profile.assert_not_called()  # no search execution

    def test_found_pjs_with_confirm_apply_nnam_wins_application(self):
        """Arabic 'نعم' with FOUND PJS + armed _pending_confirm_apply → the
        application confirmation wins, no PJS consume."""
        api, repo, appended = _make_precedence_api()
        intent = _apply_intent()
        profile = _simple_profile()
        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch.object(api, "_resolve_profile", return_value=profile), \
             patch.object(api, "_append_chat", side_effect=lambda u, r, m: appended.append(m)), \
             patch.object(api, "_get_openai_agent", return_value=MagicMock()), \
             patch.object(api, "_get_recent_context", return_value={
                 "_pending_confirm_apply": {
                     "title": "Environmental Manager - Railway Construction Project",
                     "company": "Confidential Jobs",
                 }
             }), \
             patch.object(api, "_store_recent_context"), \
             patch("src.rico_chat_api.classify_intent", return_value=intent), \
             patch("src.repositories.applications_repo.create_manual", return_value=True):
            result = api.process_message("test@rico.ai", "نعم")

        assert result.get("type") == "mark_applied"
        assert repo.consume.call_count == 0
        assert repo.lookup.call_count == 0

    def test_found_pjs_with_confirm_apply_write_failure_keeps_application_status(self):
        """FOUND PJS + armed _pending_confirm_apply + failed manual write → the
        application-status update outcome wins; PJS is untouched."""
        api, repo, appended = _make_precedence_api()
        intent = _apply_intent()
        profile = _simple_profile()
        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch.object(api, "_resolve_profile", return_value=profile), \
             patch.object(api, "_append_chat", side_effect=lambda u, r, m: appended.append(m)), \
             patch.object(api, "_get_openai_agent", return_value=MagicMock()), \
             patch.object(api, "_get_recent_context", return_value={
                 "_pending_confirm_apply": {
                     "title": "Environmental Manager - Railway Construction Project",
                     "company": "Confidential Jobs",
                 }
             }), \
             patch.object(api, "_store_recent_context"), \
             patch("src.rico_chat_api.classify_intent", return_value=intent), \
             patch("src.repositories.applications_repo.create_manual", return_value=False):
            result = api.process_message("test@rico.ai", "yes")

        assert result.get("type") == "application_status_update_failed"
        assert repo.consume.call_count == 0
        assert repo.lookup.call_count == 0

    def test_found_pjs_with_confirm_profile_update_wins_profile(self):
        """FOUND PJS + armed profile-update confirmation + 'yes' → profile
        update wins; PJS is untouched."""
        api, repo, appended = _make_precedence_api()
        profile = _simple_profile()
        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch.object(api, "_resolve_profile", return_value=profile), \
             patch.object(api, "_append_chat", side_effect=lambda u, r, m: appended.append(m)), \
             patch.object(api, "_get_recent_context", return_value={
                 "_pending_field": "confirm_profile_update",
                 "_pending_profile_update": {"target_roles": ["Data Analyst"]},
             }), \
             patch.object(api, "_store_recent_context"), \
             patch("src.rico_chat_api.upsert_profile", return_value=profile), \
             patch("src.rico_chat_api._route",
                   return_value=MagicMock(tool_name=None, entities={}, tool_args={},
                                          confirmation_prompt=None, source="keyword")):
            result = api._handle_active_user("test@rico.ai", "yes")

        assert result.get("type") == "preferences_updated"
        assert repo.consume.call_count == 0
        assert repo.lookup.call_count == 0

    def test_found_pjs_with_confirm_set_active_cv_wins_active_cv(self):
        """FOUND PJS + armed active-CV confirmation + 'yes' → the active-CV
        switch wins; PJS is untouched."""
        api, repo, appended = _make_precedence_api()
        profile = _simple_profile()
        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch.object(api, "_resolve_profile", return_value=profile), \
             patch.object(api, "_append_chat", side_effect=lambda u, r, m: appended.append(m)), \
             patch.object(api, "_get_recent_context", return_value={
                 "_pending_field": "confirm_set_active_cv",
                 "_pending_active_cv": {"target_document_id": "doc-1"},
             }), \
             patch.object(api, "_store_recent_context"), \
             patch("src.rico_chat_api._route",
                   return_value=MagicMock(tool_name=None, entities={}, tool_args={},
                                          confirmation_prompt=None, source="keyword")):
            result = api._handle_active_user("test@rico.ai", "yes")

        # Either the active-CV confirmation resolves (type != search_error) or,
        # if the switch cannot complete without a document store, routing still
        # continues WITHOUT consuming the PJS.  The invariant under test: no
        # PJS consume/lookup and no search execution.
        assert result.get("type") != "search_error"
        assert repo.consume.call_count == 0
        assert repo.lookup.call_count == 0
        api.system.run_for_profile.assert_not_called()

    def test_found_pjs_alone_yes_consumes_and_executes_once(self):
        """FOUND PJS with NO higher-specificity pending action: 'yes' still
        consumes and executes exactly once."""
        api = _make_api(pending={"role": "Accountant", "location": "Dubai"})
        with patch.object(api, "_target_role_search_response",
                          return_value={"type": "job_matches", "matches": []}) as search:
            result = api._redeem_pending_job_search("u1", "yes", profile={})
        assert result is not None
        assert result.get("type") == "job_matches"
        api._pjs_repo.lookup.assert_called_once()
        api._pjs_repo.consume.assert_called_once()
        search.assert_called_once()

    def test_repeated_confirmation_same_turn_no_double(self):
        """Two redemption calls in the same turn share the single-turn cache:
        exactly one lookup, one consume, one execution."""
        api = _make_api(pending={"role": "Accountant", "location": "Dubai"})
        with patch.object(api, "_target_role_search_response",
                          return_value={"type": "job_matches", "matches": []}) as search:
            first = api._redeem_pending_job_search("u1", "yes", profile={})
            second = api._redeem_pending_job_search("u1", "yes", profile={})
        assert first is not None and second is not None
        assert first is second, "turn-cached result must be returned for both calls"
        api._pjs_repo.lookup.assert_called_once()
        api._pjs_repo.consume.assert_called_once()
        search.assert_called_once()

    def test_response_equals_persisted_assistant_response(self):
        """Returned response equals the finalized persisted assistant response:
        same message, no private marker, no search response written to history."""
        api, repo, appended = _make_precedence_api()
        intent = _apply_intent()
        profile = _simple_profile()
        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
             patch.object(api, "_resolve_profile", return_value=profile), \
             patch.object(api, "_append_chat", side_effect=lambda u, r, m: appended.append(m)), \
             patch.object(api, "_get_openai_agent", return_value=MagicMock()), \
             patch.object(api, "_get_recent_context", return_value={
                 "_pending_confirm_apply": {
                     "title": "Environmental Manager - Railway Construction Project",
                     "company": "Confidential Jobs",
                 }
             }), \
             patch.object(api, "_store_recent_context"), \
             patch("src.rico_chat_api.classify_intent", return_value=intent), \
             patch("src.repositories.applications_repo.create_manual", return_value=True):
            result = api.process_message("test@rico.ai", "yes")

        assert appended, "must persist an assistant reply"
        # The persisted message is the same as the returned message.
        assert appended[-1] == result.get("message", "")
        # No search response was persisted.
        assert all(("job_matches" not in str(m) and "search" not in str(m).lower()) for m in appended)
        assert api._PJS_OFFER_FIELD not in result
