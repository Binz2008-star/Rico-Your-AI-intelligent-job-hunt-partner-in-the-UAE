"""
tests/test_document_storage_quotas.py

Tests for multi-CV / document storage quota feature (feat/document-storage-quotas).

Covers:
- Free user with 0 CVs can upload first CV
- Free user with 1 CV gets quota error on second upload attempt
- Pro user can upload up to 5 CVs
- Premium user is never blocked

All DB and subscription calls are mocked — no real database required.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)
os.environ.setdefault("ADMIN_EMAIL", "rico-admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_entitlements(cv_limit, other_limit):
    from src.schemas.subscription import SubscriptionEntitlements
    return SubscriptionEntitlements(
        monthly_ai_message_limit=50,
        saved_jobs_limit=10,
        profile_optimization_limit=1,
        cv_storage_limit=cv_limit,
        other_document_limit=other_limit,
    )


def _make_resolved(cv_limit, other_limit, plan_value="free"):
    entitlements = _make_entitlements(cv_limit, other_limit)
    plan = MagicMock()
    plan.value = plan_value
    subscription = MagicMock()
    subscription.entitlements = entitlements
    subscription.plan = plan
    resolved = MagicMock()
    resolved.subscription = subscription
    return resolved


# ── SubscriptionEntitlements schema ───────────────────────────────────────────

class TestEntitlementsSchema:
    def test_free_entitlements_have_cv_limit_of_1(self):
        from src.subscription_plans import FREE_ENTITLEMENTS
        assert FREE_ENTITLEMENTS.cv_storage_limit == 1

    def test_free_entitlements_have_other_limit_of_2(self):
        from src.subscription_plans import FREE_ENTITLEMENTS
        assert FREE_ENTITLEMENTS.other_document_limit == 2

    def test_pro_plan_has_cv_limit_of_5(self):
        from src.subscription_plans import RICO_MONTHLY_PLAN
        assert RICO_MONTHLY_PLAN.entitlements.cv_storage_limit == 5

    def test_pro_plan_has_other_limit_of_10(self):
        from src.subscription_plans import RICO_MONTHLY_PLAN
        assert RICO_MONTHLY_PLAN.entitlements.other_document_limit == 10

    def test_entitlements_serialise_to_dict(self):
        from src.subscription_plans import FREE_ENTITLEMENTS
        d = FREE_ENTITLEMENTS.model_dump()
        assert d["cv_storage_limit"] == 1
        assert d["other_document_limit"] == 2


# ── _build_gate_check / GateCheck ─────────────────────────────────────────────

class TestBuildGateCheck:
    def _check(self, usage, resolved):
        from src.services.subscription_gating import _build_gate_check
        with patch("src.subscription_plans.resolve_effective_user_plan", return_value=resolved):
            return _build_gate_check("user@x.com", "cv_storage_limit", usage, resolved)

    def test_free_user_0_cvs_is_allowed(self):
        check = self._check(0, _make_resolved(1, 2))
        assert check.allowed is True
        assert check.remaining == 1

    def test_free_user_1_cv_is_blocked(self):
        check = self._check(1, _make_resolved(1, 2))
        assert check.allowed is False
        assert check.remaining == 0

    def test_pro_user_4_cvs_is_allowed(self):
        check = self._check(4, _make_resolved(5, 10, "pro"))
        assert check.allowed is True
        assert check.remaining == 1

    def test_pro_user_5_cvs_is_blocked(self):
        check = self._check(5, _make_resolved(5, 10, "pro"))
        assert check.allowed is False

    def test_premium_user_is_never_blocked(self):
        check = self._check(100, _make_resolved(None, None, "premium"))
        assert check.allowed is True
        assert check.limit is None
        assert check.remaining is None


# ── subscription_gating.enforce_document_quota ────────────────────────────────

class TestEnforceDocumentQuota:
    """enforce_document_quota raises HTTP 422 when blocked."""

    def _enforce(self, doc_type, count, resolved):
        from src.services.subscription_gating import enforce_document_quota
        with patch("src.services.subscription_gating.resolve_effective_user_plan", return_value=resolved):
            with patch("src.services.subscription_gating.count_user_documents", return_value=count):
                enforce_document_quota("user@x.com", doc_type)

    def test_free_0_cvs_does_not_raise(self):
        self._enforce("cv", 0, _make_resolved(1, 2))  # no exception

    def test_free_1_cv_raises_422(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            self._enforce("cv", 1, _make_resolved(1, 2))
        assert exc_info.value.status_code == 422
        detail = exc_info.value.detail
        assert detail["detail"] == "cv_storage_limit_exceeded"
        assert detail["plan"] == "free"
        assert detail["used"] == 1
        assert detail["limit"] == 1
        assert "upgrade" in detail["upgrade_hint"].lower()

    def test_pro_4_cvs_does_not_raise(self):
        self._enforce("cv", 4, _make_resolved(5, 10, "pro"))

    def test_pro_5_cvs_raises_422(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            self._enforce("cv", 5, _make_resolved(5, 10, "pro"))
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["plan"] == "pro"

    def test_premium_unlimited_never_raises(self):
        self._enforce("cv", 999, _make_resolved(None, None, "premium"))

    def test_cover_letter_uses_other_document_limit(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            self._enforce("cover_letter", 2, _make_resolved(1, 2))
        assert exc_info.value.status_code == 422
        detail = exc_info.value.detail
        assert detail["detail"] == "other_document_limit_exceeded"
        assert detail["doc_type"] == "cover_letter"


# ── Files API endpoint ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": "alice@rico.ai", "role": "user"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


class TestFilesEndpointQuota:
    """Upload endpoint enforces quota before touching the DB."""

    def _post_file(self, client, *, quota_exceeded=False, db_available=True):
        """POST a minimal fake-PDF to /api/v1/user/files with mocked quota."""
        fake_pdf = b"%PDF-1.4 fake content"
        with patch("src.api.routers.files.enforce_document_quota") as mock_enforce:
            if quota_exceeded:
                # Simulate quota exceeded
                from fastapi import HTTPException
                mock_enforce.side_effect = HTTPException(
                    status_code=422,
                    detail={
                        "detail": "cv_storage_limit_exceeded",
                        "plan": "free",
                        "used": 1,
                        "limit": 1,
                        "upgrade_hint": "Upgrade to Pro",
                        "doc_type": "cv",
                        "message": "CV limit reached",
                    },
                )
            with patch("src.api.routers.files._db") as mock_db:
                mock_db.available = db_available
                # New exact-dedupe pre-check (#960): a distinct file is not a duplicate.
                mock_db.find_user_document_by_hash.return_value = None
                mock_db.get_or_create_user_document.return_value = {
                    "id": "new-uuid-123",
                    "filename": "cv.pdf",
                    "doc_type": "cv",
                    "is_primary": False,
                    "inserted": True,
                }
                return client.post(
                    "/api/v1/user/files?doc_type=cv",
                    files={"file": ("cv.pdf", fake_pdf, "application/pdf")},
                )

    def test_free_user_0_cvs_upload_succeeds(self, auth_client):
        """First CV upload is allowed (quota check passes, save called)."""
        r = self._post_file(auth_client, quota_exceeded=False)
        assert r.status_code == 201
        body = r.json()
        assert body["ok"] is True

    def test_free_user_1_cv_upload_returns_422(self, auth_client):
        """Second CV attempt returns 422 with structured quota error."""
        r = self._post_file(auth_client, quota_exceeded=True)
        assert r.status_code == 422
        body = r.json()
        detail = body.get("detail", body)
        if isinstance(detail, dict):
            assert detail.get("detail") == "cv_storage_limit_exceeded"
            assert detail.get("plan") == "free"
            assert detail.get("used") == 1
            assert detail.get("limit") == 1

    def test_upload_rejects_non_pdf(self, auth_client):
        """Non-PDF file should return 422 even before quota is checked."""
        with patch("src.api.routers.files.enforce_document_quota"):
            with patch("src.api.routers.files._db") as mock_db:
                mock_db.available = True
                r = auth_client.post(
                    "/api/v1/user/files?doc_type=cv",
                    files={"file": ("cv.docx", b"not a pdf", "application/octet-stream")},
                )
        assert r.status_code == 422

    def test_quota_endpoint_returns_plan_and_usage(self, auth_client):
        """GET /quota returns plan, cv used/limit, other used/limit."""
        from src.schemas.subscription import SubscriptionEntitlements
        entitlements = SubscriptionEntitlements(
            cv_storage_limit=1,
            other_document_limit=2,
        )
        plan = MagicMock()
        plan.value = "free"
        subscription = MagicMock()
        subscription.entitlements = entitlements
        subscription.plan = plan
        resolved = MagicMock()
        resolved.subscription = subscription

        with patch("src.api.routers.files.resolve_effective_user_plan", return_value=resolved):
            with patch("src.api.routers.files._db") as mock_db:
                mock_db.available = True
                mock_db.count_user_documents.return_value = 1
                r = auth_client.get("/api/v1/user/files/quota")

        assert r.status_code == 200
        body = r.json()
        assert body["plan"] == "free"
        assert "cv" in body
        assert body["cv"]["limit"] == 1


# ── Rico context awareness ─────────────────────────────────────────────────────

class TestRicoChatContext:
    """Injected uploaded_documents list is built from list_user_documents().

    RicoDB is imported inside _build_openai_context via a local import, so we
    patch it at src.rico_db.RicoDB (the class itself), not at rico_chat_api module level.
    """

    def _build_ctx(self, docs, db_available=True):
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI.__new__(RicoChatAPI)
        # Minimal init attrs that _build_openai_context may touch
        api._memory = MagicMock()
        api._memory.load_chat_history.return_value = []

        mock_db = MagicMock()
        mock_db.available = db_available
        mock_db.list_user_documents.return_value = docs

        # RicoDB is used via a local 'from src.rico_db import RicoDB as _RicoDB'
        # inside the method, so patch the class constructor in rico_db itself.
        with patch("src.rico_db.RicoDB", return_value=mock_db):
            with patch.object(api, "_get_recent_messages", return_value=[]):
                with patch.object(api, "_recent_jobs_summary", return_value=""):
                    ctx = api._build_openai_context(None, user_id="user@x.com")
        return ctx

    def test_no_documents_means_no_key_in_context(self):
        ctx = self._build_ctx([])
        assert "uploaded_documents" not in ctx

    def test_single_cv_injected_into_context(self):
        docs = [
            {
                "filename": "MyCv.pdf",
                "doc_type": "cv",
                "label": "Finance CV",
                "is_primary": True,
                "skills_count": 8,
                "years_experience": 5.0,
                "created_at": "2025-01-01T00:00:00+00:00",
                "updated_at": "2025-01-01T00:00:00+00:00",
            }
        ]
        ctx = self._build_ctx(docs)
        assert "uploaded_documents" in ctx
        uploaded = ctx["uploaded_documents"]
        assert len(uploaded) == 1
        assert uploaded[0]["doc_type"] == "cv"
        assert uploaded[0]["is_primary"] is True
        assert uploaded[0]["skills_count"] == 8

    def test_multiple_cvs_all_injected(self):
        docs = [
            {"filename": "cv1.pdf", "doc_type": "cv", "label": None, "is_primary": True, "skills_count": 5, "years_experience": 3.0},
            {"filename": "cv2.pdf", "doc_type": "cv", "label": "Tech CV", "is_primary": False, "skills_count": 9, "years_experience": 7.0},
        ]
        ctx = self._build_ctx(docs)
        assert len(ctx["uploaded_documents"]) == 2

    def test_db_unavailable_does_not_raise(self):
        """If RicoDB is unavailable, context is built without uploaded_documents."""
        ctx = self._build_ctx([], db_available=False)
        # Should not raise; uploaded_documents simply absent
        assert "uploaded_documents" not in ctx


# ── 6. /api/v1/rico/upload-cv — quota enforcement for authenticated uploads ────

class TestUploadCvEndpointQuota:
    """Tests that POST /api/v1/rico/upload-cv enforces quota for auth users."""

    def _upload(self, user_id: str, cv_count: int, cv_limit):
        """Drive rico_upload_cv with a patched quota check."""
        from io import BytesIO
        from fastapi.testclient import TestClient
        from src.api.app import app

        pdf_bytes = b"%PDF-1.4 minimal"

        resolved = _make_resolved(cv_limit, other_limit=2, plan_value="free")

        with (
            patch("src.services.subscription_gating.count_user_documents", return_value=cv_count),
            patch("src.services.subscription_gating.resolve_effective_user_plan", return_value=resolved),
            patch("src.api.routers.rico_chat._resolve_upload_user_id", return_value=user_id),
            patch("src.api.routers.rico_chat._is_valid_public_user_id", return_value=False),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/rico/upload-cv",
                files={"file": ("cv.pdf", BytesIO(pdf_bytes), "application/pdf")},
            )
        return response

    def test_free_user_with_0_cvs_passes_quota_check(self):
        """Free user with no CVs yet: upload proceeds past the quota gate."""
        r = self._upload("user@test.com", cv_count=0, cv_limit=1)
        # Quota passes — may fail later (parse error) but NOT 422 quota exceeded
        assert r.status_code != 422 or (
            isinstance(r.json().get("detail"), dict)
            and r.json()["detail"].get("detail") != "cv_storage_limit_exceeded"
        )

    def test_free_user_with_1_cv_blocked_by_quota(self):
        """Free user already has 1 CV (limit=1): upload must return 422."""
        r = self._upload("user@test.com", cv_count=1, cv_limit=1)
        assert r.status_code == 422
        detail = r.json().get("detail", {})
        assert isinstance(detail, dict), f"expected structured detail, got: {detail!r}"
        assert detail.get("detail") == "cv_storage_limit_exceeded"
        assert detail.get("used") == 1
        assert detail.get("limit") == 1

    def test_guest_user_bypasses_quota_check(self):
        """Guest session (public:*) is exempt — quota check must be skipped."""
        from io import BytesIO
        from fastapi.testclient import TestClient
        from src.api.app import app

        pdf_bytes = b"%PDF-1.4 minimal"

        with (
            patch("src.api.routers.rico_chat._resolve_upload_user_id",
                  return_value="public:web-abc123"),
            patch("src.api.routers.rico_chat._is_valid_public_user_id", return_value=True),
            # Quota enforcer must NOT be called for guest — if called, fail the test
            patch("src.services.subscription_gating.enforce_document_quota",
                  side_effect=AssertionError("quota must not be called for guest")) as mock_quota,
        ):
            client = TestClient(app, raise_server_exceptions=False)
            client.post(
                "/api/v1/rico/upload-cv",
                files={"file": ("cv.pdf", BytesIO(pdf_bytes), "application/pdf")},
            )
            mock_quota.assert_not_called()

    def test_auth_upload_uses_jwt_identity_not_guest_id(self):
        """
        Authenticated CV upload must resolve identity via JWT/session,
        NOT a public:* guest ID.  Verifies _resolve_upload_user_id is called
        and its result (not a hardcoded public ID) drives the quota check.
        """
        from io import BytesIO
        from fastapi.testclient import TestClient
        from src.api.app import app

        pdf_bytes = b"%PDF-1.4 minimal"
        quota_called_with: list = []

        def _capture_quota(uid, doc_type):
            quota_called_with.append((uid, doc_type))
            # Allow (don't raise)

        with (
            patch("src.api.routers.rico_chat._resolve_upload_user_id",
                  return_value="authed@example.com"),
            patch("src.api.routers.rico_chat._is_valid_public_user_id", return_value=False),
            patch("src.services.subscription_gating.enforce_document_quota",
                  side_effect=_capture_quota),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            client.post(
                "/api/v1/rico/upload-cv",
                files={"file": ("cv.pdf", BytesIO(pdf_bytes), "application/pdf")},
            )

        assert len(quota_called_with) == 1, "enforce_document_quota must be called exactly once"
        uid, doc_type = quota_called_with[0]
        assert uid == "authed@example.com", f"must use JWT identity, got: {uid!r}"
        assert not uid.startswith("public:"), f"must NOT be a guest ID, got: {uid!r}"
        assert doc_type == "cv"
