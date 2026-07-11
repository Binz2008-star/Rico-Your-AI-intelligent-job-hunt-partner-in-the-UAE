"""
tests/test_963_onboarding_cv_persistence.py

#963: persist confirmed onboarding CV and hydrate extracted profile fields,
using one canonical confirmation path shared with /command confirmation.

Covers:
  * repo (cv_upload_artifact_repo): create/resolve round trip, cross-user
    scoping (a valid upload_id never resolves for a different user_id),
    expiry (an expired row never resolves), graceful no-DB degradation
    (never raises).
  * route (/upload-cv): server-side SHA-256 of the ORIGINAL bytes, a durable
    upload_id returned for authenticated users, no artifact created for
    rejected/non-CV/classified documents (nothing reaches the CV pipeline).
  * route (/confirm-cv-profile): an artifact resolved by upload_id supplies
    content_hash/file_size/cv_text to the canonical get_or_create_user_document
    write and to upsert_profile's cv_text -- never the legacy save_user_document;
    a missing/expired/cross-user upload_id degrades gracefully (still uses the
    canonical path, just without hash/text); onboarding completion is decided
    by the SAME minimum-profile gate onboarding/submit uses, never a blind
    side effect of confirming a CV; a retried/duplicated confirm call is
    idempotent-safe (same content_hash both times, so the DB-level atomic
    dedupe proven in tests/test_user_documents_dedup.py applies uniformly);
    the endpoint is exactly the ONE code path both /command and onboarding
    use (no upload_id is optional/backward-compatible, not a fork).

All DB / AI-provider / quota calls are mocked -- no real database, no live
network calls.
"""
from __future__ import annotations

import hashlib
import io
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.models.onboarding import ONBOARDING_COMPLETED, ONBOARDING_IN_PROGRESS
from src.repositories.cv_upload_artifact_repo import (
    create_cv_upload_artifact,
    resolve_cv_upload_artifact,
)

_UTC = timezone.utc

_PUBLIC_UID = "public:web-963test12345"
_AUTH_UID = "alice@rico.ai"

_CV_TEXT = (
    "Jane Doe. Professional Summary: Senior product leader seeking a new role. "
    "Work Experience: Product Owner at FinCo 2017-2024. "
    "Education: BSc Computer Science, University of Dubai. "
    "Skills: product, delivery, stakeholder management. linkedin.com/in/janedoe"
)

_CV_PARSE_RESULT = {
    "text": _CV_TEXT,
    "skills": ["product", "delivery"],
    "emails": ["jane@example.com"],
    "phones": [],
    "years_experience_hint": 8.0,
    "certifications": [],
    "languages": ["english"],
    "extraction_quality": "good",
    "extracted_chars": len(_CV_TEXT),
    "name": "Jane Doe",
    "current_role": "Product Owner",
    "document_type": "cv",
}

_INVOICE_TEXT = (
    "Invoice Number: INV-2024-0091\nBill To: Acme Trading LLC\n"
    "Total Amount Due: AED 4,250.00\nPayment Due: 30 days\n"
)

_IDENTITY_TEXT = (
    "Passport Number: A1234567\nPlace of Birth: Dubai\n"
    "Machine Readable Zone\nIssuing Authority: UAE\n"
)


def _pdf(text: str) -> bytes:
    return b"%PDF-1.4\n" + text.encode("latin-1")


def _no_fitz():
    return patch.dict("sys.modules", {"fitz": None})


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from src.api.rate_limit import limiter
    limiter.reset()
    yield


# ── repo: cv_upload_artifact_repo ─────────────────────────────────────────────

def _cursor_returning(row):
    cur = MagicMock()
    cur.fetchone.return_value = row
    # Real psycopg2 cursors expose an int rowcount; the opportunistic purge in
    # create_cv_upload_artifact reads it. Default 0 so a MagicMock rowcount
    # never breaks the `> 0` comparison.
    cur.rowcount = 0
    return cur


def _conn_with_cursor(cur):
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    return conn


class TestCvUploadArtifactRepoCreate:
    def test_create_returns_id_and_commits(self):
        cur = _cursor_returning(["11111111-1111-1111-1111-111111111111"])
        conn = _conn_with_cursor(cur)
        with patch("src.db.get_db_connection", return_value=conn):
            artifact_id = create_cv_upload_artifact(
                "alice@rico.ai",
                filename="cv.pdf",
                doc_type="cv",
                content_hash="abc123",
                file_size=1024,
                cv_text="Jane Doe CV text",
            )
        assert artifact_id == "11111111-1111-1111-1111-111111111111"
        conn.commit.assert_called_once()
        all_sql = " ".join(str(c.args[0]).upper() for c in cur.execute.call_args_list)
        assert "INSERT INTO CV_UPLOAD_ARTIFACTS" in all_sql
        # The same transaction also opportunistically purges expired rows
        # (Blocker 2: actual deletion, no background worker).
        assert "DELETE FROM CV_UPLOAD_ARTIFACTS" in all_sql
        assert "EXPIRES_AT < NOW()" in all_sql

    def test_create_returns_none_when_db_unavailable(self):
        with patch("src.db.get_db_connection", return_value=None):
            artifact_id = create_cv_upload_artifact(
                "alice@rico.ai", filename="cv.pdf", doc_type="cv",
                content_hash="abc123", file_size=10, cv_text="x",
            )
        assert artifact_id is None

    def test_create_never_raises_on_db_error(self):
        cur = MagicMock()
        cur.execute.side_effect = RuntimeError("boom")
        conn = _conn_with_cursor(cur)
        with patch("src.db.get_db_connection", return_value=conn):
            artifact_id = create_cv_upload_artifact(
                "alice@rico.ai", filename="cv.pdf", doc_type="cv",
                content_hash="abc123", file_size=10, cv_text="x",
            )
        assert artifact_id is None
        conn.rollback.assert_called_once()

    def test_create_returns_none_without_required_fields(self):
        assert create_cv_upload_artifact(
            "", filename="cv.pdf", doc_type="cv", content_hash="abc", file_size=1, cv_text="x",
        ) is None
        assert create_cv_upload_artifact(
            "alice@rico.ai", filename="cv.pdf", doc_type="cv", content_hash="", file_size=1, cv_text="x",
        ) is None


class TestCvUploadArtifactRepoResolve:
    def test_resolve_returns_artifact_fields(self):
        cur = _cursor_returning(("cv.pdf", "cv", "abc123", 1024, "full cv text"))
        conn = _conn_with_cursor(cur)
        with patch("src.db.get_db_connection", return_value=conn):
            artifact = resolve_cv_upload_artifact("alice@rico.ai", "11111111-1111-1111-1111-111111111111")
        assert artifact == {
            "filename": "cv.pdf", "doc_type": "cv", "content_hash": "abc123",
            "file_size": 1024, "cv_text": "full cv text",
        }
        sql = cur.execute.call_args.args[0].upper()
        assert "USER_ID = %S" in sql and "EXPIRES_AT > NOW()" in sql

    def test_resolve_scoped_to_user_id_in_query(self):
        """The SELECT filters on (id AND user_id) -- a valid id for a
        different user is filtered out by the DB, never returned as a match."""
        cur = _cursor_returning(None)
        conn = _conn_with_cursor(cur)
        with patch("src.db.get_db_connection", return_value=conn):
            artifact = resolve_cv_upload_artifact("mallory@rico.ai", "11111111-1111-1111-1111-111111111111")
        assert artifact is None
        params = cur.execute.call_args.args[1]
        assert params == ("11111111-1111-1111-1111-111111111111", "mallory@rico.ai")

    def test_resolve_returns_none_when_no_row(self):
        cur = _cursor_returning(None)
        conn = _conn_with_cursor(cur)
        with patch("src.db.get_db_connection", return_value=conn):
            artifact = resolve_cv_upload_artifact("alice@rico.ai", "does-not-exist")
        assert artifact is None

    def test_resolve_never_raises_on_db_error(self):
        cur = MagicMock()
        cur.execute.side_effect = RuntimeError("boom")
        conn = _conn_with_cursor(cur)
        with patch("src.db.get_db_connection", return_value=conn):
            artifact = resolve_cv_upload_artifact("alice@rico.ai", "some-id")
        assert artifact is None

    def test_resolve_returns_none_without_db(self):
        with patch("src.db.get_db_connection", return_value=None):
            assert resolve_cv_upload_artifact("alice@rico.ai", "some-id") is None


# ── route: /upload-cv — server-side hash + artifact creation ─────────────────

class TestUploadCvArtifactCreation:
    def test_authenticated_upload_creates_artifact_with_server_hash(self, client):
        from src.api.auth import create_access_token
        token = create_access_token({"sub": _AUTH_UID, "role": "user"})
        client.cookies.set("access_token", token)
        raw = _pdf(_CV_TEXT)
        expected_hash = hashlib.sha256(raw).hexdigest()
        try:
            with (
                _no_fitz(),
                patch("src.services.chat_service.parse_cv", return_value=_CV_PARSE_RESULT),
                patch("src.api.routers.rico_chat.get_profile", return_value=None),
                patch("src.services.cv_quality_warnings.build_cv_quality_warnings", return_value=[]),
                patch(
                    "src.repositories.cv_upload_artifact_repo.create_cv_upload_artifact",
                    return_value="artifact-uuid-1",
                ) as create_mock,
            ):
                r = client.post(
                    "/api/v1/rico/upload-cv",
                    files={"file": ("jane_cv.pdf", io.BytesIO(raw), "application/pdf")},
                )
        finally:
            client.cookies.clear()
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "preview_ready"
        assert body["upload_id"] == "artifact-uuid-1"
        create_mock.assert_called_once()
        kwargs = create_mock.call_args.kwargs
        assert kwargs["content_hash"] == expected_hash
        assert kwargs["file_size"] == len(raw)
        assert kwargs["cv_text"] == _CV_TEXT

    def test_guest_upload_creates_no_artifact(self, client):
        raw = _pdf(_CV_TEXT)
        with (
            _no_fitz(),
            patch("src.services.chat_service.parse_cv", return_value=_CV_PARSE_RESULT),
            patch("src.api.routers.rico_chat.get_profile", return_value=None),
            patch("src.services.cv_quality_warnings.build_cv_quality_warnings", return_value=[]),
            patch("src.repositories.cv_upload_artifact_repo.create_cv_upload_artifact") as create_mock,
        ):
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("jane_cv.pdf", io.BytesIO(raw), "application/pdf")},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "preview_ready"
        assert body.get("upload_id") is None
        create_mock.assert_not_called()

    def test_rejected_invoice_upload_creates_no_artifact(self, client):
        """Rejected/non-CV documents never reach the artifact-creation code —
        it sits after every classification/rejection branch in upload-cv."""
        with (
            _no_fitz(),
            patch("src.services.chat_service.parse_cv", return_value=_CV_PARSE_RESULT),
            patch("src.repositories.cv_upload_artifact_repo.create_cv_upload_artifact") as create_mock,
        ):
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("invoice.pdf", io.BytesIO(_pdf(_INVOICE_TEXT)), "application/pdf")},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "classified"
        assert "preview" not in body
        create_mock.assert_not_called()

    def test_identity_document_upload_creates_no_artifact(self, client):
        with (
            _no_fitz(),
            patch("src.services.chat_service.parse_cv", return_value=_CV_PARSE_RESULT),
            patch("src.repositories.cv_upload_artifact_repo.create_cv_upload_artifact") as create_mock,
        ):
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
                files={"file": ("passport.pdf", io.BytesIO(_pdf(_IDENTITY_TEXT)), "application/pdf")},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "rejected"
        create_mock.assert_not_called()


# ── route: /confirm-cv-profile — artifact resolution + canonical write ───────

_ARTIFACT = {
    "filename": "upload.pdf",
    "doc_type": "cv",
    "content_hash": "deadbeef" * 8,
    "file_size": 54321,
    "cv_text": _CV_TEXT,
}


def _confirm_payload(*, filename="upload.pdf", doc_type="cv", upload_id=None):
    payload = {
        "preview": {
            "name": "Jane Doe",
            "current_role": "Product Owner",
            "experience_years": 8,
            "skills_detected": ["product", "delivery"],
            "target_roles": ["Product Manager"],
            "certifications": [],
            "languages": ["english"],
        },
        "filename": filename,
        "doc_type": doc_type,
    }
    if upload_id is not None:
        payload["upload_id"] = upload_id
    return payload


def _make_fake_ricodb(get_or_create_mock):
    class _FakeRicoDB:
        available = True

        def __init__(self, *a, **kw):
            pass

        def get_or_create_user_document(self, **kwargs):
            get_or_create_mock(**kwargs)
            return {
                "id": "fake-doc-id", "filename": kwargs.get("filename"),
                "doc_type": kwargs.get("doc_type"), "is_primary": kwargs.get("is_primary", False),
                "inserted": True,
            }

        def save_user_document(self, **kwargs):
            raise AssertionError("legacy save_user_document must never be called")

    return _FakeRicoDB


class TestConfirmCvProfileArtifactResolution:
    def _post_confirm(self, client, *, upload_id=None, gate_ok=True, resolve_return=_ARTIFACT):
        get_or_create_mock = MagicMock()
        upsert_mock = MagicMock()
        with (
            patch("src.api.routers.rico_chat.upsert_profile", upsert_mock),
            patch("src.api.routers.rico_chat.get_profile", return_value=None),
            patch("src.services.profile_context_resolver.evaluate_minimum_profile", return_value=(gate_ok, [])),
            patch("src.repositories.onboarding_repo.set_onboarding_status") as set_status_mock,
            patch("src.services.subscription_gating.enforce_profile_optimization_allowed"),
            patch("src.services.subscription_gating.record_profile_optimization_usage"),
            patch("src.api.routers.rico_chat._resolve_upload_user_id", return_value=_AUTH_UID),
            patch(
                "src.repositories.cv_upload_artifact_repo.resolve_cv_upload_artifact",
                return_value=resolve_return,
            ) as resolve_mock,
            patch("src.rico_db.RicoDB", _make_fake_ricodb(get_or_create_mock)),
        ):
            r = client.post(
                f"/api/v1/rico/confirm-cv-profile?user_id={_AUTH_UID}",
                json=_confirm_payload(upload_id=upload_id),
            )
        return r, get_or_create_mock, upsert_mock, resolve_mock, set_status_mock

    def test_valid_upload_id_confirms_and_dedupes(self, client):
        """A complete, matching, unexpired artifact confirms normally and
        supplies the server-computed hash/size/text -- the ONLY path that
        creates a user_documents row."""
        r, get_or_create_mock, upsert_mock, resolve_mock, _ = self._post_confirm(client, upload_id="artifact-1")
        assert r.status_code == 200, r.text
        resolve_mock.assert_called_once_with(_AUTH_UID, "artifact-1")
        get_or_create_mock.assert_called_once()
        kwargs = get_or_create_mock.call_args.kwargs
        assert kwargs["content_hash"] == _ARTIFACT["content_hash"]
        assert kwargs["file_size"] == _ARTIFACT["file_size"]
        assert upsert_mock.call_args.kwargs["cv_text"] == _ARTIFACT["cv_text"]

    def _assert_rejected_no_side_effects(self, r, get_or_create_mock, upsert_mock, set_status_mock):
        assert r.status_code == 409, r.text
        body = r.json()
        assert body == {
            "ok": False,
            "status": "cv_confirmation_required",
            "message": "Please upload the CV again before confirming.",
        }
        # No side effects at all -- not even a profile write or onboarding
        # status change, let alone a document row.
        upsert_mock.assert_not_called()
        get_or_create_mock.assert_not_called()
        set_status_mock.assert_not_called()

    def test_missing_upload_id_is_rejected(self, client):
        """#975 blocker 1: a caller that never sends upload_id must be
        rejected outright (409), never silently degrade to an unhashed
        document."""
        r, get_or_create_mock, upsert_mock, resolve_mock, set_status_mock = self._post_confirm(
            client, upload_id=None,
        )
        resolve_mock.assert_not_called()
        self._assert_rejected_no_side_effects(r, get_or_create_mock, upsert_mock, set_status_mock)

    def test_expired_upload_id_is_rejected(self, client):
        """An expired artifact resolves to None (resolve_cv_upload_artifact's
        own SQL filters `expires_at > NOW()`) -- confirm must reject, not
        fall back to an unhashed document."""
        r, get_or_create_mock, upsert_mock, resolve_mock, set_status_mock = self._post_confirm(
            client, upload_id="expired-artifact", resolve_return=None,
        )
        resolve_mock.assert_called_once_with(_AUTH_UID, "expired-artifact")
        self._assert_rejected_no_side_effects(r, get_or_create_mock, upsert_mock, set_status_mock)

    def test_foreign_upload_id_is_rejected(self, client):
        """An upload_id that belongs to a different user never resolves
        (resolve_cv_upload_artifact scopes by id AND user_id) -- confirm must
        reject, never leak or persist using another user's artifact."""
        r, get_or_create_mock, upsert_mock, resolve_mock, set_status_mock = self._post_confirm(
            client, upload_id="belongs-to-mallory", resolve_return=None,
        )
        resolve_mock.assert_called_once_with(_AUTH_UID, "belongs-to-mallory")
        self._assert_rejected_no_side_effects(r, get_or_create_mock, upsert_mock, set_status_mock)

    def test_artifact_missing_content_hash_is_rejected(self, client):
        incomplete = {**_ARTIFACT, "content_hash": None}
        r, get_or_create_mock, upsert_mock, resolve_mock, set_status_mock = self._post_confirm(
            client, upload_id="incomplete-artifact", resolve_return=incomplete,
        )
        self._assert_rejected_no_side_effects(r, get_or_create_mock, upsert_mock, set_status_mock)

    def test_artifact_missing_file_size_is_rejected(self, client):
        incomplete = {**_ARTIFACT, "file_size": None}
        r, get_or_create_mock, upsert_mock, resolve_mock, set_status_mock = self._post_confirm(
            client, upload_id="incomplete-artifact", resolve_return=incomplete,
        )
        self._assert_rejected_no_side_effects(r, get_or_create_mock, upsert_mock, set_status_mock)

    def test_artifact_missing_filename_is_rejected(self, client):
        incomplete = {**_ARTIFACT, "filename": None}
        r, get_or_create_mock, upsert_mock, resolve_mock, set_status_mock = self._post_confirm(
            client, upload_id="incomplete-artifact", resolve_return=incomplete,
        )
        self._assert_rejected_no_side_effects(r, get_or_create_mock, upsert_mock, set_status_mock)

    def test_artifact_missing_doc_type_is_rejected(self, client):
        incomplete = {**_ARTIFACT, "doc_type": None}
        r, get_or_create_mock, upsert_mock, resolve_mock, set_status_mock = self._post_confirm(
            client, upload_id="incomplete-artifact", resolve_return=incomplete,
        )
        self._assert_rejected_no_side_effects(r, get_or_create_mock, upsert_mock, set_status_mock)

    def test_mismatched_artifact_filename_is_rejected(self, client):
        """The artifact resolved (right user, unexpired) but records a
        DIFFERENT filename than the one being confirmed -- a stale preview
        confirmed against a since-changed upload. Must reject, never
        silently attach the wrong artifact's hash/text to this confirm."""
        mismatched = {**_ARTIFACT, "filename": "a-different-file.pdf"}
        r, get_or_create_mock, upsert_mock, resolve_mock, set_status_mock = self._post_confirm(
            client, upload_id="artifact-1", resolve_return=mismatched,
        )
        self._assert_rejected_no_side_effects(r, get_or_create_mock, upsert_mock, set_status_mock)

    def test_double_submit_same_upload_id_feeds_same_content_hash_twice(self, client):
        """Idempotency precondition: a retried/duplicated confirm for the
        SAME upload_id must feed get_or_create_user_document the identical
        content_hash both times -- that's what lets the DB-level atomic
        dedupe (tests/test_user_documents_dedup.py) collapse it to one row."""
        r1, get_or_create_mock_1, _, _, _ = self._post_confirm(client, upload_id="dup-artifact")
        r2, get_or_create_mock_2, _, _, _ = self._post_confirm(client, upload_id="dup-artifact")
        assert r1.status_code == 200 and r2.status_code == 200
        hash1 = get_or_create_mock_1.call_args.kwargs["content_hash"]
        hash2 = get_or_create_mock_2.call_args.kwargs["content_hash"]
        assert hash1 == hash2 == _ARTIFACT["content_hash"]

    def test_confirm_persists_literal_preview_values_no_server_merge(self, client):
        """Backend half of 'user-edited fields win': confirm-cv-profile must
        write exactly the preview values it was given, never silently merge
        with a prior stored value -- last caller wins is an orchestration
        property (frontend call order), which only holds if this endpoint is
        a pure overwrite, not a coalesce."""
        _, _, upsert_mock, _, _ = self._post_confirm(client, upload_id="artifact-1")
        updates = upsert_mock.call_args.kwargs["updates"]
        assert updates["target_roles"] == ["Product Manager"]
        assert updates["skills"] == ["product", "delivery"]
        assert updates["years_experience"] == 8


class TestConfirmCvProfileOnboardingGate:
    def _post_confirm(self, client, *, gate_ok: bool):
        # A valid, complete, matching artifact -- these tests exercise the
        # onboarding-completion gate, which (since #975 blocker 1) is only
        # reached once the artifact passes strict validation.
        get_or_create_mock = MagicMock()
        with (
            patch("src.api.routers.rico_chat.upsert_profile"),
            patch("src.api.routers.rico_chat.get_profile", return_value=None),
            patch("src.services.profile_context_resolver.evaluate_minimum_profile", return_value=(gate_ok, [])),
            patch("src.repositories.onboarding_repo.set_onboarding_status") as set_status_mock,
            patch("src.api.routers.rico_chat.mark_onboarding_complete") as legacy_mark_mock,
            patch("src.services.subscription_gating.enforce_profile_optimization_allowed"),
            patch("src.services.subscription_gating.record_profile_optimization_usage"),
            patch("src.api.routers.rico_chat._resolve_upload_user_id", return_value=_AUTH_UID),
            patch(
                "src.repositories.cv_upload_artifact_repo.resolve_cv_upload_artifact",
                return_value=_ARTIFACT,
            ),
            patch("src.rico_db.RicoDB", _make_fake_ricodb(get_or_create_mock)),
        ):
            r = client.post(
                f"/api/v1/rico/confirm-cv-profile?user_id={_AUTH_UID}",
                json=_confirm_payload(upload_id="artifact-1"),
            )
        return r, set_status_mock, legacy_mark_mock

    def test_gate_passing_marks_completed(self, client):
        r, set_status_mock, legacy_mark_mock = self._post_confirm(client, gate_ok=True)
        assert r.status_code == 200, r.text
        set_status_mock.assert_called_once_with(_AUTH_UID, ONBOARDING_COMPLETED)
        legacy_mark_mock.assert_not_called()

    def test_gate_failing_marks_in_progress_not_complete(self, client):
        """#963 architecture requirement: onboarding completion must use the
        existing minimum-profile gate, not a blind confirm side effect. A CV
        confirm alone (missing target_roles/preferred_cities/years) must
        never flip onboarding to 'complete'."""
        r, set_status_mock, legacy_mark_mock = self._post_confirm(client, gate_ok=False)
        assert r.status_code == 200, r.text
        set_status_mock.assert_called_once_with(_AUTH_UID, ONBOARDING_IN_PROGRESS)
        legacy_mark_mock.assert_not_called()

    def test_guest_confirm_never_touches_onboarding_status(self, client):
        get_or_create_mock = MagicMock()
        with (
            patch("src.api.routers.rico_chat.upsert_profile"),
            patch("src.repositories.onboarding_repo.set_onboarding_status") as set_status_mock,
            patch("src.services.subscription_gating.record_profile_optimization_usage"),
        ):
            r = client.post(
                f"/api/v1/rico/confirm-cv-profile?user_id={_PUBLIC_UID}",
                json=_confirm_payload(),
            )
        assert r.status_code == 200, r.text
        set_status_mock.assert_not_called()


def _make_failing_ricodb(exc: Exception):
    """Fake RicoDB whose canonical document write raises. `available` is True
    so we exercise the write-then-fail path, not the DB-unavailable branch."""
    class _FailingRicoDB:
        available = True

        def __init__(self, *a, **kw):
            pass

        def get_or_create_user_document(self, **kwargs):
            raise exc

        def save_user_document(self, **kwargs):
            raise AssertionError("legacy save_user_document must never be called")

    return _FailingRicoDB


class TestConfirmCvProfileDocumentPersistenceFailure:
    """#975 blocker 1: a My Files document-write failure must FAIL the confirm
    with a non-2xx and leave NO partial state — the document write runs first,
    before any profile/onboarding mutation, and is never swallowed."""

    def _post(self, client, *, ricodb_cls):
        upsert_mock = MagicMock()
        get_profile_mock = MagicMock(return_value=None)
        with (
            patch("src.api.routers.rico_chat.upsert_profile", upsert_mock),
            patch("src.api.routers.rico_chat.get_profile", get_profile_mock),
            patch("src.services.profile_context_resolver.evaluate_minimum_profile", return_value=(True, [])),
            patch("src.repositories.onboarding_repo.set_onboarding_status") as set_status_mock,
            patch("src.api.routers.rico_chat.mark_onboarding_complete") as legacy_mark_mock,
            patch("src.services.subscription_gating.enforce_profile_optimization_allowed"),
            patch("src.services.subscription_gating.record_profile_optimization_usage"),
            patch("src.api.routers.rico_chat._resolve_upload_user_id", return_value=_AUTH_UID),
            patch(
                "src.repositories.cv_upload_artifact_repo.resolve_cv_upload_artifact",
                return_value=_ARTIFACT,
            ),
            patch("src.rico_db.RicoDB", ricodb_cls),
        ):
            r = client.post(
                f"/api/v1/rico/confirm-cv-profile?user_id={_AUTH_UID}",
                json=_confirm_payload(upload_id="artifact-1"),
            )
        return r, upsert_mock, set_status_mock, legacy_mark_mock

    def test_doc_write_exception_returns_non_2xx_no_partial_state(self, client):
        r, upsert_mock, set_status_mock, legacy_mark_mock = self._post(
            client, ricodb_cls=_make_failing_ricodb(RuntimeError("db exploded")),
        )
        # Non-2xx, and explicitly NOT a success claim.
        assert r.status_code == 500, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "cv_persistence_failed"
        assert body["status"] != "profile_updated"
        # No partial state: nothing after the failed doc write ran.
        upsert_mock.assert_not_called()
        set_status_mock.assert_not_called()
        legacy_mark_mock.assert_not_called()

    def test_doc_db_unavailable_returns_non_2xx_no_partial_state(self, client):
        class _UnavailableRicoDB:
            available = False

            def __init__(self, *a, **kw):
                pass

            def get_or_create_user_document(self, **kwargs):
                raise AssertionError("must not be called when DB unavailable")

            def save_user_document(self, **kwargs):
                raise AssertionError("legacy save_user_document must never be called")

        r, upsert_mock, set_status_mock, legacy_mark_mock = self._post(
            client, ricodb_cls=_UnavailableRicoDB,
        )
        assert r.status_code == 503, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "cv_persistence_unavailable"
        upsert_mock.assert_not_called()
        set_status_mock.assert_not_called()
        legacy_mark_mock.assert_not_called()


class TestConfirmCvProfileProfilePersistenceFailure:
    """#975 follow-up blocker: a silent Neon failure of the PROFILE-field write
    must NOT be masked by the JSON memory mirror and reported as success. The
    profile write is require_db=True, so on a DB failure confirm returns a
    non-2xx and never marks onboarding complete — and a retry is safe."""

    def _post(self, client, *, upsert_side_effect):
        get_or_create_mock = MagicMock()
        upsert_mock = MagicMock(side_effect=upsert_side_effect)
        record_usage_mock = MagicMock()
        with (
            patch("src.api.routers.rico_chat.upsert_profile", upsert_mock),
            patch("src.api.routers.rico_chat.get_profile", return_value=None),
            patch("src.services.profile_context_resolver.evaluate_minimum_profile", return_value=(True, [])),
            patch("src.repositories.onboarding_repo.set_onboarding_status") as set_status_mock,
            patch("src.services.subscription_gating.enforce_profile_optimization_allowed"),
            patch("src.services.subscription_gating.record_profile_optimization_usage", record_usage_mock),
            patch("src.api.routers.rico_chat._resolve_upload_user_id", return_value=_AUTH_UID),
            patch(
                "src.repositories.cv_upload_artifact_repo.resolve_cv_upload_artifact",
                return_value=_ARTIFACT,
            ),
            patch("src.rico_db.RicoDB", _make_fake_ricodb(get_or_create_mock)),
        ):
            r = client.post(
                f"/api/v1/rico/confirm-cv-profile?user_id={_AUTH_UID}",
                json=_confirm_payload(upload_id="artifact-1"),
            )
        return r, get_or_create_mock, upsert_mock, set_status_mock, record_usage_mock

    def test_profile_db_failure_returns_non_2xx_no_completion(self, client):
        """require_db=True: a raised profile-persist error must surface as a
        non-2xx with no onboarding completion and no usage recorded — never a
        false success from the JSON mirror."""
        r, get_or_create_mock, upsert_mock, set_status_mock, record_usage_mock = self._post(
            client, upsert_side_effect=RuntimeError("neon write failed"),
        )
        assert r.status_code == 500, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "profile_persistence_failed"
        assert body["status"] != "profile_updated"
        # The My Files write ran first (and is idempotent), but nothing
        # downstream of the failed profile write ran.
        get_or_create_mock.assert_called_once()
        record_usage_mock.assert_not_called()
        set_status_mock.assert_not_called()

    def test_confirm_is_retry_safe_after_profile_db_failure(self, client):
        """A confirm that failed on a transient Neon error can be retried
        safely: the retry re-runs the idempotent My Files write (dedupes on
        content_hash) and the keyed profile UPSERT, and succeeds end-to-end."""
        # Attempt 1: Neon down -> 500, no completion.
        r1, goc1, _u1, set1, _r1 = self._post(client, upsert_side_effect=RuntimeError("neon down"))
        assert r1.status_code == 500
        assert r1.json()["status"] == "profile_persistence_failed"
        set1.assert_not_called()
        # Attempt 2: Neon recovered -> full success.
        r2, goc2, _u2, set2, _r2 = self._post(client, upsert_side_effect=None)
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "profile_updated"
        set2.assert_called_once_with(_AUTH_UID, ONBOARDING_COMPLETED)
        # The document write happened on BOTH attempts and is idempotent — a
        # retry never creates a duplicate row (real dedupe proven in
        # tests/integration + tests/test_user_documents_dedup.py).
        goc1.assert_called_once()
        goc2.assert_called_once()


# ── repo: Blocker 2 — expired artifacts are actually deleted ─────────────────

class TestCvUploadArtifactPurge:
    def test_purge_emits_bounded_delete_of_expired_rows(self):
        cur = _cursor_returning(None)
        cur.rowcount = 3
        conn = _conn_with_cursor(cur)
        from src.repositories.cv_upload_artifact_repo import purge_expired_cv_upload_artifacts
        with patch("src.db.get_db_connection", return_value=conn):
            deleted = purge_expired_cv_upload_artifacts(limit=50)
        assert deleted == 3
        conn.commit.assert_called_once()
        sql = " ".join(str(c.args[0]).upper() for c in cur.execute.call_args_list)
        assert "DELETE FROM CV_UPLOAD_ARTIFACTS" in sql
        assert "EXPIRES_AT < NOW()" in sql
        assert "LIMIT" in sql  # bounded, never an unbounded table-wide delete
        # The bound is passed as a parameter, not string-formatted.
        assert cur.execute.call_args_list[-1].args[1] == (50,)

    def test_purge_returns_zero_when_db_unavailable(self):
        from src.repositories.cv_upload_artifact_repo import purge_expired_cv_upload_artifacts
        with patch("src.db.get_db_connection", return_value=None):
            assert purge_expired_cv_upload_artifacts() == 0

    def test_purge_never_raises_on_db_error(self):
        cur = MagicMock()
        cur.execute.side_effect = RuntimeError("boom")
        conn = _conn_with_cursor(cur)
        from src.repositories.cv_upload_artifact_repo import purge_expired_cv_upload_artifacts
        with patch("src.db.get_db_connection", return_value=conn):
            assert purge_expired_cv_upload_artifacts() == 0
        conn.rollback.assert_called_once()


# ── repo contract: upsert_profile(require_db=...) ────────────────────────────

class TestProfileRepoRequireDb:
    """Locks the require_db contract that confirm-cv-profile relies on: with
    require_db=True a DB write failure RAISES (no false success masked by the
    JSON mirror); with the default it stays swallowed (mirror returned)."""

    def _patched(self, *, tx_raises: bool):
        from contextlib import contextmanager
        import src.repositories.profile_repo as pr

        @contextmanager
        def _tx():
            if tx_raises:
                raise RuntimeError("neon boom")
            yield MagicMock()

        mem = MagicMock()
        mem.upsert_profile_from_dict.return_value = "MIRROR_PROFILE"
        return patch.multiple(
            pr,
            _memory=MagicMock(return_value=mem),
            _db=MagicMock(return_value=MagicMock()),   # truthy DB
            _db_transaction=_tx,
        )

    def test_require_db_true_raises_on_db_failure(self):
        import src.repositories.profile_repo as pr
        with self._patched(tx_raises=True):
            with pytest.raises(Exception):
                pr.upsert_profile("alice@rico.ai", {"skills": ["x"]}, require_db=True)

    def test_require_db_false_swallows_db_failure_and_returns_mirror(self):
        import src.repositories.profile_repo as pr
        with self._patched(tx_raises=True):
            result = pr.upsert_profile("alice@rico.ai", {"skills": ["x"]}, require_db=False)
        assert result == "MIRROR_PROFILE"

    def test_require_db_true_no_db_configured_raises(self):
        import src.repositories.profile_repo as pr
        mem = MagicMock()
        mem.upsert_profile_from_dict.return_value = "MIRROR_PROFILE"
        with patch.multiple(pr, _memory=MagicMock(return_value=mem), _db=MagicMock(return_value=None)):
            with pytest.raises(Exception):
                pr.upsert_profile("alice@rico.ai", {"skills": ["x"]}, require_db=True)
