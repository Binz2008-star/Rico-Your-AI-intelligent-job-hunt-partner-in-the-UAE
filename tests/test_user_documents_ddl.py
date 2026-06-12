"""
tests/test_user_documents_ddl.py

Regression tests for the production 500 on GET /api/v1/user/files.

Root cause: src/rico_db.py defined `_USER_DOCUMENTS_DDL` twice; the second
definition shadowed the first and declared `current_role TEXT` unquoted.
CURRENT_ROLE is a reserved keyword in PostgreSQL, so `_ensure_schema` raised
`psycopg2.errors.SyntaxError: syntax error at or near "current_role"` on
every connect, turning every user_documents query into a 500.

These tests guard against the duplicate definition reappearing and against
the reserved column name being used unquoted, and verify schema creation and
list_user_documents() run against a mocked connection without error.

No real database is required.
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import src.rico_db as rico_db
from src.rico_db import RicoDB

_RICO_DB_SOURCE = Path(rico_db.__file__).read_text(encoding="utf-8")


# ── DDL source sanity ──────────────────────────────────────────────────────────

class TestUserDocumentsDDLSource:
    def test_exactly_one_ddl_definition(self):
        assert _RICO_DB_SOURCE.count("_USER_DOCUMENTS_DDL = ") == 1

    def test_ddl_quotes_current_role_column(self):
        assert '"current_role" TEXT' in rico_db._USER_DOCUMENTS_DDL

    def test_ddl_has_no_unquoted_current_role(self):
        # CURRENT_ROLE is reserved in PostgreSQL — it must always be quoted.
        unquoted = re.compile(r'(?<!")current_role(?!")')
        assert not unquoted.search(rico_db._USER_DOCUMENTS_DDL)

    def test_queries_use_quoted_current_role(self):
        # Every SQL reference to the column (outside parameter tuples and
        # Python identifiers) must be the quoted form.
        assert '"current_role"' in _RICO_DB_SOURCE


# ── Schema creation against a mocked connection ────────────────────────────────

def _mock_conn():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


class TestEnsureSchema:
    def test_ensure_schema_executes_user_documents_ddl_once(self):
        db = RicoDB(database_url="postgresql://fake-ensure-schema-test/db")
        conn, cursor = _mock_conn()
        try:
            db._ensure_schema(conn)
            executed = [c.args[0] for c in cursor.execute.call_args_list]
            assert rico_db._USER_DOCUMENTS_DDL in executed
            assert executed.count(rico_db._USER_DOCUMENTS_DDL) == 1
            conn.commit.assert_called_once()
        finally:
            RicoDB._schema_ready_urls.discard(db.database_url)

    def test_no_executed_ddl_contains_unquoted_current_role(self):
        db = RicoDB(database_url="postgresql://fake-ddl-scan-test/db")
        conn, cursor = _mock_conn()
        unquoted = re.compile(r'(?<!")current_role(?!")')
        try:
            db._ensure_schema(conn)
            for call in cursor.execute.call_args_list:
                sql = call.args[0]
                assert not unquoted.search(sql), f"unquoted current_role in DDL: {sql[:120]}"
        finally:
            RicoDB._schema_ready_urls.discard(db.database_url)


# ── list_user_documents against a mocked connection ────────────────────────────

class TestListUserDocuments:
    def test_list_user_documents_selects_quoted_current_role(self):
        db = RicoDB(database_url="postgresql://fake-list-docs-test/db")
        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = []

        with patch.object(db, "connect", return_value=conn):
            docs = db.list_user_documents("alice@rico.ai")

        assert docs == []
        select_sql = cursor.execute.call_args.args[0]
        assert '"current_role"' in select_sql
        assert "FROM user_documents" in select_sql

    def test_list_user_documents_serialises_rows(self):
        from datetime import datetime, timezone

        db = RicoDB(database_url="postgresql://fake-list-rows-test/db")
        conn, cursor = _mock_conn()
        ts = datetime(2026, 6, 1, tzinfo=timezone.utc)
        cursor.fetchall.return_value = [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "user_id": "alice@rico.ai",
                "filename": "cv.pdf",
                "original_filename": "cv.pdf",
                "doc_type": "cv",
                "file_size": 1024,
                "label": None,
                "is_primary": True,
                "skills_count": 5,
                "years_experience": 4.0,
                "current_role": "Accountant",
                "created_at": ts,
                "updated_at": ts,
            }
        ]

        with patch.object(db, "connect", return_value=conn):
            docs = db.list_user_documents("alice@rico.ai")

        assert len(docs) == 1
        assert docs[0]["id"] == "11111111-1111-1111-1111-111111111111"
        assert docs[0]["current_role"] == "Accountant"
        assert docs[0]["created_at"] == ts.isoformat()
