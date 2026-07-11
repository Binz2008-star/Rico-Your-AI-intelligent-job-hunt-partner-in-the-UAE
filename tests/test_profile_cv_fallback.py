"""
tests/test_profile_cv_fallback.py

Tests for fix(files): show parsed profile CV when no active CV document exists.

The legacy 'profile-cv' fallback used to fire only when user_documents was
empty. A user with a parsed profile CV plus one unrelated upload (e.g. a
doc_type="other" file) therefore saw no active CV in My Files or in Rico's
chat context. The fallback now fires whenever there is no document with
doc_type == "cv" AND is_primary == true, and real documents are kept.

Also covers the second-upload flow: an allowed second document appears in
My Files after success, and a second CV on the Free plan returns a clear
structured quota error rather than fake success.

All DB / profile / subscription calls are mocked — no real database.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


def _other_doc():
    return {
        "id": "doc-other-1",
        "user_id": "alice@rico.ai",
        "filename": "Roben_Edwan_VIP_Relationship_Manager_CV.pdf",
        "original_filename": "Roben_Edwan_VIP_Relationship_Manager_CV.pdf",
        "doc_type": "other",
        "file_size": 120000,
        "label": None,
        "is_primary": False,
        "skills_count": 0,
        "years_experience": None,
        "created_at": "2026-06-12T10:40:00+00:00",
        "updated_at": "2026-06-12T10:40:00+00:00",
    }


def _primary_cv_doc():
    return {
        "id": "doc-cv-1",
        "user_id": "alice@rico.ai",
        "filename": "Roben_CV_2026.pdf",
        "original_filename": "Roben_CV_2026.pdf",
        "doc_type": "cv",
        "file_size": 90000,
        "label": "Main CV",
        "is_primary": True,
        "skills_count": 12,
        "years_experience": 7.0,
        "created_at": "2026-06-12T10:41:00+00:00",
        "updated_at": "2026-06-12T10:41:00+00:00",
    }


def _profile_with_cv():
    return SimpleNamespace(
        cv_filename="Roben_Parsed_Profile_CV.pdf",
        cv_extracted_at="2026-05-20T12:00:00+00:00",
        skills=["banking", "crm", "sales", "arabic"],
        years_experience=9.0,
        current_role="VIP Relationship Manager",
    )


def _profile_without_cv():
    return SimpleNamespace(cv_filename=None, cv_extracted_at=None, skills=[], years_experience=None, current_role=None)


def _resolved_plan(plan_value="free", cv_limit=1, other_limit=2):
    from src.schemas.subscription import SubscriptionEntitlements
    entitlements = SubscriptionEntitlements(cv_storage_limit=cv_limit, other_document_limit=other_limit)
    plan = MagicMock()
    plan.value = plan_value
    subscription = MagicMock()
    subscription.entitlements = entitlements
    subscription.plan = plan
    resolved = MagicMock()
    resolved.subscription = subscription
    return resolved


@pytest.fixture(scope="module")
def auth_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": "alice@rico.ai", "role": "user"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


def _list_files(client, docs, profile):
    with patch("src.api.routers.files._db") as mock_db, \
         patch("src.api.routers.files.profile_repo.get_profile", return_value=profile), \
         patch("src.api.routers.files.resolve_effective_user_plan", return_value=_resolved_plan()):
        mock_db.available = True
        mock_db.list_user_documents.return_value = docs
        return client.get("/api/v1/user/files")


# ── GET /api/v1/user/files fallback matrix ─────────────────────────────────────

class TestFilesEndpointFallback:
    def test_other_doc_plus_profile_cv_returns_both(self, auth_client):
        r = _list_files(auth_client, [_other_doc()], _profile_with_cv())
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        by_id = {d["id"]: d for d in body["files"]}
        assert "profile-cv" in by_id
        assert "doc-other-1" in by_id
        synthetic = by_id["profile-cv"]
        assert synthetic["doc_type"] == "cv"
        assert synthetic["is_primary"] is True
        assert synthetic["is_legacy"] is True
        assert synthetic["filename"] == "Roben_Parsed_Profile_CV.pdf"
        # the real upload is not hidden and keeps its own type
        assert by_id["doc-other-1"]["doc_type"] == "other"
        assert by_id["doc-other-1"]["is_primary"] is False

    def test_real_primary_cv_means_no_synthetic_duplicate(self, auth_client):
        r = _list_files(auth_client, [_primary_cv_doc(), _other_doc()], _profile_with_cv())
        assert r.status_code == 200
        body = r.json()
        ids = [d["id"] for d in body["files"]]
        assert "profile-cv" not in ids
        assert body["total"] == 2

    def test_empty_docs_plus_profile_cv_returns_synthetic(self, auth_client):
        r = _list_files(auth_client, [], _profile_with_cv())
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["files"][0]["id"] == "profile-cv"
        assert body["files"][0]["is_primary"] is True

    def test_docs_without_profile_cv_returns_only_real_docs(self, auth_client):
        r = _list_files(auth_client, [_other_doc()], _profile_without_cv())
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["files"][0]["id"] == "doc-other-1"

    def test_synthetic_record_does_not_count_against_quota(self, auth_client):
        r = _list_files(auth_client, [_other_doc()], _profile_with_cv())
        quota = r.json()["quota"]
        # Enforcement counts user_documents rows: 0 CVs, 1 other.
        assert quota["cv_used"] == 0
        assert quota["other_used"] == 1


# ── Chat context mirrors the files endpoint ────────────────────────────────────

def _build_chat_ctx(docs, profile):
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI.__new__(RicoChatAPI)
    api._memory = MagicMock()
    api._memory.load_chat_history.return_value = []

    mock_db = MagicMock()
    mock_db.available = True
    mock_db.list_user_documents.return_value = docs

    with patch("src.rico_db.RicoDB", return_value=mock_db):
        with patch.object(api, "_get_recent_messages", return_value=[]):
            with patch.object(api, "_recent_jobs_summary", return_value=""):
                return api._build_openai_context(profile, user_id="alice@rico.ai")


class TestChatContextMirrorsFilesEndpoint:
    def test_other_doc_plus_profile_cv_yields_both_with_synthetic_active(self):
        ctx = _build_chat_ctx([_other_doc()], {"cv_filename": "Roben_Parsed_Profile_CV.pdf"})
        docs = ctx["uploaded_documents"]
        assert len(docs) == 2
        # synthetic active CV first, real upload kept
        assert docs[0]["filename"] == "Roben_Parsed_Profile_CV.pdf"
        assert docs[0]["doc_type"] == "cv"
        assert docs[0]["is_primary"] is True
        assert docs[0]["is_legacy"] is True
        assert docs[1]["filename"] == "Roben_Edwan_VIP_Relationship_Manager_CV.pdf"
        assert docs[1]["doc_type"] == "other"

    def test_real_primary_cv_means_no_synthetic_in_context(self):
        ctx = _build_chat_ctx([_primary_cv_doc(), _other_doc()], {"cv_filename": "Roben_Parsed_Profile_CV.pdf"})
        filenames = [d["filename"] for d in ctx["uploaded_documents"]]
        assert "Roben_Parsed_Profile_CV.pdf" not in filenames
        assert len(filenames) == 2

    def test_non_primary_cv_doc_still_gets_profile_fallback(self):
        non_primary_cv = dict(_primary_cv_doc(), is_primary=False)
        ctx = _build_chat_ctx([non_primary_cv], {"cv_filename": "Roben_Parsed_Profile_CV.pdf"})
        docs = ctx["uploaded_documents"]
        assert docs[0]["is_legacy"] is True
        assert docs[0]["is_primary"] is True
        assert len(docs) == 2

    def test_docs_without_profile_cv_returns_only_real_docs(self):
        ctx = _build_chat_ctx([_other_doc()], {"skills": ["x"]})
        docs = ctx["uploaded_documents"]
        assert len(docs) == 1
        assert docs[0]["doc_type"] == "other"


# ── Second-upload behavior ─────────────────────────────────────────────────────

class TestSecondUpload:
    def test_second_allowed_document_appears_in_my_files_after_success(self, auth_client):
        """Upload an allowed second doc (201), then list must include it."""
        fake_pdf = b"%PDF-1.4 fake"
        with patch("src.api.routers.files.enforce_document_quota"), \
             patch("src.api.routers.files._db") as mock_db:
            mock_db.available = True
            mock_db.find_user_document_by_hash.return_value = None
            mock_db.get_or_create_user_document.return_value = {
                "id": "doc-other-2",
                "filename": "certificates.pdf",
                "doc_type": "other",
                "is_primary": False,
                "inserted": True,
            }
            r_up = auth_client.post(
                "/api/v1/user/files?doc_type=other",
                files={"file": ("certificates.pdf", fake_pdf, "application/pdf")},
            )
        assert r_up.status_code == 201
        assert r_up.json()["ok"] is True

        second = dict(_other_doc(), id="doc-other-2", filename="certificates.pdf")
        r_list = _list_files(auth_client, [_other_doc(), second], _profile_without_cv())
        ids = [d["id"] for d in r_list.json()["files"]]
        assert "doc-other-2" in ids

    def test_second_cv_on_free_plan_returns_clear_quota_error(self, auth_client):
        """Second CV on Free must 422 with a structured, human-readable error —
        never a 2xx fake success."""
        fake_pdf = b"%PDF-1.4 fake"
        with patch("src.services.subscription_gating.count_user_documents", return_value=1), \
             patch("src.services.subscription_gating.resolve_effective_user_plan",
                   return_value=_resolved_plan("free", cv_limit=1)), \
             patch("src.api.routers.files._db") as mock_db:
            mock_db.available = True
            # New exact-dedupe pre-check (#960): a distinct 2nd CV is not a duplicate,
            # so quota enforcement still runs and returns 422.
            mock_db.find_user_document_by_hash.return_value = None
            r = auth_client.post(
                "/api/v1/user/files?doc_type=cv",
                files={"file": ("second_cv.pdf", fake_pdf, "application/pdf")},
            )
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert detail["detail"] == "cv_storage_limit_exceeded"
        assert detail["used"] == 1
        assert detail["limit"] == 1
        # Clear, actionable error — not a silent failure
        assert detail.get("message")
        assert "upgrade" in str(detail.get("upgrade_hint", "")).lower()
        mock_db.get_or_create_user_document.assert_not_called()
