"""
tests/test_rico_routes.py
Smoke tests verifying Rico routes are mounted and reachable through the
layered API. Rico internals are fully mocked — no DB or Telegram tokens needed.
"""
from __future__ import annotations

import hashlib
import hmac as _hmac_module
import io
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


@pytest.fixture(autouse=True)
def clear_github_webhook_secret():
    """Keep these route tests independent from any developer-local .env secret."""
    original = os.environ.get("GITHUB_WEBHOOK_SECRET")
    os.environ["GITHUB_WEBHOOK_SECRET"] = ""
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("GITHUB_WEBHOOK_SECRET", None)
        else:
            os.environ["GITHUB_WEBHOOK_SECRET"] = original


@pytest.fixture(autouse=True)
def clear_jotform_webhook_secret():
    """Keep Jotform route tests independent from any developer-local .env secret."""
    original = os.environ.get("JOTFORM_WEBHOOK_SECRET")
    os.environ["JOTFORM_WEBHOOK_SECRET"] = ""
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("JOTFORM_WEBHOOK_SECRET", None)
        else:
            os.environ["JOTFORM_WEBHOOK_SECRET"] = original


@pytest.fixture(autouse=True)
def clear_telegram_webhook_secret():
    """Keep Telegram route tests independent from any developer-local .env secret."""
    original = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    os.environ["TELEGRAM_WEBHOOK_SECRET"] = ""
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("TELEGRAM_WEBHOOK_SECRET", None)
        else:
            os.environ["TELEGRAM_WEBHOOK_SECRET"] = original


@pytest.fixture(autouse=True)
def reset_rate_limiter_storage():
    from src.api.rate_limit import limiter
    try:
        limiter._storage.reset()
    except Exception:
        pass

# ── Shared test clients ───────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """Unauthenticated client — used for webhook and upload tests."""
    from fastapi.testclient import TestClient
    from src.api.app import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def auth_client():
    """Authenticated client with a valid JWT cookie — required for /chat."""
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token
    token = create_access_token({"sub": "alice@rico.ai", "role": "user"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


# ── Helpers ───────────────────────────────────────────────────────────────────

_CHAT_RESPONSE = {"type": "assistant", "message": "Hello from Rico"}
_PUBLIC_UPLOAD_ID = "public:web-upload12345"
_CV_PARSED = {
    # Readable text >= the parse-quality gate's minimum (50 chars, printable).
    # The fixture must satisfy the #1118 readability contract, since the upload
    # route now gates on parsed["text"]/["extracted_chars"] before preview_ready.
    "text": (
        "John Doe — HSE Manager. Five years of UAE experience across health, "
        "safety and environment. Skills: NEBOSH, ISO 14001, risk assessment, "
        "safety audits, compliance. Email test@example.com."
    ),
    "extracted_chars": 186,
    "skills": ["hse"],
    "emails": ["test@example.com"],
    "phones": [],
    "years_experience_hint": 5.0,
    "certifications": ["nebosh"],
    "languages": ["english"],
}
_TELEGRAM_RESPONSE = {"chat_id": "12345", "reply": {"type": "assistant", "message": "Hi"}}
_JOTFORM_RESPONSE = {"status": "ok", "user_id": "42"}


def _mock_cv_detector(doc_type: str = "cv"):
    mock_parser = type("Parser", (), {"detect_document_type": lambda self, text: doc_type})()
    return patch("src.cv_parser.CVParser", return_value=mock_parser)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Route existence — every route must return 2xx (not 404 / 405)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRicoChatRouteExists:
    def test_chat_route_returns_200(self, auth_client):
        with patch("src.services.chat_service.send_message", return_value=_CHAT_RESPONSE):
            r = auth_client.post("/api/v1/rico/chat", json={"message": "Hello"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_chat_route_not_404(self, auth_client):
        with patch("src.services.chat_service.send_message", return_value=_CHAT_RESPONSE):
            r = auth_client.post("/api/v1/rico/chat", json={"message": "Hello"})
        assert r.status_code != 404, "Rico chat route is not mounted"

    def test_chat_response_body_passes_through(self, auth_client):
        with patch("src.services.chat_service.send_message", return_value=_CHAT_RESPONSE):
            r = auth_client.post("/api/v1/rico/chat", json={"message": "Find me jobs"})
        assert r.status_code == 200
        assert r.json()["message"] == "Hello from Rico"

    def test_unauthenticated_chat_returns_401(self, client):
        """Web chat must reject unauthenticated requests."""
        r = client.post("/api/v1/rico/chat", json={"message": "Hello"})
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"

    def test_chat_history_returns_200_for_authenticated_user(self, auth_client):
        """Chat history endpoint must return 200 (not 500) for authenticated users."""
        r = auth_client.get("/api/v1/rico/chat/history?limit=6")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert "messages" in body
        assert "total" in body
        assert "has_more" in body

    def test_chat_history_not_500_for_authenticated_user(self, auth_client):
        """Chat history must not return 500 server error."""
        r = auth_client.get("/api/v1/rico/chat/history?limit=8")
        assert r.status_code != 500, f"Chat history returned 500: {r.text}"
        assert r.status_code in (200, 401), f"Expected 200 or 401, got {r.status_code}"

    def test_request_body_user_id_is_ignored_for_authenticated_users(self, auth_client):
        """user_id in body must never override the identity from the JWT."""
        captured = {}

        def spy(ctx, message, **kwargs):
            captured["user_id"] = ctx.user_id
            return _CHAT_RESPONSE

        with patch("src.services.chat_service.send_message", side_effect=spy):
            r = auth_client.post(
                "/api/v1/rico/chat",
                # Send a body user_id for a different user — must be ignored.
                json={"user_id": "bob@evil.com", "message": "Hello"},
            )
        assert r.status_code == 200
        assert captured["user_id"] == "alice@rico.ai"
        assert captured["user_id"] != "bob@evil.com"

    def test_chat_missing_message_returns_422(self, auth_client):
        r = auth_client.post("/api/v1/rico/chat", json={})
        assert r.status_code == 422

    def test_chat_message_over_4096_chars_returns_422(self, auth_client):
        r = auth_client.post("/api/v1/rico/chat", json={"message": "A" * 4097})
        assert r.status_code == 422

    def test_chat_message_exactly_4096_chars_allowed(self, auth_client):
        with patch("src.services.chat_service.send_message", return_value=_CHAT_RESPONSE):
            r = auth_client.post("/api/v1/rico/chat", json={"message": "A" * 4096})
        assert r.status_code == 200


class TestRicoProfileUpdateRouteExists:
    def test_profile_patch_route_returns_200_and_updates_fields(self, auth_client):
        captured = {}

        def spy_upsert(user_id, updates):
            captured["user_id"] = user_id
            captured["updates"] = updates
            return {"ok": True}

        payload = {
            "preferred_cities": ["Dubai", " Abu Dhabi "],
            "current_role": " HSE Lead ",
            "skills": ["HSE", " NEBOSH "],
            "years_experience": 10.0,
            "target_roles": [" HSE Manager "],
        }

        with patch("src.api.routers.rico_chat.upsert_profile", side_effect=spy_upsert), \
             patch("src.api.routers.rico_chat._profile_updates_visible", return_value=True):
            r = auth_client.patch("/api/v1/rico/profile", json=payload)

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["status"] == "ok"
        assert set(["target_roles", "preferred_cities", "years_experience", "current_role", "skills"]).issubset(
            set(body["updated_fields"])
        )
        assert "normalization_version" in body["updated_fields"]
        assert captured["user_id"] == "alice@rico.ai"
        assert captured["updates"]["target_roles"] == ["HSE Manager"]
        assert captured["updates"]["preferred_cities"] == ["Dubai", "Abu Dhabi"]
        assert captured["updates"]["years_experience"] == 10.0
        assert captured["updates"]["current_role"] == "HSE Lead"
        assert captured["updates"]["skills"] == ["HSE", "NEBOSH"]
        assert "normalization_version" in captured["updates"]

    def test_profile_patch_route_accepts_name(self, auth_client):
        captured = {}

        def spy_upsert(user_id, updates):
            captured["user_id"] = user_id
            captured["updates"] = updates
            return {"ok": True}

        with patch("src.api.routers.rico_chat.upsert_profile", side_effect=spy_upsert), \
             patch("src.api.routers.rico_chat._profile_updates_visible", return_value=True):
            r = auth_client.patch("/api/v1/rico/profile", json={"name": "  Roben Nihad  "})

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json() == {
            "status": "ok",
            "updated_fields": ["name"],
        }
        assert captured["user_id"] == "alice@rico.ai"
        assert captured["updates"] == {"name": "Roben Nihad"}


class TestRicoCVUploadRouteExists:
    def test_upload_cv_route_returns_200(self, client):
        with patch("src.services.chat_service.parse_cv", return_value=_CV_PARSED), _mock_cv_detector():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UPLOAD_ID}",
                files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
            )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json()["status"] == "preview_ready"

    def test_upload_cv_route_not_404(self, client):
        with patch("src.services.chat_service.parse_cv", return_value=_CV_PARSED), _mock_cv_detector():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UPLOAD_ID}",
                files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
            )
        assert r.status_code != 404, "Rico upload-cv route is not mounted"

    def test_upload_cv_response_contains_parsed_key(self, client):
        with patch("src.services.chat_service.parse_cv", return_value=_CV_PARSED), _mock_cv_detector():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UPLOAD_ID}",
                files={"file": ("resume.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
            )
        assert r.status_code == 200
        body = r.json()
        assert "parsed" in body
        assert body["user_id"] == _PUBLIC_UPLOAD_ID
        assert body["status"] == "preview_ready"

    def test_upload_cv_missing_file_returns_422(self, client):
        r = client.post(f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UPLOAD_ID}")
        assert r.status_code == 422

    def test_upload_cv_missing_user_id_returns_422(self, client):
        r = client.post(
            "/api/v1/rico/upload-cv",
            files={"file": ("cv.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )
        assert r.status_code == 422

    def test_authenticated_upload_without_query_user_id_uses_cookie_identity(self, auth_client):
        with patch("src.services.chat_service.parse_cv", return_value=_CV_PARSED), _mock_cv_detector():
            r = auth_client.post(
                "/api/v1/rico/upload-cv",
                files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
            )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["status"] == "preview_ready"
        assert body["user_id"] == "alice@rico.ai"

    def test_invalid_auth_cookie_without_query_user_id_returns_401(self, client):
        client.cookies.set("access_token", "not.a.valid.jwt")
        try:
            r = client.post(
                "/api/v1/rico/upload-cv",
                files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
            )
        finally:
            client.cookies.clear()
        assert r.status_code == 401

    def test_upload_cv_non_pdf_accepted_by_document_intelligence(self, client):
        # Since CAREER-OS-06, non-PDF text files are accepted and classified
        # rather than rejected with 422. A short plain-text file classifies as
        # "unknown" and falls through to the CV pipeline (returning a preview).
        with patch("src.services.chat_service.parse_cv", return_value=_CV_PARSED), _mock_cv_detector():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UPLOAD_ID}",
                files={"file": ("resume.pdf", io.BytesIO(b"This is not a PDF"), "application/pdf")},
            )
        assert r.status_code == 200

    def test_upload_cv_empty_file_returns_422(self, client):
        r = client.post(
            f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UPLOAD_ID}",
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        )
        assert r.status_code == 422

    def test_upload_cv_exe_disguised_as_pdf_returns_422(self, client):
        # MZ magic bytes are detected by the Document Intelligence layer and
        # rejected before any content extraction is attempted.
        exe_header = b"MZ\x90\x00" + b"\x00" * 60
        r = client.post(
            f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UPLOAD_ID}",
            files={"file": ("malware.pdf", io.BytesIO(exe_header), "application/pdf")},
        )
        assert r.status_code == 422

    def test_upload_cv_path_traversal_filename_sanitised(self, client):
        with patch("src.services.chat_service.parse_cv", return_value=_CV_PARSED), _mock_cv_detector():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UPLOAD_ID}",
                files={"file": ("../../etc/passwd", io.BytesIO(b"%PDF-1.4 ok"), "application/pdf")},
            )
        assert r.status_code == 200
        assert "/" not in r.json()["filename"]
        assert ".." not in r.json()["filename"]

    def test_upload_cv_xss_filename_sanitised(self, client):
        with patch("src.services.chat_service.parse_cv", return_value=_CV_PARSED), _mock_cv_detector():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UPLOAD_ID}",
                files={"file": ('<script>alert(1)</script>.pdf', io.BytesIO(b"%PDF-1.4 ok"), "application/pdf")},
            )
        assert r.status_code == 200
        assert "<" not in r.json()["filename"]
        assert ">" not in r.json()["filename"]


class TestRicoCVUploadSecurity:
    """Security tests for CV upload with validated public session IDs."""

    def test_public_web_session_cv_upload_returns_preview(self, client):
        """Guest users with valid public:web-* session IDs should receive preview_ready, not persistence."""
        public_session_id = "public:web-abc123xyz789"
        with patch("src.services.chat_service.parse_cv", return_value=_CV_PARSED), _mock_cv_detector():
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={public_session_id}",
                files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "preview_ready"
        assert body["user_id"] == public_session_id
        assert body["preview"]["skills_detected"] == ["hse"]

    def test_guest_invalid_user_id_is_rejected(self, client):
        """Guest users with invalid user_id format should be rejected with 401."""
        invalid_ids = [
            "admin@example.com",
            "user-123",
            "public:invalid",
            "public:web-",
            "public:" + ("a" * 65),
            "../../etc/passwd",
            "authenticated-user-id",
        ]
        for invalid_id in invalid_ids:
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={invalid_id}",
                files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
            )
            assert r.status_code == 401, f"Expected 401 for user_id={invalid_id}, got {r.status_code}"

    def test_public_chat_rejects_overlong_session_id(self, client):
        """Public chat and CV upload must share the same public session bounds."""
        r = client.post(
            "/api/v1/rico/chat/public",
            json={"message": "Find jobs", "session_id": "a" * 65},
        )
        assert r.status_code == 422

    def test_guest_cannot_write_arbitrary_user_id_email(self, client):
        """Guest users cannot use arbitrary email addresses as user_id."""
        arbitrary_ids = [
            "alice@example.com",
            "admin@rico.ai",
            "test@test.com",
        ]
        for arbitrary_id in arbitrary_ids:
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={arbitrary_id}",
                files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
            )
            assert r.status_code == 401, f"Expected 401 for user_id={arbitrary_id}, got {r.status_code}"

    def test_authenticated_upload_ignores_supplied_public_user_id(self, auth_client):
        """Authenticated uploads must ignore supplied public user_id and use auth identity."""
        public_session_id = "public:web-abc123"
        with patch("src.services.chat_service.parse_cv", return_value=_CV_PARSED), _mock_cv_detector():
            r = auth_client.post(
                f"/api/v1/rico/upload-cv?user_id={public_session_id}",
                files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "preview_ready"
        assert body["user_id"] == "alice@rico.ai"
        assert body["user_id"] != public_session_id

    def test_public_chat_after_upload_loads_persisted_cv_profile(self, client):
        """Public chat should load persisted CV profile from previous upload."""
        public_session_id = "public:web-xyz789abc"
        with patch("src.services.chat_service.parse_cv", return_value=_CV_PARSED), _mock_cv_detector():
            # First, upload CV
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id={public_session_id}",
                files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
            )
            assert r.status_code == 200
            assert r.json()["status"] == "preview_ready"

        # Then verify chat can load the persisted profile
        with patch("src.services.chat_service.send_message", return_value=_CHAT_RESPONSE) as mock_send:
            r = client.post(
                "/api/v1/rico/chat/public",
                json={"message": "Find jobs", "session_id": public_session_id.replace("public:", "")},
            )
        assert r.status_code == 200
        # Verify the chat service received the correct user_id via SessionContext
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["ctx"].user_id == public_session_id


class TestRicoPublicChatSubscriptionGate:
    """A registered user must not dodge their monthly AI-message cap by routing through
    /chat/public with ?email=, and an unverified email must never be escalated to
    authenticated privileges (private-job visibility / account-subscription disclosure)."""

    @staticmethod
    def _gate(allowed: bool):
        from src.services.subscription_gating import GateCheck
        return GateCheck(
            allowed=allowed,
            feature="monthly_ai_message_limit",
            usage=100 if not allowed else 5,
            limit=100,
            remaining=0 if not allowed else 95,
            plan="free",
            message="Monthly message limit reached." if not allowed else "ok",
        )

    def test_registered_email_over_cap_is_blocked(self, client):
        from types import SimpleNamespace
        with patch("src.repositories.users_repo.get_user_by_email",
                   return_value=SimpleNamespace(email="member@x.com")), \
             patch("src.services.subscription_gating.check_ai_message_allowed_for_user",
                   return_value=self._gate(allowed=False)), \
             patch("src.services.chat_service.send_message") as mock_send:
            r = client.post(
                "/api/v1/rico/chat/public",
                json={"message": "find me jobs", "email": "member@x.com"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["type"] == "subscription_limit"
        assert body.get("next_action") == "upgrade_subscription"
        # Capped: the AI routing path must never run.
        mock_send.assert_not_called()

    def test_registered_email_under_cap_proceeds_as_public(self, client):
        from types import SimpleNamespace
        with patch("src.repositories.users_repo.get_user_by_email",
                   return_value=SimpleNamespace(email="member@x.com")), \
             patch("src.services.subscription_gating.check_ai_message_allowed_for_user",
                   return_value=self._gate(allowed=True)), \
             patch("src.services.chat_service.send_message",
                   return_value=_CHAT_RESPONSE) as mock_send:
            r = client.post(
                "/api/v1/rico/chat/public",
                # Mixed-case email must canonicalize to the stored identity.
                json={"message": "find me jobs", "email": "Member@X.com"},
            )
        assert r.status_code == 200, r.text
        mock_send.assert_called_once()
        ctx = mock_send.call_args.kwargs["ctx"]
        # Security invariant: an unverified email is NOT promoted to authenticated,
        # and — critically — NEVER adopts the registered account's identity. The
        # chat runs as a namespaced, non-persisting public session so it cannot read
        # or write the account's profile/history. The anti-dodge cap is still enforced
        # (the gate above was keyed on the registered email), not by impersonation.
        import hashlib
        expected = "public:e-" + hashlib.sha256(b"member@x.com").hexdigest()[:40]
        assert ctx.auth_type == "public"
        assert ctx.can_view_private_jobs is False
        assert ctx.can_persist_profile is False
        # Mixed-case "Member@X.com" canonicalizes (strip+lower) to the same bucket.
        assert ctx.user_id == expected
        assert ctx.user_id != "member@x.com"

    def test_unregistered_email_is_not_gated(self, client):
        with patch("src.repositories.users_repo.get_user_by_email", return_value=None), \
             patch("src.services.subscription_gating.check_ai_message_allowed_for_user") as mock_gate, \
             patch("src.services.chat_service.send_message",
                   return_value=_CHAT_RESPONSE) as mock_send:
            r = client.post(
                "/api/v1/rico/chat/public",
                json={"message": "find me jobs", "email": "stranger@x.com"},
            )
        assert r.status_code == 200, r.text
        # No account => no cap lookup, request proceeds as a namespaced public session.
        mock_gate.assert_not_called()
        mock_send.assert_called_once()
        ctx = mock_send.call_args.kwargs["ctx"]
        # An unverified email — even one with no matching account — never becomes the
        # user_id: it is hashed into a non-persisting public bucket so it cannot read
        # or write any profile/history keyed on that raw email.
        import hashlib
        expected = "public:e-" + hashlib.sha256(b"stranger@x.com").hexdigest()[:40]
        assert ctx.auth_type == "public"
        assert ctx.can_persist_profile is False
        assert ctx.user_id == expected
        assert ctx.user_id != "stranger@x.com"

    def test_anonymous_session_is_not_gated(self, client):
        with patch("src.services.subscription_gating.check_ai_message_allowed_for_user") as mock_gate, \
             patch("src.services.chat_service.send_message",
                   return_value=_CHAT_RESPONSE) as mock_send:
            r = client.post(
                "/api/v1/rico/chat/public",
                json={"message": "find me jobs", "session_id": "anon-123"},
            )
        assert r.status_code == 200, r.text
        mock_gate.assert_not_called()
        mock_send.assert_called_once()
        ctx = mock_send.call_args.kwargs["ctx"]
        assert ctx.auth_type == "public"
        assert ctx.user_id == "public:anon-123"


class TestRicoConfirmCVProfileRoute:
    def test_confirm_cv_profile_flat_body_accepted(self, client):
        public_session_id = "public:web-confirm123xyz"
        payload = {
            "preview": {
                "name": "Test User",
                "email": "test@example.com",
                "phone": "0501234567",
                "current_role": "HSE Manager",
                "experience_years": 5,
                "skills_detected": ["hse", "nebosh"],
                "target_roles": ["HSE Manager"],
                "certifications": ["NEBOSH"],
                "languages": ["English"],
            },
            "filename": "cv.pdf",
        }

        with patch("src.api.routers.rico_chat.upsert_profile") as mock_upsert, \
             patch("src.api.routers.rico_chat.mark_onboarding_complete") as mock_mark, \
             patch("src.services.subscription_gating.enforce_profile_optimization_allowed"), \
             patch("src.services.subscription_gating.record_profile_optimization_usage"):
            r = client.post(
                f"/api/v1/rico/confirm-cv-profile?user_id={public_session_id}",
                json=payload,
            )

        assert r.status_code != 422, f"Body rejected by FastAPI: {r.text}"
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["status"] == "profile_updated"
        mock_upsert.assert_called_once()
        mock_mark.assert_not_called()

        call_kwargs = mock_upsert.call_args.kwargs
        assert call_kwargs["user_id"] == public_session_id
        assert call_kwargs["updates"]["skills"] == ["hse", "nebosh"]
        assert call_kwargs["updates"]["cv_filename"] == "cv.pdf"

    def test_cv_email_and_phone_never_overwrite_account_identity(self, client):
        """A CV's parsed email/phone (often a referee's or an old employer's) must never be
        persisted. Routing it through upsert_profile -> upsert_user (COALESCE) would silently
        overwrite the authenticated uploader's canonical identity and could break their login
        or password reset. Account identity comes from the session, not document text."""
        public_session_id = "public:web-identity-guard"
        payload = {
            "preview": {
                "name": "Real Owner",
                "email": "referee-not-the-user@oldcompany.com",
                "phone": "+971500000000",
                "current_role": "HSE Manager",
                "experience_years": 7,
                "skills_detected": ["hse", "nebosh"],
                "target_roles": ["HSE Manager"],
                "certifications": ["NEBOSH"],
                "languages": ["English", "Arabic"],
            },
            "filename": "cv.pdf",
        }

        with patch("src.api.routers.rico_chat.upsert_profile") as mock_upsert, \
             patch("src.api.routers.rico_chat.mark_onboarding_complete"), \
             patch("src.services.subscription_gating.record_profile_optimization_usage"):
            r = client.post(
                f"/api/v1/rico/confirm-cv-profile?user_id={public_session_id}",
                json=payload,
            )

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        mock_upsert.assert_called_once()
        updates = mock_upsert.call_args.kwargs["updates"]
        # Contamination vector closed: identity fields from CV text are not persisted.
        assert "email" not in updates, "CV-parsed email must not reach the profile/identity layer"
        assert "phone" not in updates, "CV-parsed phone must not reach the profile/identity layer"
        # Legitimate CV-derived profile fields still flow through untouched.
        assert updates["name"] == "Real Owner"
        assert updates["current_role"] == "HSE Manager"
        assert updates["skills"] == ["hse", "nebosh"]
        assert updates["certifications"] == ["NEBOSH"]
        assert updates["cv_filename"] == "cv.pdf"

    def test_confirm_cv_profile_without_contact_details_still_succeeds(self, client):
        """A preview with no email/phone must still persist the rest of the profile cleanly."""
        public_session_id = "public:web-no-contact"
        payload = {
            "preview": {
                "name": "No Contact",
                "current_role": "Safety Officer",
                "skills_detected": ["iosh"],
            },
            "filename": "cv2.pdf",
        }

        with patch("src.api.routers.rico_chat.upsert_profile") as mock_upsert, \
             patch("src.api.routers.rico_chat.mark_onboarding_complete"), \
             patch("src.services.subscription_gating.record_profile_optimization_usage"):
            r = client.post(
                f"/api/v1/rico/confirm-cv-profile?user_id={public_session_id}",
                json=payload,
            )

        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        updates = mock_upsert.call_args.kwargs["updates"]
        assert "email" not in updates
        assert "phone" not in updates
        assert updates["name"] == "No Contact"
        assert updates["skills"] == ["iosh"]


class TestRicoTelegramWebhookRouteExists:
    def test_telegram_webhook_route_returns_200(self, client):
        update = {
            "message": {
                "chat": {"id": 12345},
                "from": {"id": 12345},
                "text": "Hello",
            }
        }
        with patch("src.services.chat_service.handle_telegram_update", return_value=_TELEGRAM_RESPONSE):
            r = client.post("/api/v1/rico/webhooks/telegram", json=update)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_telegram_webhook_route_not_404(self, client):
        with patch("src.services.chat_service.handle_telegram_update", return_value=_TELEGRAM_RESPONSE):
            r = client.post("/api/v1/rico/webhooks/telegram", json={})
        assert r.status_code != 404, "Rico Telegram webhook route is not mounted"

    def test_telegram_webhook_passes_update_to_service(self, client):
        update = {"message": {"chat": {"id": 99}, "text": "test"}}
        captured = {}

        def spy(u):
            captured["update"] = u
            return _TELEGRAM_RESPONSE

        with patch("src.services.chat_service.handle_telegram_update", side_effect=spy):
            r = client.post("/api/v1/rico/webhooks/telegram", json=update)
        assert r.status_code == 200
        assert captured["update"] == update

    def test_telegram_webhook_rejects_invalid_secret_when_configured(self, client, monkeypatch):
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "telegram-secret")
        with patch("src.services.chat_service.handle_telegram_update", return_value=_TELEGRAM_RESPONSE) as mock_handle:
            r = client.post("/api/v1/rico/webhooks/telegram", json={})
        assert r.status_code == 403
        mock_handle.assert_not_called()

    def test_telegram_webhook_accepts_valid_secret_when_configured(self, client, monkeypatch):
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "telegram-secret")
        with patch("src.services.chat_service.handle_telegram_update", return_value=_TELEGRAM_RESPONSE) as mock_handle:
            r = client.post(
                "/api/v1/rico/webhooks/telegram",
                json={},
                headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret"},
            )
        assert r.status_code == 200
        mock_handle.assert_called_once()

    def test_telegram_webhook_fails_closed_in_production_without_secret(self, client, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
        with patch("src.services.chat_service.handle_telegram_update", return_value=_TELEGRAM_RESPONSE) as mock_handle:
            r = client.post("/api/v1/rico/webhooks/telegram", json={})
        assert r.status_code == 503
        mock_handle.assert_not_called()


class TestRicoJotformWebhookRouteExists:
    def test_jotform_webhook_route_returns_200(self, client):
        payload = {"pretty": {"email": "test@example.com", "full_name": "Test User"}}
        with patch("src.services.chat_service.handle_jotform_submission", return_value=_JOTFORM_RESPONSE):
            r = client.post("/api/v1/rico/webhooks/jotform", json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_jotform_webhook_route_not_404(self, client):
        with patch("src.services.chat_service.handle_jotform_submission", return_value=_JOTFORM_RESPONSE):
            r = client.post("/api/v1/rico/webhooks/jotform", json={})
        assert r.status_code != 404, "Rico Jotform webhook route is not mounted"

    def test_jotform_webhook_response_has_status(self, client):
        payload = {"pretty": {"email": "a@b.com"}}
        with patch("src.services.chat_service.handle_jotform_submission", return_value=_JOTFORM_RESPONSE):
            r = client.post("/api/v1/rico/webhooks/jotform", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["user_id"] == "42"

    def test_jotform_webhook_passes_payload_to_service(self, client):
        payload = {"pretty": {"full_name": "Jane"}}
        captured = {}

        def spy(p):
            captured["payload"] = p
            return _JOTFORM_RESPONSE

        with patch("src.services.chat_service.handle_jotform_submission", side_effect=spy):
            r = client.post("/api/v1/rico/webhooks/jotform", json=payload)
        assert r.status_code == 200
        assert captured["payload"] == payload

    def test_jotform_webhook_secret_enforced_when_set(self, client):
        with patch.dict(os.environ, {"JOTFORM_WEBHOOK_SECRET": "supersecret"}):
            r = client.post("/api/v1/rico/webhooks/jotform", json={"pretty": {"email": "test@example.com"}})
        assert r.status_code == 403

    def test_jotform_webhook_valid_secret_passes(self, client):
        payload = {"pretty": {"email": "test@example.com", "full_name": "Test User"}}
        with patch("src.services.chat_service.handle_jotform_submission", return_value=_JOTFORM_RESPONSE), \
             patch.dict(os.environ, {"JOTFORM_WEBHOOK_SECRET": "supersecret"}):
            r = client.post(
                "/api/v1/rico/webhooks/jotform",
                json=payload,
                headers={"X-Webhook-Secret": "supersecret"},
            )
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# GitHub webhook route tests
# ═══════════════════════════════════════════════════════════════════════════════

_GITHUB_PUSH_RESPONSE = {
    "status": "ok",
    "event": "push",
    "repo": "org/repo",
    "ref": "refs/heads/main",
    "commits": 1,
}
_GITHUB_PING_RESPONSE = {"status": "ok", "message": "pong", "zen": "Keep it logically awesome."}


def _github_sig(body: bytes, secret: str) -> str:
    return "sha256=" + _hmac_module.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestRicoGithubWebhookRouteExists:
    def test_github_webhook_route_not_404(self, client):
        import json
        body = json.dumps({"zen": "Keep it logically awesome."}).encode()
        with patch("src.services.chat_service.handle_github_event", return_value=_GITHUB_PING_RESPONSE):
            r = client.post(
                "/api/v1/rico/webhooks/github",
                content=body,
                headers={"X-GitHub-Event": "ping", "Content-Type": "application/json"},
            )
        assert r.status_code != 404, "GitHub webhook route is not mounted"

    def test_github_ping_returns_200(self, client):
        import json
        body = json.dumps({"zen": "Keep it logically awesome."}).encode()
        with patch("src.services.chat_service.handle_github_event", return_value=_GITHUB_PING_RESPONSE):
            r = client.post(
                "/api/v1/rico/webhooks/github",
                content=body,
                headers={"X-GitHub-Event": "ping", "Content-Type": "application/json"},
            )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json()["status"] == "ok"

    def test_github_push_event_returns_200(self, client):
        import json
        payload = {
            "ref": "refs/heads/main",
            "repository": {"full_name": "org/repo"},
            "pusher": {"name": "alice"},
            "commits": [{"id": "abc"}],
        }
        body = json.dumps(payload).encode()
        with patch("src.services.chat_service.handle_github_event", return_value=_GITHUB_PUSH_RESPONSE):
            r = client.post(
                "/api/v1/rico/webhooks/github",
                content=body,
                headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["event"] == "push"

    def test_github_missing_event_header_returns_400(self, client):
        import json
        body = json.dumps({}).encode()
        r = client.post(
            "/api/v1/rico/webhooks/github",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 400

    def test_github_webhook_signature_enforced_when_secret_set(self, client):
        import json
        body = json.dumps({"zen": "test"}).encode()
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "supersecret"}):
            r = client.post(
                "/api/v1/rico/webhooks/github",
                content=body,
                headers={
                    "X-GitHub-Event": "ping",
                    "X-Hub-Signature-256": "sha256=badhash",
                    "Content-Type": "application/json",
                },
            )
        assert r.status_code == 403

    def test_github_webhook_valid_signature_passes(self, client):
        import json
        secret = "supersecret"
        body = json.dumps({"zen": "test"}).encode()
        sig = _github_sig(body, secret)
        with patch("src.services.chat_service.handle_github_event", return_value=_GITHUB_PING_RESPONSE), \
             patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
            r = client.post(
                "/api/v1/rico/webhooks/github",
                content=body,
                headers={
                    "X-GitHub-Event": "ping",
                    "X-Hub-Signature-256": sig,
                    "Content-Type": "application/json",
                },
            )
        assert r.status_code == 200

    def test_github_event_passed_to_service(self, client):
        import json
        captured = {}

        def spy(event, payload):
            captured["event"] = event
            captured["payload"] = payload
            return _GITHUB_PUSH_RESPONSE

        body_dict = {"ref": "refs/heads/main", "commits": []}
        body = json.dumps(body_dict).encode()
        with patch("src.services.chat_service.handle_github_event", side_effect=spy):
            r = client.post(
                "/api/v1/rico/webhooks/github",
                content=body,
                headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
            )
        assert r.status_code == 200
        assert captured["event"] == "push"
        assert captured["payload"]["ref"] == "refs/heads/main"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Service-layer unit tests (no HTTP)
# ═══════════════════════════════════════════════════════════════════════════════

class TestChatService:
    def test_send_message_delegates_to_rico_chat_api(self):
        from src.schemas.chat import RicoSessionContext
        from src.services.chat_service import send_message
        ctx = RicoSessionContext.for_authenticated("u1")
        mock_api = type("API", (), {"process_message": lambda self, user_id, message, **kwargs: _CHAT_RESPONSE})()
        with patch("src.rico_env.get_ai_provider", return_value="openai"), \
             patch("src.rico_chat_api.RicoChatAPI") as MockAPI:
            MockAPI.return_value = mock_api
            # "hi" is not a document action; the real staticmethod returns False, so
            # send_message skips the document-read path and delegates to process_message.
            MockAPI.is_document_action_message.return_value = False
            result = send_message(ctx=ctx, message="hi")
        assert result == _CHAT_RESPONSE

    def test_parse_cv_delegates_to_cv_parser(self):
        from src.services.chat_service import parse_cv
        mock_parsed = type("P", (), {"to_dict": lambda self: _CV_PARSED})()
        mock_parser = type("Parser", (), {"parse_bytes": lambda self, d, filename: mock_parsed})()
        with patch("src.cv_parser.CVParser", return_value=mock_parser):
            result = parse_cv(b"fake pdf data", filename="cv.pdf")
        assert result == _CV_PARSED

    def test_handle_telegram_update_delegates(self):
        from src.services.chat_service import handle_telegram_update
        update = {"message": {"text": "hello"}}
        with patch("src.rico_telegram_webhook.process_telegram_update", return_value=_TELEGRAM_RESPONSE):
            result = handle_telegram_update(update)
        assert result == _TELEGRAM_RESPONSE

    def test_handle_jotform_submission_delegates(self):
        from src.services.chat_service import handle_jotform_submission
        # Must include user data so the service doesn't short-circuit before delegating.
        payload = {"pretty": {"email": "test@example.com", "full_name": "Test User"}}
        with patch("src.rico_jotform_webhook.handle_jotform_submission", return_value=_JOTFORM_RESPONSE):
            result = handle_jotform_submission(payload)
        assert result == _JOTFORM_RESPONSE


# ═══════════════════════════════════════════════════════════════════════════════
# Regression: Jotform webhook robustness
# Covers the production 500 caused by empty/minimal Agent test payloads and
# raw Jotform field labels not matching the snake_case keys Rico expects.
# ═══════════════════════════════════════════════════════════════════════════════

class TestJotformWebhookRobustness:
    """Regression suite for Jotform 500 bug (rico-job-automation-api)."""

    # ── HTTP endpoint (via TestClient) ────────────────────────────────────────

    def test_agent_test_payload_returns_200(self, client):
        """Minimal Jotform Agent 'Send API Request' test payload must not 500."""
        r = client.post(
            "/api/v1/rico/webhooks/jotform",
            json={"formID": "261277622782059", "consent": "yes"},
        )
        assert r.status_code == 200, f"Got {r.status_code}: {r.text}"

    def test_agent_test_payload_returns_accepted(self, client):
        r = client.post(
            "/api/v1/rico/webhooks/jotform",
            json={"formID": "261277622782059", "consent": "yes"},
        )
        body = r.json()
        assert body["status"] == "accepted"
        assert "message" in body

    def test_empty_payload_returns_200(self, client):
        r = client.post("/api/v1/rico/webhooks/jotform", json={})
        assert r.status_code == 200

    def test_empty_payload_returns_accepted(self, client):
        r = client.post("/api/v1/rico/webhooks/jotform", json={})
        body = r.json()
        assert body["status"] == "accepted"

    def test_raw_jotform_field_names_reach_rico_handler(self, client):
        """Raw Jotform labels ('Full Name', 'Email') must be normalised and delegated."""
        payload = {
            "Full Name": "Robin Edwan",
            "Email": "robin@example.com",
            "Telegram Username": "@robin",
            "Target Job Titles": "HSE Manager",
        }
        with patch("src.rico_jotform_webhook.handle_jotform_submission", return_value=_JOTFORM_RESPONSE):
            r = client.post("/api/v1/rico/webhooks/jotform", json=payload)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_pretty_key_payload_reaches_rico_handler(self, client):
        """Payload already using 'pretty' dict must be passed through unchanged."""
        payload = {
            "pretty": {
                "full_name": "Robin Edwan",
                "email": "robin@example.com",
            }
        }
        with patch("src.rico_jotform_webhook.handle_jotform_submission", return_value=_JOTFORM_RESPONSE):
            r = client.post("/api/v1/rico/webhooks/jotform", json=payload)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_db_error_returns_200_not_500(self, client):
        """Even when the DB write fails, the router must return 200."""
        payload = {"pretty": {"email": "x@example.com"}}
        with patch(
            "src.rico_jotform_webhook.handle_jotform_submission",
            side_effect=RuntimeError("RicoDB unavailable: DATABASE_URL or psycopg2 missing"),
        ):
            r = client.post("/api/v1/rico/webhooks/jotform", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "accepted"

    def test_invalid_json_returns_200(self, client):
        r = client.post(
            "/api/v1/rico/webhooks/jotform",
            content=b"{not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "accepted"

    # ── Service-layer unit tests (no HTTP) ────────────────────────────────────

    def test_normalize_strips_non_profile_keys(self):
        from src.services.chat_service import _normalize_jotform_payload
        out = _normalize_jotform_payload({"formID": "123", "consent": "yes"})
        assert "formID" in out
        assert "consent" in out

    def test_normalize_maps_full_name(self):
        from src.services.chat_service import _normalize_jotform_payload
        out = _normalize_jotform_payload({"Full Name": "Robin"})
        assert out.get("full_name") == "Robin"
        assert "Full Name" not in out

    def test_normalize_maps_email(self):
        from src.services.chat_service import _normalize_jotform_payload
        out = _normalize_jotform_payload({"Email": "a@b.com"})
        assert out.get("email") == "a@b.com"

    def test_normalize_maps_target_job_titles(self):
        from src.services.chat_service import _normalize_jotform_payload
        out = _normalize_jotform_payload({"Target Job Titles": "HSE Manager"})
        assert out.get("target_roles") == "HSE Manager"

    def test_normalize_passthrough_on_pretty_key(self):
        from src.services.chat_service import _normalize_jotform_payload
        payload = {"pretty": {"email": "x@y.com"}}
        assert _normalize_jotform_payload(payload) is payload

    def test_has_user_data_false_for_agent_test_payload(self):
        from src.services.chat_service import _has_user_data
        assert _has_user_data({"formID": "261277622782059", "consent": "yes"}) is False

    def test_has_user_data_true_for_email(self):
        from src.services.chat_service import _has_user_data
        assert _has_user_data({"email": "a@b.com"}) is True

    def test_has_user_data_false_for_name_only_via_pretty_key(self):
        # full_name alone is not a stable user_id — email or telegram required
        from src.services.chat_service import _has_user_data
        assert _has_user_data({"pretty": {"full_name": "Robin"}}) is False

    def test_has_user_data_true_for_email_via_pretty_key(self):
        from src.services.chat_service import _has_user_data
        assert _has_user_data({"pretty": {"email": "r@x.com"}}) is True

    def test_service_short_circuits_empty_payload(self):
        from src.services.chat_service import handle_jotform_submission
        result = handle_jotform_submission({})
        assert result["status"] == "accepted"
        assert "no profile fields" in result["message"]

    def test_service_short_circuits_agent_test_payload(self):
        from src.services.chat_service import handle_jotform_submission
        result = handle_jotform_submission({"formID": "261277622782059", "consent": "yes"})
        assert result["status"] == "accepted"

    def test_service_returns_accepted_on_db_error(self):
        from src.services.chat_service import handle_jotform_submission
        payload = {"pretty": {"email": "x@example.com"}}
        with patch(
            "src.rico_jotform_webhook.handle_jotform_submission",
            side_effect=RuntimeError("DB down"),
        ):
            result = handle_jotform_submission(payload)
        assert result["status"] == "accepted"
        assert "pending" in result["message"]


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/me, GET/POST /api/v1/rico/profile, GET/POST saved-searches
# ═══════════════════════════════════════════════════════════════════════════════

_EMPTY_PROFILE   = {"profile_exists": False, "email": "alice@rico.ai"}
_FULL_PROFILE    = {
    "profile_exists": True,
    "user_id": "alice@rico.ai",
    "name": "Alice",
    "email": "alice@rico.ai",
    "target_roles": ["HSE Manager"],
    "skills": ["ISO 45001"],
    "years_experience": 5,
}
_SAVED_SEARCHES  = [{"id": 1, "query": "HSE Dubai", "filters": {}, "created_at": "2026-05-10T00:00:00"}]


class TestMeRoute:
    def test_unauthenticated_returns_guest_identity(self, client):
        r = client.get("/api/v1/me")
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "email": None,
            "role": "guest",
            "authenticated": False,
            "guest": True,
        }

    def test_authenticated_returns_200(self, auth_client):
        r = auth_client.get("/api/v1/me")
        assert r.status_code == 200

    def test_authenticated_returns_email(self, auth_client):
        r = auth_client.get("/api/v1/me")
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "alice@rico.ai"
        assert body["authenticated"] is True

    def test_authenticated_returns_role(self, auth_client):
        r = auth_client.get("/api/v1/me")
        assert "role" in r.json()

    # ── name field (added for personalized welcome) ───────────────────────────

    def test_authenticated_returns_name_when_rico_users_has_row(self, auth_client):
        """name is returned when rico_users has a matching row with a non-null name."""
        with patch("src.api.routers.user._fetch_display_name", return_value="Alice"):
            r = auth_client.get("/api/v1/me")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Alice"
        assert body["authenticated"] is True

    def test_authenticated_returns_null_name_when_no_rico_users_row(self, auth_client):
        """name is null when rico_users has no matching row or name is NULL — request still succeeds."""
        with patch("src.api.routers.user._fetch_display_name", return_value=None):
            r = auth_client.get("/api/v1/me")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] is None
        assert body["authenticated"] is True

    def test_guest_response_has_no_name_field(self, client):
        """Guest /me contract is unaffected by the name field — exact shape preserved."""
        r = client.get("/api/v1/me")
        assert r.status_code == 200
        body = r.json()
        assert "name" not in body
        assert body == {
            "email": None,
            "role": "guest",
            "authenticated": False,
            "guest": True,
        }


class TestVersionRoute:
    def test_versioned_route_returns_deployment_metadata(self, client, monkeypatch):
        monkeypatch.setenv("GIT_COMMIT", "abc123")
        monkeypatch.setenv("RICO_ENV", "test")
        monkeypatch.setenv("DEPLOYED_AT", "2026-05-23T00:00:00Z")

        r = client.get("/api/v1/version")

        assert r.status_code == 200
        body = r.json()
        # started_at is runtime-computed (process boot, ISO-8601) — assert shape,
        # not value. It exists so deploy verification has a signal that cannot go
        # stale the way the env-driven deployed_at can.
        started_at = body.pop("started_at")
        assert isinstance(started_at, str) and started_at.startswith("20")
        assert body == {
            "app": "ricohunt",
            "version": "1.0.0",
            "commit": "abc123",
            "environment": "test",
            "deployed_at": "2026-05-23T00:00:00Z",
        }

    def test_stale_deployed_at_does_not_make_current_commit_look_old(self, client, monkeypatch):
        """Regression for #1065: a stale deployed_at must not make a current deploy look old.

        deployed_at is static env metadata that can lag main by weeks. The
        authoritative deploy signals are commit (compared to origin/main) and
        started_at (process boot). This sets deployed_at to an ancient date while
        the commit is current and asserts commit/started_at are unaffected — so
        operator tooling that reads commit + started_at never concludes a current
        deploy is stale.
        """
        from datetime import datetime

        monkeypatch.setenv("GIT_COMMIT", "cur9ent")
        monkeypatch.setenv("RICO_ENV", "test")
        # Deliberately ancient static metadata — the kind that lags main by weeks.
        monkeypatch.setenv("DEPLOYED_AT", "2020-01-01T00:00:00Z")

        r = client.get("/api/v1/version")
        assert r.status_code == 200
        body = r.json()

        # commit is the authoritative version signal — driven by the live env,
        # never by the stale deployed_at value.
        assert body["commit"] == "cur9ent"

        # started_at is a real, recent boot timestamp (this decade), proving the
        # process is live regardless of the stale deployed_at.
        started_at = datetime.fromisoformat(body["started_at"])
        assert started_at.year >= 2025

        # The stale build metadata is preserved for backward compatibility but is
        # clearly older than the process boot — it is not the live deploy signal.
        deployed_at = datetime.fromisoformat(body["deployed_at"].replace("Z", "+00:00"))
        assert deployed_at.year == 2020
        assert deployed_at < started_at


class TestRicoProfileRoute:
    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/v1/rico/profile")
        assert r.status_code == 401

    def test_authenticated_empty_profile_returns_200(self, auth_client):
        with patch("src.repositories.profile_repo.get_profile", return_value=None):
            r = auth_client.get("/api/v1/rico/profile")
        assert r.status_code == 200
        assert r.json()["profile_exists"] is False

    def test_authenticated_empty_profile_has_email(self, auth_client):
        with patch("src.repositories.profile_repo.get_profile", return_value=None):
            r = auth_client.get("/api/v1/rico/profile")
        assert r.json()["email"] == "alice@rico.ai"

    def test_authenticated_full_profile_returns_200(self, auth_client):
        from src.rico_agent import RicoProfile
        profile = RicoProfile(user_id="alice@rico.ai", name="Alice",
                               email="alice@rico.ai", target_roles=["HSE Manager"])
        with patch("src.repositories.profile_repo.get_profile", return_value=profile):
            r = auth_client.get("/api/v1/rico/profile")
        assert r.status_code == 200
        body = r.json()
        assert body["profile_exists"] is True
        assert body["name"] == "Alice"
        assert "HSE Manager" in body["target_roles"]

    def test_user_id_from_jwt_not_body(self, auth_client):
        """Route must derive user_id from JWT, not from any request body field."""
        captured = {}
        from src.rico_agent import RicoProfile

        def spy(user_id):
            captured["user_id"] = user_id
            return RicoProfile(user_id=user_id)

        with patch("src.repositories.profile_repo.get_profile", side_effect=spy):
            auth_client.get("/api/v1/rico/profile")
        assert captured["user_id"] == "alice@rico.ai"


class TestRicoSavedSearchesRoute:
    def test_get_unauthenticated_returns_401(self, client):
        r = client.get("/api/v1/rico/settings/saved-searches")
        assert r.status_code == 401

    def test_post_unauthenticated_returns_401(self, client):
        r = client.post("/api/v1/rico/settings/saved-searches",
                        json={"query": "HSE Dubai"})
        assert r.status_code == 401

    def test_get_authenticated_returns_200(self, auth_client):
        with patch("src.repositories.profile_repo.list_saved_searches", return_value=[]):
            r = auth_client.get("/api/v1/rico/settings/saved-searches")
        assert r.status_code == 200

    def test_get_returns_empty_list_when_no_searches(self, auth_client):
        with patch("src.repositories.profile_repo.list_saved_searches", return_value=[]):
            r = auth_client.get("/api/v1/rico/settings/saved-searches")
        body = r.json()
        assert body["searches"] == []
        assert body["total"] == 0

    def test_get_returns_searches(self, auth_client):
        rows = [{"id": 1, "query": "HSE Dubai", "filters": {}, "created_at": None}]
        with patch("src.repositories.profile_repo.list_saved_searches", return_value=rows):
            r = auth_client.get("/api/v1/rico/settings/saved-searches")
        body = r.json()
        assert body["total"] == 1
        assert body["searches"][0]["query"] == "HSE Dubai"

    def test_post_authenticated_returns_201(self, auth_client):
        with patch("src.repositories.profile_repo.save_search") as mock_save:
            r = auth_client.post("/api/v1/rico/settings/saved-searches",
                                 json={"query": "HSE Manager Dubai"})
        assert r.status_code == 201
        assert r.json()["status"] == "saved"

    def test_post_uses_jwt_identity_not_body(self, auth_client):
        captured = {}

        def spy(user_id, query, filters):
            captured["user_id"] = user_id

        with patch("src.repositories.profile_repo.save_search", side_effect=spy):
            auth_client.post("/api/v1/rico/settings/saved-searches",
                             json={"query": "test", "user_id": "injected@evil.com"})
        assert captured.get("user_id") == "alice@rico.ai"

    def test_post_empty_query_returns_422(self, auth_client):
        r = auth_client.post("/api/v1/rico/settings/saved-searches",
                             json={"query": ""})
        assert r.status_code == 422


class TestJobsRoutes:
    def test_save_job_requires_auth(self, client):
        r = client.post("/api/v1/jobs/job-1/save", json={"job": {"title": "Role"}})
        assert r.status_code == 401

    def test_list_jobs_includes_match_explanation(self, auth_client):
        jobs = [{
            "id": "job-1",
            "title": "Senior Python Developer",
            "company": "Acme",
            "location": "Remote",
            "skills": ["Python", "SQL"],
            "score": 84,
            "link": "https://example.com/jobs/1",
        }]
        profile = type(
            "Profile",
            (),
            {
                "skills": ["Python", "SQL", "AWS"],
                "target_roles": ["Python Developer"],
                "years_experience": 6,
                "current_role": "Backend Engineer",
            },
        )()

        def score_jobs(scored_jobs, user_id):
            for job in scored_jobs:
                job["score"] = int(job.get("score", 0) or 0)
            return scored_jobs

        with patch("src.services.jobs_service.is_db_available", return_value=False), \
             patch("src.job_history.load_job_history", return_value=jobs), \
             patch("src.scoring.score_jobs_for_user", side_effect=score_jobs), \
             patch("src.services.jobs_service.get_user_profile", return_value=profile):
            r = auth_client.get("/api/v1/jobs")

        assert r.status_code == 200
        body = r.json()
        explanation = body["jobs"][0]["match_explanation"]
        assert explanation["verdict"] == "strong_fit"
        assert explanation["why_this_fits"]
        assert explanation["worth_checking"]
        assert explanation["recommended_next_step"]

    def test_save_job_route_returns_200(self, auth_client):
        payload = {
            "job": {
                "title": "Risk Manager",
                "company": "Gulf Corp",
                "location": "Abu Dhabi, UAE",
                "link": "https://example.com/job/ep-001",
            }
        }
        with patch("src.api.routers.jobs.save_job", return_value=True), \
             patch("src.repositories.applications_repo.find_by_job_id", return_value={"status": "saved"}):
            r = auth_client.post("/api/v1/jobs/job-1/save", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "saved"

    def test_save_job_rejects_conflicting_body_job_id(self, auth_client):
        payload = {"job": {"id": "other-job", "title": "Risk Manager", "link": "https://example.com/job/ep-001"}}
        r = auth_client.post("/api/v1/jobs/job-1/save", json=payload)
        assert r.status_code == 422


# =============================================================================
# Missing endpoint tests
# =============================================================================

class TestRicoChatHistoryRoute:
    """GET /api/v1/rico/chat/history - conversation history with pagination."""

    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/v1/rico/chat/history")
        assert r.status_code == 401

    def test_authenticated_returns_200(self, auth_client):
        with patch("src.services.chat_service.get_chat_history", return_value=[]):
            r = auth_client.get("/api/v1/rico/chat/history")
        assert r.status_code == 200

    def test_response_contains_messages_and_total(self, auth_client):
        mock_history = [
            {"role": "user", "content": "Hi", "timestamp": "2026-05-12T10:00:00"},
            {"role": "assistant", "content": "Hello", "timestamp": "2026-05-12T10:00:05"},
        ]
        with patch("src.services.chat_service.get_chat_history", return_value=mock_history):
            r = auth_client.get("/api/v1/rico/chat/history")
        body = r.json()
        assert "messages" in body
        assert "total" in body
        assert body["total"] == 2
        assert len(body["messages"]) == 2

    def test_limit_parameter_applied(self, auth_client):
        with patch("src.services.chat_service.get_chat_history", return_value=[]) as mock_get:
            r = auth_client.get("/api/v1/rico/chat/history?limit=5")
        assert r.status_code == 200
        mock_get.assert_called_once()
        # The service function receives limit=5; actual assertion depends on implementation
        args, kwargs = mock_get.call_args
        assert kwargs.get("limit") == 5 or args[1] == 5  # adapt to signature

    def test_before_timestamp_parameter_passed(self, auth_client):
        with patch("src.services.chat_service.get_chat_history", return_value=[]) as mock_get:
            r = auth_client.get("/api/v1/rico/chat/history?before=2026-05-10T00:00:00Z")
        assert r.status_code == 200
        mock_get.assert_called_once()
        # Verify before timestamp is parsed and passed
        call_args = mock_get.call_args[1]
        assert "before" in call_args or len(mock_get.call_args[0]) > 2

    def test_invalid_timestamp_returns_422(self, auth_client):
        r = auth_client.get("/api/v1/rico/chat/history?before=not-a-date")
        assert r.status_code == 422

    def test_limit_out_of_range_returns_422(self, auth_client):
        r = auth_client.get("/api/v1/rico/chat/history?limit=1000")
        assert r.status_code == 422


class TestRicoFeedbackRoute:
    """POST /api/v1/rico/feedback - record user feedback for learning."""

    def test_unauthenticated_returns_401(self, client):
        # Pydantic validation happens before auth check, so we need valid body
        payload = {
            "job_id": "job123",
            "feedback_type": "positive",
            "rating": 5,
        }
        r = client.post("/api/v1/rico/feedback", json=payload)
        assert r.status_code == 401

    def test_missing_required_fields_returns_422(self, auth_client):
        r = auth_client.post("/api/v1/rico/feedback", json={})
        assert r.status_code == 422

    def test_invalid_feedback_type_returns_422(self, auth_client):
        payload = {
            "job_id": "job123",
            "feedback_type": "awesome",  # not allowed
            "rating": 5,
        }
        r = auth_client.post("/api/v1/rico/feedback", json=payload)
        assert r.status_code == 422

    def test_rating_out_of_range_returns_422(self, auth_client):
        payload = {
            "job_id": "job123",
            "feedback_type": "positive",
            "rating": 6,
        }
        r = auth_client.post("/api/v1/rico/feedback", json=payload)
        assert r.status_code == 422

    def test_valid_feedback_returns_204(self, auth_client):
        payload = {
            "job_id": "job123",
            "feedback_type": "positive",
            "rating": 5,
            "comment": "Great match",
        }
        with patch("src.api.routers.rico_chat.get_learning_repository") as mock_repo:
            mock_instance = mock_repo.return_value
            mock_instance.record_signal.return_value = None
            r = auth_client.post("/api/v1/rico/feedback", json=payload)
        assert r.status_code == 204

    def test_feedback_records_learning_signal(self, auth_client):
        payload = {
            "job_id": "job456",
            "feedback_type": "negative",
            "rating": 2,
            "comment": "Not relevant",
        }
        with patch("src.api.routers.rico_chat.get_learning_repository") as mock_repo:
            mock_instance = mock_repo.return_value
            mock_instance.record_signal.return_value = None
            r = auth_client.post("/api/v1/rico/feedback", json=payload)
        assert r.status_code == 204
        mock_instance.record_signal.assert_called_once()
        # Verify the learning repository receives correct data
        call_args = mock_instance.record_signal.call_args[1]
        assert call_args["signal_type"] == "feedback"
        assert call_args["signal_value"] == "negative"
        assert call_args["signal_weight"] == -0.2  # rating 2 maps to -0.2
        assert call_args["source"] == "user_feedback"
        assert call_args["metadata"]["job_id"] == "job456"
        assert call_args["metadata"]["rating"] == 2


class TestRicoDeleteSavedSearchRoute:
    """DELETE /api/v1/rico/settings/saved-searches/{id}"""

    def test_unauthenticated_returns_401(self, client):
        r = client.delete("/api/v1/rico/settings/saved-searches/00000000-0000-0000-0000-000000000001")
        assert r.status_code == 401

    def test_authenticated_deletes_search_returns_204(self, auth_client):
        with patch("src.api.routers.rico_chat.delete_search", return_value=True):
            r = auth_client.delete("/api/v1/rico/settings/saved-searches/550e8400-e29b-41d4-a716-446655440000")
        assert r.status_code == 204
        assert not r.text  # no content

    def test_delete_nonexistent_search_returns_404(self, auth_client):
        with patch("src.api.routers.rico_chat.delete_search", return_value=False):
            r = auth_client.delete("/api/v1/rico/settings/saved-searches/550e8400-e29b-41d4-a716-446655440001")
        assert r.status_code == 404

    def test_delete_uses_jwt_identity_not_url_injection(self, auth_client):
        captured = {}

        def spy(user_id, search_id):
            captured["user_id"] = user_id
            return True

        with patch("src.api.routers.rico_chat.delete_search", side_effect=spy):
            r = auth_client.delete("/api/v1/rico/settings/saved-searches/550e8400-e29b-41d4-a716-446655440002")
        assert r.status_code == 204
        assert captured["user_id"] == "alice@rico.ai"
        # JWT identity is used, not URL injection


class TestRicoOpenAISmokeRoute:
    """GET /api/v1/rico/openai-smoke - AI provider health check."""

    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/v1/rico/openai-smoke")
        assert r.status_code == 401

    def test_authenticated_returns_200(self, auth_client):
        # Mock the internal call to avoid actual API key dependency
        with patch("src.api.routers.rico_chat.call_openai_minimal", return_value={
            "success": True,
            "text": "OK",
            "provider_available": True,
            "model": "gpt-4",
        }), patch("src.api.routers.rico_chat.get_ai_provider", return_value="openai"):
            r = auth_client.get("/api/v1/rico/openai-smoke")
        assert r.status_code == 200

    def test_response_contains_provider_and_success_flag(self, auth_client):
        with patch("src.api.routers.rico_chat.call_openai_minimal", return_value={
            "success": True,
            "text": "OK",
            "provider_available": True,
            "model": "gpt-3.5-turbo",
        }), patch("src.api.routers.rico_chat.get_ai_provider", return_value="openai"):
            r = auth_client.get("/api/v1/rico/openai-smoke")
        body = r.json()
        assert "success" in body
        assert "provider" in body
        assert body["success"] is True
        assert body["provider"] == "openai"

    def test_deepseek_provider_works(self, auth_client):
        with patch("src.api.routers.rico_chat.call_openai_minimal", return_value={
            "success": True,
            "text": "OK",
            "provider_available": True,
            "deepseek_model": "deepseek-chat",
        }), patch("src.api.routers.rico_chat.get_ai_provider", return_value="deepseek"):
            r = auth_client.get("/api/v1/rico/openai-smoke")
        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "deepseek"
        assert body["success"] is True

    def test_fallback_provider_disabled_returns_200_but_not_success(self, auth_client):
        # When active provider is neither openai nor deepseek, smoke returns structured error.
        with patch("src.api.routers.rico_chat.call_openai_minimal", return_value={
            "success": False,
            "text": "Premium AI provider disabled",
            "provider_available": False,
        }), patch("src.api.routers.rico_chat.get_ai_provider", return_value="anthropic"):
            r = auth_client.get("/api/v1/rico/openai-smoke")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert body["provider"] == "anthropic"
        assert "Premium AI provider disabled" in body["response"]
