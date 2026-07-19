"""analytics_events foundation (migration 047).

Pins the contracts of the event store:

1. PRIVACY — allowlisted events only; property values limited to booleans,
   bounded ints, and short enum-like tokens: free-form prose, full emails,
   and query strings cannot pass, while token-shaped or digit-only
   identifiers still could — the enforceable guarantee is the reviewed
   allowlist + validator, not an absolute "no PII" claim. Identities (user
   id / guest session id) are stored only as keyed HMACs — raw values never
   reach rows or logs; absent dedicated key ⇒ ALL writes skipped, no
   unkeyed fallback.
2. IDENTITY — every event requires a real actor: user_id for authenticated,
   a bounded guest_session_id for guests; no identity ⇒ fail-closed reject
   before DB, so distinct anonymous users never collapse onto one actor.
3. IDEMPOTENCY — stable dedupe keys (client_event_id first, else
   actor+event+canonical-props+minute bucket) inserted ON CONFLICT DO NOTHING.
4. RESILIENCE — never raises: DB down, table absent (42P01 latches the store
   off per process), and transient errors all degrade to a no-op.
5. RETENTION — purge_expired() implements the 180-day policy and rejects
   unsafe bounds fail-closed.
6. DRIFT — EVENT_ALLOWLIST and migration 047's event_name CHECK move in
   lockstep.
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
    expected = hmac.new(_TEST_KEY.encode(), f"user:{email}".encode(), hashlib.sha256).hexdigest()
    assert expected in row


def test_identity_hash_is_stable_per_identity_and_keyed(monkeypatch):
    a = repo._hmac_identity("user:a@x.com")
    assert repo._hmac_identity("user:a@x.com") == a      # stable
    assert repo._hmac_identity("user:b@x.com") != a      # per-identity
    assert repo._hmac_identity("guest:a@x.com") != a     # domain-separated
    monkeypatch.setenv(repo._HMAC_KEY_ENV, "another-key")
    assert repo._hmac_identity("user:a@x.com") != a      # keyed


def test_user_identity_is_normalized_before_hashing():
    _, _, c1 = _record("session_start", user_id="A@X.com ")
    _, _, c2 = _record("session_start", user_id="a@x.com")
    assert c1.execute.call_args[0][1][3] == c2.execute.call_args[0][1][3]


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
        guest_session_id="public:sid-shape",
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


def test_purge_bounds_rejects_zero():
    """Zero retention_days returns 0 without DB connection."""
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection") as mock_conn:
        removed = repo.purge_expired(0)
    assert removed == 0
    mock_conn.assert_not_called()  # No DB connection attempted


def test_purge_bounds_rejects_negative():
    """Negative retention_days returns 0 without DB connection."""
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection") as mock_conn:
        removed = repo.purge_expired(-100)
    assert removed == 0
    mock_conn.assert_not_called()  # No DB connection attempted


def test_purge_bounds_rejects_extreme():
    """Values >3650 return 0 without DB connection."""
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection") as mock_conn:
        removed = repo.purge_expired(10000)
    assert removed == 0
    mock_conn.assert_not_called()  # No DB connection attempted


def test_purge_bounds_rejects_non_numeric():
    """Non-numeric values return 0 without DB connection."""
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection") as mock_conn:
        removed = repo.purge_expired("invalid")
    assert removed == 0
    mock_conn.assert_not_called()  # No DB connection attempted


def test_purge_bounds_accepts_normal_values():
    """Valid values (1-3650) proceed to DB."""
    conn, cursor = _mock_conn()
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn):
        repo.purge_expired(180)
        (sql, params) = cursor.execute.call_args[0]
        assert params == (180,)  # normal value passes through


def test_count_and_purge_share_the_exact_predicate():
    """DEC-20260719-001: dry-run count and DELETE are built from the SAME
    predicate string, so the two queries cannot drift apart over time."""
    assert repo._PURGE_SQL == "DELETE FROM analytics_events WHERE " + repo._EXPIRED_PREDICATE_SQL
    assert repo._COUNT_EXPIRED_SQL == (
        "SELECT count(*) FROM analytics_events WHERE " + repo._EXPIRED_PREDICATE_SQL
    )


def test_count_expired_counts_without_deleting():
    conn, cursor = _mock_conn()
    cursor.fetchone.return_value = (7,)
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn):
        assert repo.count_expired() == 7
    (sql, params) = cursor.execute.call_args[0]
    assert sql == repo._COUNT_EXPIRED_SQL
    assert params == (repo.RETENTION_DAYS,)
    assert not conn.commit.called  # read-only — nothing to commit


def test_count_expired_bounds_fail_closed():
    """Same 1..3650 bounds as purge_expired; invalid values never touch DB."""
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection") as mock_conn:
        for bad in (0, -5, 10000, "invalid"):
            assert repo.count_expired(bad) == 0
    mock_conn.assert_not_called()


def test_count_expired_never_raises():
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", side_effect=RuntimeError("boom")):
        assert repo.count_expired() == 0


# ── 5. Guest identity correctness ─────────────────────────────────────────────
# Distinct anonymous users must NEVER collapse onto a shared actor: guest
# events require a bounded guest_session_id, stored only as a keyed HMAC.

def test_different_guest_session_ids_do_not_dedupe_together():
    r1, _, c1 = _record("session_start", audience="guest",
                        guest_session_id="public:sid-one",
                        properties={"surface": "command"})
    r2, _, c2 = _record("session_start", audience="guest",
                        guest_session_id="public:sid-two",
                        properties={"surface": "command"})
    assert r1 is True and r2 is True
    row1, row2 = c1.execute.call_args[0][1], c2.execute.call_args[0][1]
    assert row1[3] != row2[3]  # distinct actor hashes
    assert row1[7] != row2[7]  # distinct dedupe keys — no cross-guest collapse


def test_same_guest_session_id_stays_idempotent_for_identical_events():
    r1, _, c1 = _record("session_start", audience="guest",
                        guest_session_id="public:sid-one",
                        properties={"surface": "command"})
    r2, _, c2 = _record("session_start", audience="guest",
                        guest_session_id="public:sid-one",
                        properties={"surface": "command"})
    assert r1 is True and r2 is True
    key1, key2 = c1.execute.call_args[0][1][7], c2.execute.call_args[0][1][7]
    assert key1 == key2  # identical event, same guest, same minute → one row via ON CONFLICT


@pytest.mark.parametrize("bad_gsid", [None, "", "   ", "x" * 129])
def test_guest_event_without_valid_session_id_is_rejected_without_db(bad_gsid):
    conn, cursor = _mock_conn()
    result, _, _ = _record("session_start", conn=conn, cursor=cursor,
                           audience="guest", guest_session_id=bad_gsid,
                           properties={"surface": "command"})
    assert result is False
    assert not cursor.execute.called  # fail-closed before any DB write


def test_user_event_without_identity_is_rejected_without_db():
    """No shared empty actor for the authenticated path either."""
    conn, cursor = _mock_conn()
    result, _, _ = _record("session_start", conn=conn, cursor=cursor, user_id=None)
    assert result is False
    assert not cursor.execute.called


def test_raw_guest_session_id_never_in_rows_or_logs(caplog):
    secret_sid = "public:guest-sid-SECRET-abc123"
    with caplog.at_level(logging.DEBUG, logger="src.repositories.analytics_events_repo"):
        result, _, cursor = _record("session_start", audience="guest",
                                    guest_session_id=secret_sid,
                                    properties={"surface": "command"})
        # rejection path must not leak it either
        conn2, cursor2 = _mock_conn()
        _record("session_start", conn=conn2, cursor=cursor2,
                audience="guest", guest_session_id="")
    assert result is True
    row = cursor.execute.call_args[0][1]
    assert not any(isinstance(v, str) and secret_sid in v for v in row)
    assert not any(secret_sid in r.getMessage() for r in caplog.records)
    # stored actor is the keyed HMAC of the domain-prefixed identity
    expected = hmac.new(_TEST_KEY.encode(), f"guest:{secret_sid}".encode(), hashlib.sha256).hexdigest()
    assert expected in row


# ── 6. Allowlist ↔ DDL drift protection ──────────────────────────────────────

def test_event_allowlist_exactly_matches_migration_check_values():
    """migration 047's event_name CHECK and EVENT_ALLOWLIST must move in
    lockstep — a mismatch on either side silently drops events at insert
    time (CHECK violation is swallowed as a transient error)."""
    import re as _re
    from pathlib import Path

    sql = Path("migrations/047_analytics_events.sql").read_text(encoding="utf-8")
    check_block = _re.search(r"event_name\s+VARCHAR\(64\)\s+NOT NULL\s+CHECK\s*\(\s*event_name\s+IN\s*\((.*?)\)\s*\)", sql, _re.S)
    assert check_block, "event_name CHECK block not found in migration 047"
    ddl_events = set(_re.findall(r"'([a-z0-9_]+)'", check_block.group(1)))
    assert ddl_events == set(repo.EVENT_ALLOWLIST), (
        f"allowlist/DDL drift — only in code: {set(repo.EVENT_ALLOWLIST) - ddl_events}; "
        f"only in migration: {ddl_events - set(repo.EVENT_ALLOWLIST)}"
    )


# ── 7. Malformed-input hardening (post-merge audit gates 1-2) ─────────────────
# The never-raises contract must hold for EVERY caller, not only the emitter
# layer: malformed argument types are rejected fail-closed before any DB
# access, and row construction lives inside the try so residual construction
# errors degrade to the logged skip path.

@pytest.mark.parametrize("bad_props", [["x"], "free text", 42, {"a"}])
def test_non_dict_properties_rejected_without_raising_or_db(bad_props):
    conn, cursor = _mock_conn()
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn):
        assert repo.record_event(
            "job_action", user_id="u@x.com", properties=bad_props,
        ) is False
    assert not cursor.execute.called


@pytest.mark.parametrize("bad_cid", [123, 1.5, b"evt-1", ["evt-1"]])
def test_non_str_client_event_id_rejected_without_raising_or_db(bad_cid):
    conn, cursor = _mock_conn()
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn):
        assert repo.record_event(
            "session_start", user_id="u@x.com", client_event_id=bad_cid,
        ) is False
    assert not cursor.execute.called


@pytest.mark.parametrize("bad_when", ["2026-07-19", 1752900000, 1.5])
def test_non_datetime_occurred_at_rejected_without_raising_or_db(bad_when):
    conn, cursor = _mock_conn()
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn):
        assert repo.record_event(
            "session_start", user_id="u@x.com", occurred_at=bad_when,
        ) is False
    assert not cursor.execute.called


def test_rejection_logs_never_contain_offending_values(caplog):
    with caplog.at_level(logging.DEBUG, logger="src.repositories.analytics_events_repo"), \
         patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=_mock_conn()[0]):
        repo.record_event("job_action", user_id="u@x.com",
                          properties="secret@leak.example")
        repo.record_event("job_action", user_id="u@x.com",
                          client_event_id=987654321)
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "secret@leak.example" not in joined
    assert "987654321" not in joined


def test_construction_failure_degrades_to_false_never_raises():
    """Belt-and-braces pin: even if row construction itself throws, the
    caller sees False, never an exception."""
    conn, cursor = _mock_conn()
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn), \
         patch.object(repo, "_clean_properties", side_effect=RuntimeError("boom")):
        assert repo.record_event("session_start", user_id="u@x.com") is False
    assert not cursor.execute.called


def test_purge_and_count_bounds_reject_bool():
    """bool is an int subclass — True must never be accepted as a 1-day
    retention window (near-total purge)."""
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection") as mock_conn:
        assert repo.purge_expired(True) == 0
        assert repo.purge_expired(False) == 0
        assert repo.count_expired(True) == 0
    mock_conn.assert_not_called()
