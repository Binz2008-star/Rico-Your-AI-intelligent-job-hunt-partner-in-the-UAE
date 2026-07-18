"""analytics_events foundation (migration 047).

Pins the four contracts of the event store:

1. PRIVACY — structurally no PII: only allowlisted events; properties limited
   to booleans, bounded ints, and enum-like tokens (free text, emails, and
   query strings cannot pass); the actor is a keyed HMAC (raw user id never
   reaches a row); absent dedicated key ⇒ ALL writes skipped, no unkeyed
   fallback.
2. IDEMPOTENCY — stable dedupe keys (client_event_id first, else
   actor+event+canonical-props+minute bucket) inserted ON CONFLICT DO NOTHING.
3. RESILIENCE — never raises: DB down, table absent (42P01 latches the store
   off per process), and transient errors all degrade to a no-op.
4. RETENTION — purge_expired() implements the 180-day policy.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.repositories import analytics_events_repo as repo

_TEST_KEY = "test-analytics-hmac-key-not-a-real-secret"
_WHEN = datetime(2026, 7, 19, 10, 30, 45, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    repo._reset_state_for_tests()
    monkeypatch.setenv(repo._HMAC_KEY_ENV, _TEST_KEY)
    yield
    repo._reset_state_for_tests()


def _mock_conn(rowcount: int = 1):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.rowcount = rowcount
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn, cursor


def _record(event="job_action", conn=None, cursor=None, **kwargs):
    if conn is None:
        conn, cursor = _mock_conn()
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn):
        result = repo.record_event(event, occurred_at=_WHEN, **kwargs)
    return result, conn, cursor


# ── 1. Privacy ────────────────────────────────────────────────────────────────

def test_unknown_event_is_rejected_without_touching_db():
    conn, cursor = _mock_conn()
    result, _, _ = _record("totally_made_up_event", conn=conn, cursor=cursor)
    assert result is False
    assert not cursor.execute.called


def test_unknown_and_invalid_properties_are_stripped():
    result, _, cursor = _record(
        "job_action",
        user_id="user@x.com",
        properties={
            "action": "save",                      # valid token
            "rank": 3,                             # valid int
            "query": "HSE Manager Dubai",          # unknown key → stripped
            "note": "call me at a@b.com",          # unknown key → stripped
            "surface": "Has Spaces And Caps",      # known key, invalid value → dropped
        },
    )
    assert result is True
    (_sql, row) = cursor.execute.call_args[0]
    stored_props = json.loads(row[-1])
    assert stored_props == {"action": "save", "rank": 3}


def test_free_text_and_pii_shapes_cannot_pass_the_token_validator():
    for bad in ("a@b.com", "+9715012345", "HSE Manager Dubai", "x" * 65, "", "عربي"):
        assert not repo._v_token(bad), bad
    for good in ("command", "jsearch", "apply_click", "en", "v1.2:beta"):
        assert repo._v_token(good), good


def test_raw_user_id_never_reaches_the_row():
    email = "person@example.com"
    result, _, cursor = _record("session_start", user_id=email, properties={"surface": "command"})
    assert result is True
    (_sql, row) = cursor.execute.call_args[0]
    assert not any(isinstance(v, str) and email in v for v in row)
    expected = hmac.new(_TEST_KEY.encode(), email.encode(), hashlib.sha256).hexdigest()
    assert expected in row


def test_actor_hash_differs_across_users_and_keys(monkeypatch):
    a = repo._actor_hash("a@x.com")
    assert repo._actor_hash("a@x.com") == a          # stable
    assert repo._actor_hash("A@X.com ") == a         # normalized
    assert repo._actor_hash("b@x.com") != a          # per-user
    assert repo._actor_hash(None) == ""              # anonymous allowed
    monkeypatch.setenv(repo._HMAC_KEY_ENV, "another-key")
    assert repo._actor_hash("a@x.com") != a          # keyed


def test_missing_key_skips_all_writes_failclosed(monkeypatch, caplog):
    monkeypatch.delenv(repo._HMAC_KEY_ENV, raising=False)
    conn, cursor = _mock_conn()
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn), \
         caplog.at_level(logging.WARNING, logger="src.repositories.analytics_events_repo"):
        assert repo.record_event("session_start", user_id="u@x.com") is False
        assert repo.record_event("session_start", user_id="u@x.com") is False
    assert not cursor.execute.called
    warnings = [r for r in caplog.records if "RICO_ANALYTICS_HMAC_KEY" in r.getMessage()]
    assert len(warnings) == 1  # once per process
    assert not any("u@x.com" in r.getMessage() for r in caplog.records)


# ── 2. Idempotency ────────────────────────────────────────────────────────────

def test_client_event_id_gives_stable_dedupe_key():
    k1 = repo._dedupe_key("actor", "job_action", {"rank": 1}, "evt-123", _WHEN)
    k2 = repo._dedupe_key("actor", "job_action", {"rank": 99}, "evt-123", _WHEN)
    assert k1 == k2  # client id wins over property differences
    assert repo._dedupe_key("actor", "job_action", {}, "evt-124", _WHEN) != k1


def test_auto_dedupe_key_is_canonical_and_minute_bucketed():
    a = repo._dedupe_key("actor", "job_action", {"rank": 1, "boosted": True}, None, _WHEN)
    b = repo._dedupe_key("actor", "job_action", {"boosted": True, "rank": 1}, None,
                         _WHEN.replace(second=1, microsecond=7))
    assert a == b  # property order and sub-minute timing don't matter
    assert repo._dedupe_key("actor", "job_action", {"rank": 2}, None, _WHEN) != a


def test_conflict_returns_false_without_error():
    conn, cursor = _mock_conn(rowcount=0)  # ON CONFLICT DO NOTHING path
    result, _, _ = _record("session_start", conn=conn, cursor=cursor, user_id="u@x.com")
    assert result is False
    assert conn.commit.called


def test_insert_uses_on_conflict_do_nothing():
    result, _, cursor = _record("session_start", user_id="u@x.com")
    assert result is True
    (sql, _row) = cursor.execute.call_args[0]
    assert "ON CONFLICT (dedupe_key) DO NOTHING" in sql


# ── 3. Resilience ─────────────────────────────────────────────────────────────

def test_noop_when_db_unavailable():
    with patch.object(repo, "is_db_available", return_value=False), \
         patch.object(repo, "get_db_connection") as get_conn:
        assert repo.record_event("session_start", user_id="u@x.com") is False
    assert not get_conn.called


def test_missing_table_latches_store_off_for_process():
    conn, cursor = _mock_conn()
    exc = Exception('relation "analytics_events" does not exist')
    exc.pgcode = "42P01"
    cursor.execute.side_effect = exc
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn) as get_conn:
        assert repo.record_event("session_start", user_id="u@x.com", occurred_at=_WHEN) is False
        assert repo.record_event("session_start", user_id="u@x.com", occurred_at=_WHEN) is False
    assert get_conn.call_count == 1  # second call short-circuited


def test_transient_error_swallowed_and_does_not_latch():
    conn, cursor = _mock_conn()
    cursor.execute.side_effect = Exception("connection reset")
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn) as get_conn:
        assert repo.record_event("session_start", user_id="u@x.com", occurred_at=_WHEN) is False
        assert repo.record_event("session_start", user_id="u@x.com", occurred_at=_WHEN) is False
    assert get_conn.call_count == 2


def test_row_shape_and_schema_version():
    result, _, cursor = _record(
        "search_performed",
        user_id="u@x.com",
        audience="guest",
        surface="command",
        language="ar",
        properties={"provider": "jsearch", "results_count": 7, "fresh": True},
    )
    assert result is True
    (_sql, row) = cursor.execute.call_args[0]
    when, version, name, actor, audience, surface, language, dedupe, props = row
    assert when == _WHEN
    assert version == repo.SCHEMA_VERSION == 1
    assert name == "search_performed"
    assert len(actor) == 64 and len(dedupe) == 64
    assert audience == "guest" and surface == "command" and language == "ar"
    assert json.loads(props) == {"provider": "jsearch", "results_count": 7, "fresh": True}


# ── 4. Retention ──────────────────────────────────────────────────────────────

def test_purge_expired_deletes_beyond_retention_window():
    conn, cursor = _mock_conn()
    cursor.rowcount = 42
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn):
        removed = repo.purge_expired()
    assert removed == 42
    (sql, params) = cursor.execute.call_args[0]
    assert "DELETE FROM analytics_events" in sql
    assert "INTERVAL '1 day'" in sql
    assert params == (repo.RETENTION_DAYS,)
    assert repo.RETENTION_DAYS == 180
    assert conn.commit.called


def test_purge_never_raises():
    conn, cursor = _mock_conn()
    cursor.execute.side_effect = Exception("boom")
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn):
        assert repo.purge_expired() == 0


def test_purge_bounds_clamps_zero_to_one():
    conn, cursor = _mock_conn(rowcount=0)  # No rows deleted in this test
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn):
        removed = repo.purge_expired(0)
    assert removed == 0
    (sql, params) = cursor.execute.call_args[0]
    assert params == (1,)  # clamped to 1


def test_purge_bounds_clamps_negative_to_one():
    conn, cursor = _mock_conn(rowcount=0)  # No rows deleted in this test
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn):
        removed = repo.purge_expired(-100)
    assert removed == 0
    (sql, params) = cursor.execute.call_args[0]
    assert params == (1,)  # clamped to 1


def test_purge_bounds_clamps_extreme_to_max():
    conn, cursor = _mock_conn(rowcount=0)  # No rows deleted in this test
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn):
        removed = repo.purge_expired(10000)
    assert removed == 0
    (sql, params) = cursor.execute.call_args[0]
    assert params == (3650,)  # clamped to 10 years


def test_purge_bounds_accepts_normal_values():
    conn, cursor = _mock_conn()
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn):
        repo.purge_expired(180)
        (sql, params) = cursor.execute.call_args[0]
        assert params == (180,)  # normal value passes through


def test_guest_dedupe_collision_is_accepted():
    """Guest events share actor_hash='', so identical events in same minute collapse.

    This is a documented best-effort limitation for anonymous sessions.
    Authenticated users have per-user hashes and full dedupe.
    """
    # Two different guest users, same event, same minute → same dedupe key
    key1 = repo._dedupe_key("", "session_start", {"surface": "command"}, None, _WHEN)
    key2 = repo._dedupe_key("", "session_start", {"surface": "command"}, None, _WHEN)
    assert key1 == key2  # collision expected and accepted

    # Authenticated users have distinct hashes
    key3 = repo._dedupe_key("user1@example.com", "session_start", {"surface": "command"}, None, _WHEN)
    key4 = repo._dedupe_key("user2@example.com", "session_start", {"surface": "command"}, None, _WHEN)
    assert key3 != key4  # no collision for authenticated users
