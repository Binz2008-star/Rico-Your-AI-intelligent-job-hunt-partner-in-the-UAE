"""
Career Memory Engine M1 — MemoryWriter contract tests (ADR-001, owner gates).

Covers the owner-required M1 gates:
  - feature flag default OFF (kill switch semantics)
  - idempotency (dedup counts as success, never a second insert error)
  - per-user isolation (distinct account keys; public sessions never resolve
    to an account key)
  - privacy exclusion filter (secret-looking keys dropped at any depth)
  - shadow-write failures are swallowed and counted, never raised
  - zero behavior change: agent_runtime.handle_action result is untouched
    even when the writer explodes

All DB access is mocked — no live database (workspace testing rules).
"""

from unittest.mock import MagicMock, patch

import pytest

from src.services import memory_writer as mw


@pytest.fixture(autouse=True)
def _reset_counters():
    mw._reset_stats()
    yield
    mw._reset_stats()


def _mock_conn(rowcount: int = 1, fetch_row=("11111111-2222-3333-4444-555555555555",)):
    conn = MagicMock()
    cur = MagicMock()
    cur.rowcount = rowcount
    cur.fetchone.return_value = fetch_row
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    return conn, cur


def _record(user_id="u@test.com", **overrides):
    kwargs = dict(
        idempotency_key="k1",
        actor="agent:test",
        source="verified_event",
        payload={"action": "save"},
    )
    kwargs.update(overrides)
    return mw.record_event(user_id, "action", **kwargs)


# ── Feature flag / kill switch ────────────────────────────────────────────────

class TestFlagDefaultOff:
    def test_disabled_by_default_no_db_touched(self, monkeypatch):
        monkeypatch.delenv("RICO_MEMORY_ENGINE_ENABLED", raising=False)
        with patch("src.db.get_db_connection") as get_conn:
            assert _record() is False
        get_conn.assert_not_called()
        assert mw.get_write_stats()["skipped_disabled"] == 1
        assert mw.get_write_stats()["written"] == 0

    def test_kill_switch_any_non_true_value(self, monkeypatch):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "false")
        assert mw.is_memory_engine_enabled() is False
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "1")
        assert mw.is_memory_engine_enabled() is False
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        assert mw.is_memory_engine_enabled() is True


# ── Writes, idempotency, isolation ───────────────────────────────────────────

class TestShadowWrites:
    def test_enabled_write_uses_canonical_account_key(self, monkeypatch):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        conn, cur = _mock_conn(rowcount=1)
        with patch("src.db.get_db_connection", return_value=conn):
            assert _record("user@test.com") is True
        insert_params = cur.execute.call_args_list[-1][0][1]
        assert insert_params[0] == "acct:11111111-2222-3333-4444-555555555555"
        assert mw.get_write_stats()["written"] == 1

    def test_dedup_counts_as_success(self, monkeypatch):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        conn, _ = _mock_conn(rowcount=0)  # ON CONFLICT DO NOTHING hit
        with patch("src.db.get_db_connection", return_value=conn):
            assert _record() is True
        stats = mw.get_write_stats()
        assert stats["deduped"] == 1
        assert stats["written"] == 0

    def test_public_session_keyed_separately_without_db_lookup(self, monkeypatch):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        conn, cur = _mock_conn(rowcount=1)
        with patch("src.db.get_db_connection", return_value=conn):
            assert _record("public:web-abc123") is True
        insert_params = cur.execute.call_args_list[-1][0][1]
        assert insert_params[0] == "session:public:web-abc123"
        # only the INSERT ran — no identity SELECT for public sessions
        assert cur.execute.call_count == 1

    def test_two_users_get_distinct_keys(self, monkeypatch):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        keys = []
        for row in (("uuid-user-A",), ("uuid-user-B",)):
            conn, cur = _mock_conn(rowcount=1, fetch_row=row)
            with patch("src.db.get_db_connection", return_value=conn):
                assert _record(f"{row[0]}@test.com") is True
            keys.append(cur.execute.call_args_list[-1][0][1][0])
        assert keys == ["acct:uuid-user-A", "acct:uuid-user-B"]

    def test_unknown_identity_skips_write(self, monkeypatch):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        conn, cur = _mock_conn(fetch_row=None)
        with patch("src.db.get_db_connection", return_value=conn):
            assert _record("ghost@test.com") is False
        assert mw.get_write_stats()["unresolved_identity"] == 1
        # identity SELECT ran, INSERT never did
        assert cur.execute.call_count == 1


# ── Privacy exclusion filter (ADR-001 §8) ────────────────────────────────────

class TestExclusionFilter:
    def test_secret_keys_dropped_at_any_depth(self):
        cleaned = mw.sanitize_payload({
            "action": "save",
            "api_key": "sk-oops",
            "nested": {"Authorization": "Bearer x", "keep": 1,
                       "deeper": {"PASSWORD": "p"}},
        })
        assert cleaned == {"action": "save", "nested": {"keep": 1, "deeper": {}}}
        assert mw.get_write_stats()["excluded_keys_dropped"] == 3

    def test_oversized_strings_truncated(self):
        cleaned = mw.sanitize_payload({"blob": "x" * 5000})
        assert len(cleaned["blob"]) < 2100
        assert cleaned["blob"].endswith("…[truncated]")


# ── Failure swallowing + envelope validation ─────────────────────────────────

class TestNeverRaises:
    def test_db_exception_swallowed_and_counted(self, monkeypatch):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        conn, cur = _mock_conn()
        cur.execute.side_effect = RuntimeError("db down")
        with patch("src.db.get_db_connection", return_value=conn):
            assert _record("public:web-x") is False
        assert mw.get_write_stats()["failed"] == 1

    def test_invalid_source_rejected(self, monkeypatch):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        assert _record(source="made_up_tier") is False
        assert mw.get_write_stats()["failed"] == 1


# ── Zero behavior change on the action path ──────────────────────────────────

class TestRuntimeWiring:
    def test_handle_action_unaffected_when_writer_explodes(self):
        from src.agent.runtime import agent_runtime
        job = {"title": "QA Engineer", "company": "TestCo", "link": "https://x.test/j"}
        with patch("src.agent.runtime.AgentRuntime._audit"), \
             patch("src.agent.runtime.is_duplicate", return_value=False), \
             patch("src.applications.mark_applied", return_value=True), \
             patch("src.services.memory_writer.record_action_episode",
                   side_effect=RuntimeError("memory exploded")):
            result = agent_runtime.handle_action(
                user_id="u@test.com", action="save", job_key="jk1", job=job,
            )
        assert result.ok is True

    def test_handle_action_passes_runtime_idempotency_identity(self):
        from src.agent.runtime import agent_runtime
        job = {"title": "QA Engineer", "company": "TestCo", "link": "https://x.test/j"}
        with patch("src.agent.runtime.AgentRuntime._audit"), \
             patch("src.agent.runtime.is_duplicate", return_value=False), \
             patch("src.applications.mark_applied", return_value=True), \
             patch("src.services.memory_writer.record_action_episode") as rec:
            result = agent_runtime.handle_action(
                user_id="u@test.com", action="save", job_key="jk1", job=job,
            )
        assert result.ok is True
        rec.assert_called_once()
        kwargs = rec.call_args.kwargs
        assert kwargs["action"] == "save"
        assert kwargs["job_key"] == "jk1"
        assert kwargs["ok"] is True
        assert len(kwargs["action_id"]) == 16  # runtime's md5-derived identity
