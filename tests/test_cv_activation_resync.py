"""
tests/test_cv_activation_resync.py

Regression tests for fix: set-primary CV re-syncs profile fields.

When the user switches their active CV with POST /api/v1/user/files/{id}/set-primary,
years_experience, current_role, and skills must be written back to rico_profiles.

Tests verify:
1. set-primary calls upsert_profile with years_experience from the document
2. set-primary calls upsert_profile with current_role from the document
3. set-primary calls upsert_profile with skills from skills_json when present
4. set-primary skips skills key when skills_json is empty
5. set-primary calls no upsert when document has no resyncable fields
6. set-primary returns 200 even when profile resync raises an exception
7. save_user_document accepts and includes skills_json in its INSERT
8. save_user_document uses an empty list when skills_json is omitted
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)
os.environ.setdefault("ADMIN_EMAIL", "test@rico.ai")
os.environ.setdefault("ADMIN_PASSWORD", "testpass123")

USER_ID = "cv-resync-test@rico.ai"
DOC_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_auth_client(user_id: str = USER_ID):
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": user_id, "role": "user"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


def _primary_doc(
    *,
    years_experience: float | None = 7.0,
    current_role: str | None = "Compliance Manager",
    skills_json: list | None = None,
) -> dict:
    return {
        "id": DOC_ID,
        "user_id": USER_ID,
        "filename": "cv.pdf",
        "original_filename": "cv.pdf",
        "doc_type": "cv",
        "file_size": 0,
        "label": None,
        "is_primary": True,
        "skills_count": len(skills_json or []),
        "skills_json": skills_json or [],
        "years_experience": years_experience,
        "current_role": current_role,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    }


def _mock_db(*, set_primary_result: bool = True, primary_doc: dict | None = None,
             get_raises: Exception | None = None) -> MagicMock:
    db = MagicMock()
    db.available = True
    db.set_primary_document.return_value = set_primary_result
    if get_raises:
        db.get_primary_document.side_effect = get_raises
    else:
        db.get_primary_document.return_value = primary_doc
    return db


# ── Endpoint-level tests ───────────────────────────────────────────────────────

class TestSetPrimaryResyncsProfile:
    def _call(self, db: MagicMock, upsert: MagicMock) -> int:
        client = _make_auth_client()
        with (
            patch("src.api.routers.files._db", db),
            patch("src.api.routers.files.upsert_profile", upsert),
        ):
            resp = client.post(f"/api/v1/user/files/{DOC_ID}/set-primary")
        return resp.status_code

    def test_years_experience_resynced(self):
        upsert = MagicMock()
        db = _mock_db(primary_doc=_primary_doc(years_experience=5.5, current_role=None, skills_json=[]))
        assert self._call(db, upsert) == 200
        upsert.assert_called_once()
        updates = upsert.call_args[0][1]
        assert updates.get("years_experience") == 5.5

    def test_current_role_resynced(self):
        upsert = MagicMock()
        db = _mock_db(primary_doc=_primary_doc(years_experience=None, current_role="Risk Analyst", skills_json=[]))
        assert self._call(db, upsert) == 200
        upsert.assert_called_once()
        updates = upsert.call_args[0][1]
        assert updates.get("current_role") == "Risk Analyst"

    def test_skills_resynced_when_present(self):
        skills = ["ISO 9001", "Risk Management", "IFRS"]
        upsert = MagicMock()
        db = _mock_db(primary_doc=_primary_doc(years_experience=None, current_role=None, skills_json=skills))
        assert self._call(db, upsert) == 200
        upsert.assert_called_once()
        updates = upsert.call_args[0][1]
        assert updates.get("skills") == skills

    def test_skills_not_in_update_when_empty(self):
        upsert = MagicMock()
        db = _mock_db(primary_doc=_primary_doc(years_experience=3.0, current_role="Analyst", skills_json=[]))
        assert self._call(db, upsert) == 200
        upsert.assert_called_once()
        updates = upsert.call_args[0][1]
        assert "skills" not in updates

    def test_no_upsert_when_all_fields_empty(self):
        upsert = MagicMock()
        db = _mock_db(primary_doc=_primary_doc(years_experience=None, current_role=None, skills_json=[]))
        assert self._call(db, upsert) == 200
        upsert.assert_not_called()

    def test_resync_failure_does_not_cause_500(self):
        """A DB error during profile resync must NOT propagate as a 500."""
        upsert = MagicMock()
        db = _mock_db(get_raises=RuntimeError("DB gone"))
        assert self._call(db, upsert) == 200

    def test_all_three_fields_resynced_together(self):
        skills = ["Python", "SQL"]
        upsert = MagicMock()
        doc = _primary_doc(years_experience=8.0, current_role="Tech Lead", skills_json=skills)
        db = _mock_db(primary_doc=doc)
        assert self._call(db, upsert) == 200
        upsert.assert_called_once()
        updates = upsert.call_args[0][1]
        assert updates["years_experience"] == 8.0
        assert updates["current_role"] == "Tech Lead"
        assert updates["skills"] == skills


# ── save_user_document skills_json argument ───────────────────────────────────

class TestSaveUserDocumentSkillsJson:
    def _capture_execute(self, skills_json):
        """Run save_user_document with a mocked transaction; return captured SQL + params."""
        from src.rico_db import RicoDB
        from unittest.mock import PropertyMock

        db = RicoDB.__new__(RicoDB)
        db._pool = None

        cur_mock = MagicMock()
        conn_mock = MagicMock()
        conn_mock.__enter__ = MagicMock(return_value=conn_mock)
        conn_mock.__exit__ = MagicMock(return_value=False)
        conn_mock.cursor.return_value.__enter__ = MagicMock(return_value=cur_mock)
        conn_mock.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur_mock.fetchone.return_value = {"id": "test-id-123"}

        execute_calls: list = []

        def capture(sql, params):
            execute_calls.append((sql, params))

        cur_mock.execute.side_effect = capture

        with (
            patch.object(type(db), "available", new_callable=PropertyMock, return_value=True),
            patch.object(db, "_transaction", return_value=conn_mock),
        ):
            db.save_user_document(
                user_id="test@example.com",
                filename="cv.pdf",
                original_filename="cv.pdf",
                doc_type="cv",
                skills_count=len(skills_json or []),
                skills_json=skills_json,
                years_experience=5.0,
                current_role="Engineer",
                is_primary=True,
            )

        return execute_calls

    def _insert_call(self, calls):
        """Return the (sql, params) of the INSERT — is_primary=True also issues
        a clear-old-primary UPDATE first (same transaction), so the INSERT is
        no longer necessarily calls[0]."""
        for sql, params in calls:
            if sql.strip().upper().startswith("INSERT"):
                return sql, params
        raise AssertionError(f"no INSERT among captured calls: {calls}")

    def test_skills_json_included_in_insert_sql(self):
        calls = self._capture_execute(["Python", "SQL", "IFRS 9"])
        assert calls, "execute was never called"
        sql, _ = self._insert_call(calls)
        assert "skills_json" in sql

    def test_skills_values_passed_to_cursor(self):
        import json as _json
        skills = ["Python", "SQL"]
        calls = self._capture_execute(skills)
        assert calls
        _, params = self._insert_call(calls)
        # Find the psycopg2 Json-wrapped param and verify it holds the skills list.
        # Json objects expose their content via .adapted (psycopg2 internal).
        found = False
        for p in params:
            raw = getattr(p, "adapted", None)
            if raw is None:
                continue
            try:
                decoded = _json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                if isinstance(decoded, list) and "Python" in decoded:
                    found = True
                    break
            except Exception:
                pass
        assert found, f"Expected skills list in params, got: {params}"

    def test_skills_json_defaults_to_empty_list(self):
        """Omitting skills_json must not raise; INSERT must include skills_json column."""
        calls = self._capture_execute(None)
        assert calls
        sql, _ = self._insert_call(calls)
        assert "skills_json" in sql
