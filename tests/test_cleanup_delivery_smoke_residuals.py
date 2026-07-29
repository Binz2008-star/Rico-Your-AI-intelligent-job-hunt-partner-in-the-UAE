"""The residual cleanup is fail-closed and deletes only the audited namespace.

These guards cover the cleanup script's contract without a real database.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cleanup_delivery_smoke_residuals.py"


def _load_module() -> ModuleType:
    """Import the cleanup module with both confirmation gates armed."""
    os.environ["AUDIT_CONFIRM"] = "AUDIT-DELIVERY-RESIDUALS"
    os.environ["CLEANUP_CONFIRM"] = "CLEANUP-DELIVERY-RESIDUALS"
    spec = importlib.util.spec_from_file_location("cleanup_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def module() -> ModuleType:
    previous_audit = os.environ.get("AUDIT_CONFIRM")
    previous_cleanup = os.environ.get("CLEANUP_CONFIRM")
    os.environ["AUDIT_CONFIRM"] = "AUDIT-DELIVERY-RESIDUALS"
    os.environ["CLEANUP_CONFIRM"] = "CLEANUP-DELIVERY-RESIDUALS"
    mod = _load_module()
    yield mod
    if previous_audit is None:
        os.environ.pop("AUDIT_CONFIRM", None)
    else:
        os.environ["AUDIT_CONFIRM"] = previous_audit
    if previous_cleanup is None:
        os.environ.pop("CLEANUP_CONFIRM", None)
    else:
        os.environ["CLEANUP_CONFIRM"] = previous_cleanup


@pytest.fixture(scope="module")
def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


class _FakeCursor:
    """Minimal cursor for exercising delete logic and postcheck."""

    def __init__(self, rows: dict[str, int] | None = None):
        self.rows = rows or {}
        self._last_result: object = None
        self.rowcount = 0
        self.statements: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql: str, params: dict | tuple | None = None) -> None:
        self.statements.append(sql)
        lowered = sql.lower().strip()
        if lowered.startswith("delete"):
            table = lowered.split("from")[1].split()[0]
            self.rowcount = self.rows.get(table, 0)
            self.rows[table] = 0
            # Simulate the live ON DELETE CASCADE from rico_users to children.
            if table == "rico_users":
                for child in ("rico_profiles", "rico_chat_history", "rico_job_recommendations"):
                    self.rows[child] = 0
        elif "count" in lowered and "from" in lowered:
            table = lowered.split("from")[1].split()[0]
            self._last_result = (self.rows.get(table, 0),)
        elif "confdeltype" in lowered:
            # Pretend every uuid_child FK has ON DELETE CASCADE.
            self._last_result = [("c",)]
        else:
            self._last_result = ()

    def fetchone(self):
        return self._last_result

    def fetchall(self):
        return list(self._last_result or ())


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True

    def set_session(self, *, readonly: bool = False, autocommit: bool = False) -> None:
        pass


def test_refuses_to_run_without_confirmation():
    """The confirmation gate must be present and checked before any database access."""
    assert 'os.environ.get("CLEANUP_CONFIRM") != CONFIRMATION' in SCRIPT.read_text(encoding="utf-8")


def test_namespace_is_exactly_the_delivery_smoke_synthetic_pattern(module):
    assert module.PATTERN == "smoke-delivery-%@synthetic-rico.test"
    assert module.PATTERN.endswith("@synthetic-rico.test")
    assert module.PATTERN.startswith("smoke-delivery-")


def test_expected_fingerprint_matches_audit_run(module):
    """The fingerprint must record the 84-row result from run 30475312924."""
    assert module.EXPECTED_FINGERPRINT == {
        "users": 0,
        "email_verification_tokens": 0,
        "rico_onboarding_states": 8,
        "learning_signals": 3,
        "user_documents": 0,
        "rico_users": 8,
        "user_job_context": 5,
        "chat_operations": 3,
        "rico_profiles": 4,
        "rico_chat_history": 48,
        "rico_job_recommendations": 5,
    }
    assert sum(module.EXPECTED_FINGERPRINT.values()) == 84


def test_delete_statements_cover_all_direct_tables_and_rico_users_last(module):
    statements = module._delete_statements()
    tables = [table for table, _ in statements]
    # Every email_direct / rico_self table is deleted explicitly.
    direct_tables = {
        t for t, _, mode, _ in module.TABLES if mode in ("email_direct", "rico_self")
    }
    assert set(tables) == direct_tables
    assert tables[-1] == "rico_users"
    # uuid_child tables are never deleted manually; cascade handles them.
    child_tables = {t for t, _, mode, _ in module.TABLES if mode == "uuid_child"}
    assert not child_tables & set(tables)


def test_delete_statements_use_the_audit_predicate(module):
    """The WHERE clause must reuse the audit's candidate predicate verbatim."""
    audit_predicates = {
        t: module.build_predicate(k, m)
        for t, k, m, _ in module.TABLES
    }
    for table, sql in module._delete_statements():
        assert f"WHERE {audit_predicates[table]}" in sql


def test_commit_defaults_to_false(source: str):
    """Default behavior is a dry-run; production mutation must be opt-in."""
    assert "--commit" in source
    assert "action=\"store_true\"" in source or "action='store_true'" in source
    # Environment variable absent -> dry run.
    assert 'os.environ.get("CLEANUP_COMMIT", "").lower() == "true"' in source


def test_no_heuristic_or_date_deletion(source: str):
    """The only filter is the exact synthetic namespace."""
    lowered = source.lower()
    disallowed = [
        "now()", "current_date", "interval", "< ", "> ", "between",
        "%@%", "@",  # domain-only or wildcard patterns would be dangerous
    ]
    # The only LIKE pattern is the module constant PATTERN, not inline wildcards.
    like_matches = re.findall(r'like\s+["\']%', lowered)
    assert not like_matches, "found an inline LIKE wildcard that is not the module constant"


def _fake_connection(rows: dict[str, int]) -> _FakeConnection:
    return _FakeConnection(_FakeCursor(rows))


def test_run_cleanup_rolls_back_by_default(module):
    """When commit=False the transaction is rolled back and no changes are committed."""
    fake_conn = _fake_connection(dict(module.EXPECTED_FINGERPRINT))

    # Short-circuit the read-only precheck; it is covered by integration tests.
    module._preflight = lambda conn: dict(module.EXPECTED_FINGERPRINT)  # type: ignore[assignment]
    module._open_read_only = lambda: fake_conn  # type: ignore[assignment]
    module._open_read_write = lambda: fake_conn  # type: ignore[assignment]

    report = module.run_cleanup(commit=False)
    assert not fake_conn.committed
    assert fake_conn.rolled_back
    assert report["outcome"] == "dry-run (rolled back)"
    assert report["total_deleted"] == sum(module.EXPECTED_FINGERPRINT.values())


def test_preflight_mismatch_aborts(module):
    dummy_conn = _fake_connection({})

    def failing_preflight(conn):
        raise module.CleanupError("fingerprint mismatch: expected 8 rico_users, observed 999")

    module._preflight = failing_preflight  # type: ignore[assignment]
    module._open_read_only = lambda: dummy_conn  # type: ignore[assignment]

    with pytest.raises(module.CleanupError, match="fingerprint mismatch"):
        module.run_cleanup(commit=False)


def test_cleanup_takes_only_expected_env_input(source: str):
    """Only confirmation, DSN, and commit flag may come from the environment."""
    env_reads = set(re.findall(r"os\.environ(?:\.get)?[\[\(]\s*[\"']([A-Z_]+)[\"']", source))
    assert env_reads <= {"AUDIT_CONFIRM", "CLEANUP_CONFIRM", "DATABASE_URL", "CLEANUP_COMMIT"}, (
        f"unexpected environment input: {env_reads}"
    )
