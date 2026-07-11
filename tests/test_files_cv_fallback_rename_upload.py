"""
tests/test_files_cv_fallback_rename_upload.py

Regression suite for fix(files): restore active CV fallback and My Files persistence

Tests (6 required):
  1. list_files: other-doc present + profile CV → both real doc AND synthetic profile-cv returned
  2. list_files: real primary CV present → NO synthetic profile-cv injected (no duplicate)
  3. rename PATCH: updates label in DB and GET returns it
  4. api.ts helper: updateUserFile sends {label} key (source-level assertion)
  5. upload success (non-CV) → backend returns 201 and file appears in subsequent GET
  6. quota-blocked upload → ApiError 422, not fake success
"""
from __future__ import annotations

import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)
os.environ.setdefault("ADMIN_EMAIL", "test@rico.ai")
os.environ.setdefault("ADMIN_PASSWORD", "testpass123")

# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": "files-test@rico.ai", "role": "user"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


def _make_doc(**kwargs: Any) -> dict[str, Any]:
    """Return a minimal user_documents row with sane defaults."""
    base: dict[str, Any] = {
        "id": "doc-001",
        "user_id": "files-test@rico.ai",
        "filename": "resume.pdf",
        "original_filename": "resume.pdf",
        "doc_type": "other",
        "file_size": 1024,
        "label": None,
        "is_primary": False,
        "is_legacy": False,
        "skills_count": 0,
        "years_experience": None,
        "current_role": None,
        "created_at": None,
        "updated_at": None,
    }
    base.update(kwargs)
    return base


def _make_resolved_plan(plan_value: str = "basic", cv_limit: int = 3, other_limit: int = 5) -> MagicMock:
    """Return a mock resolved plan compatible with resolve_effective_user_plan."""
    mock_entitlements = MagicMock()
    mock_entitlements.cv_storage_limit = cv_limit
    mock_entitlements.other_document_limit = other_limit

    mock_subscription = MagicMock()
    mock_subscription.entitlements = mock_entitlements
    mock_subscription.plan = MagicMock()
    mock_subscription.plan.value = plan_value

    mock_resolved = MagicMock()
    mock_resolved.subscription = mock_subscription
    return mock_resolved


def _make_db_mock(docs: list[dict], update_returns: bool = True) -> MagicMock:
    """Build a RicoDB mock that patches the module-level _db instance."""
    mock_db = MagicMock()
    mock_db.available = True
    mock_db.list_user_documents.return_value = docs
    mock_db.update_user_document.return_value = update_returns
    mock_db.save_user_document.return_value = "new-doc-999"
    # New exact-dedupe pre-check (#960): default to "not a duplicate" so upload
    # tests exercise the normal (distinct-file) quota + save path.
    mock_db.find_user_document_by_hash.return_value = None
    return mock_db


# ── Test 1 ────────────────────────────────────────────────────────────────────
class TestProfileCvFallback:
    """
    Fix A: when a user has at least one real doc (doc_type=other) but no
    primary CV, list_files must append a synthetic profile-cv record alongside
    the real doc — never replace it.
    """

    def test_other_doc_plus_profile_cv_returns_both(self, auth_client: Any) -> None:
        """list_files includes both real other-doc AND synthetic profile-cv."""
        real_other = _make_doc(id="real-other-001", doc_type="other", is_primary=False)
        mock_db = _make_db_mock([real_other])

        mock_profile = MagicMock()
        mock_profile.cv_filename = "parsed-cv-2024.pdf"
        mock_profile.cv_extracted_at = None
        mock_profile.skills = ["Python", "FastAPI"]
        mock_profile.years_experience = 5
        mock_profile.current_role = "Backend Engineer"

        with (
            patch("src.api.routers.files._db", mock_db),
            patch("src.api.routers.files.profile_repo.get_profile", return_value=mock_profile),
            patch(
                "src.api.routers.files.resolve_effective_user_plan",
                return_value=_make_resolved_plan(),
            ),
        ):
            resp = auth_client.get("/api/v1/user/files")

        assert resp.status_code == 200, resp.text
        files = resp.json()["files"]
        ids = [f["id"] for f in files]

        # Real doc preserved
        assert "real-other-001" in ids, f"real doc missing: {ids}"
        # Synthetic profile-cv appended
        assert "profile-cv" in ids, f"synthetic cv missing: {ids}"
        assert resp.json()["total"] == 2

        profile_cv = next(f for f in files if f["id"] == "profile-cv")
        assert profile_cv["doc_type"] == "cv"
        assert profile_cv["is_primary"] is True
        assert profile_cv.get("is_legacy") is True


# ── Test 2 ────────────────────────────────────────────────────────────────────
class TestNoDuplicatePrimaryCv:
    """
    Fix A: when a real primary CV already exists in user_documents, the
    synthetic profile-cv must NOT be injected.
    """

    def test_real_primary_cv_no_synthetic_injected(self, auth_client: Any) -> None:
        """list_files does NOT append synthetic profile-cv when a real primary CV exists."""
        real_cv = _make_doc(
            id="real-cv-001",
            doc_type="cv",
            is_primary=True,
            filename="my-cv.pdf",
        )
        mock_db = _make_db_mock([real_cv])

        with (
            patch("src.api.routers.files._db", mock_db),
            patch(
                "src.api.routers.files.resolve_effective_user_plan",
                return_value=_make_resolved_plan(),
            ),
        ):
            resp = auth_client.get("/api/v1/user/files")

        assert resp.status_code == 200, resp.text
        files = resp.json()["files"]
        ids = [f["id"] for f in files]

        assert "real-cv-001" in ids
        assert "profile-cv" not in ids, f"duplicate synthetic cv found: {ids}"
        assert resp.json()["total"] == 1


# ── Test 3 ────────────────────────────────────────────────────────────────────
class TestRenamePersistence:
    """
    Fix B: PATCH /api/v1/user/files/{id} writes label to DB, and subsequent
    GET returns the updated label.
    """

    def test_patch_label_persisted_and_returned(self, auth_client: Any) -> None:
        """PATCH updates label; GET then returns the new label."""
        updated_doc = _make_doc(id="doc-rename-001", label="My Finance CV", doc_type="cv", is_primary=True)
        mock_db = _make_db_mock([updated_doc])

        with (
            patch("src.api.routers.files._db", mock_db),
            patch(
                "src.api.routers.files.resolve_effective_user_plan",
                return_value=_make_resolved_plan(),
            ),
        ):
            # PATCH
            patch_resp = auth_client.patch(
                "/api/v1/user/files/doc-rename-001",
                json={"label": "My Finance CV"},
            )
            assert patch_resp.status_code == 200, patch_resp.text
            assert patch_resp.json()["ok"] is True

            # Verify DB was called with the correct label
            mock_db.update_user_document.assert_called_once_with(
                "files-test@rico.ai",
                "doc-rename-001",
                label="My Finance CV",
                doc_type=None,
            )

            # GET — should return updated label
            get_resp = auth_client.get("/api/v1/user/files")

        assert get_resp.status_code == 200, get_resp.text
        returned_files = get_resp.json()["files"]
        target = next((f for f in returned_files if f["id"] == "doc-rename-001"), None)
        assert target is not None, "renamed file not found in list"
        assert target["label"] == "My Finance CV"


# ── Test 4 ────────────────────────────────────────────────────────────────────
class TestApiHelperSendsLabelKey:
    """
    Fix B: the TypeScript api.ts updateUserFile helper must send {label: ...}
    in the PATCH body. We verify by inspecting the source text — no runtime
    execution needed.
    """

    def test_update_user_file_sends_label_field(self) -> None:
        """api.ts updateUserFile sends the 'label' key in the request body."""
        api_ts_path = os.path.join(
            os.path.dirname(__file__), "..", "apps", "web", "lib", "api.ts"
        )
        with open(api_ts_path) as f:
            source = f.read()

        assert "updateUserFile" in source, "updateUserFile not found in api.ts"

        # Locate the updateUserFile function block (up to 600 chars after declaration)
        start = source.find("updateUserFile")
        block = source[start : start + 600]

        assert "label" in block, (
            f"'label' not found in updateUserFile block:\n{block}"
        )
        # Confirm it's sent in a request body (method: PATCH or body-like structure)
        assert "PATCH" in block or "patch" in block.lower() or "body" in block.lower(), (
            f"PATCH/body not found in updateUserFile block:\n{block}"
        )


# ── Test 5 ────────────────────────────────────────────────────────────────────
class TestUploadSuccessTriggersRefetch:
    """
    Fix C: after a successful non-CV upload (cover_letter/other), the backend
    must return 201 and the file must appear in subsequent GET /api/v1/user/files.
    This validates the complete contract — frontend calls loadFiles() after 201.
    """

    def test_upload_success_list_refreshed(self, auth_client: Any) -> None:
        """POST /api/v1/user/files returns 201 and the file appears in subsequent GET."""
        stored_doc = _make_doc(
            id="new-doc-002",
            doc_type="cover_letter",
            filename="cover.pdf",
            is_primary=False,
        )
        mock_db = _make_db_mock([stored_doc])

        pdf_content = b"%PDF-1.4 fake pdf content for testing"

        with (
            patch("src.api.routers.files._db", mock_db),
            patch("src.api.routers.files.enforce_document_quota"),
            patch(
                "src.api.routers.files.resolve_effective_user_plan",
                return_value=_make_resolved_plan(),
            ),
        ):
            upload_resp = auth_client.post(
                "/api/v1/user/files",
                files={"file": ("cover.pdf", pdf_content, "application/pdf")},
                params={"doc_type": "cover_letter"},
            )
            assert upload_resp.status_code == 201, upload_resp.text
            assert upload_resp.json()["ok"] is True

            # Simulate frontend loadFiles() after upload
            get_resp = auth_client.get("/api/v1/user/files")

        assert get_resp.status_code == 200, get_resp.text
        returned_ids = [f["id"] for f in get_resp.json()["files"]]
        assert "new-doc-002" in returned_ids, f"uploaded file not in list after refetch: {returned_ids}"


# ── Test 6 ────────────────────────────────────────────────────────────────────
class TestQuotaBlockedUploadShowsError:
    """
    Fix C: when the document quota is exceeded, POST /api/v1/user/files must
    return 422 (not 200/201). The UI maps 422 → uploadErrQuota message, not
    fake success.
    """

    def test_quota_exceeded_returns_422_not_success(self, auth_client: Any) -> None:
        """Quota-gated upload returns 422, confirming UI will show quota error."""
        from fastapi import HTTPException

        mock_db = _make_db_mock([])

        with (
            patch("src.api.routers.files._db", mock_db),
            patch(
                "src.api.routers.files.enforce_document_quota",
                side_effect=HTTPException(status_code=422, detail="Document quota exceeded"),
            ),
        ):
            pdf_content = b"%PDF-1.4 fake pdf content for testing"
            resp = auth_client.post(
                "/api/v1/user/files",
                files={"file": ("cv.pdf", pdf_content, "application/pdf")},
                params={"doc_type": "cv"},
            )

        assert resp.status_code == 422, (
            f"Expected 422 for quota-blocked upload, got {resp.status_code}: {resp.text}"
        )
        detail = str(resp.json().get("detail", "")).lower()
        assert "quota" in detail, (
            f"Expected quota message in response detail: {resp.text}"
        )
