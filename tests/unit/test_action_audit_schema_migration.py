"""Contract tests for migration 030 action_audit_log hardening."""
from pathlib import Path


MIGRATION_PATH = Path("migrations/030_action_audit_log_hardening.sql")
AUDIT_REPO_PATH = Path("src/repositories/audit_repo.py")


def _migration_sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION_PATH.exists()


def test_extends_existing_action_audit_log():
    sql = _migration_sql()

    assert "ALTER TABLE action_audit_log" in sql
    assert "ADD COLUMN IF NOT EXISTS event_type TEXT" in sql
    assert "ADD COLUMN IF NOT EXISTS data JSONB" in sql
    assert "CREATE TABLE" not in sql.upper()


def test_creates_event_lookup_index():
    sql = _migration_sql()

    assert "CREATE INDEX IF NOT EXISTS idx_action_audit_event_type_timestamp" in sql
    assert "ON action_audit_log (event_type, timestamp DESC)" in sql


def test_enforces_append_only_mutations():
    sql = _migration_sql()

    assert "CREATE OR REPLACE FUNCTION reject_action_audit_log_mutation()" in sql
    assert "BEFORE UPDATE OR DELETE OR TRUNCATE ON action_audit_log" in sql
    assert "CREATE TRIGGER trg_action_audit_log_append_only" in sql
    assert "RAISE EXCEPTION" in sql


def test_is_idempotent_and_documents_manual_rollback():
    sql = _migration_sql()

    assert "ADD COLUMN IF NOT EXISTS" in sql
    assert "CREATE INDEX IF NOT EXISTS" in sql
    assert "DROP TRIGGER IF EXISTS" in sql
    assert "Rollback (manual, only if explicitly approved)" in sql


def test_does_not_create_parallel_agentic_foundations():
    sql = _migration_sql()

    forbidden = (
        "agent_audit_events",
        "agent_approval_tokens",
        "approval_hmac",
        "policy_gate",
        "audit_writer",
    )
    lowered = sql.lower()
    for name in forbidden:
        assert name not in lowered


def test_repository_no_longer_mutates_action_audit_schema_at_request_time():
    source = AUDIT_REPO_PATH.read_text(encoding="utf-8")

    assert "ALTER TABLE action_audit_log" not in source
    assert "information_schema.columns" not in source
