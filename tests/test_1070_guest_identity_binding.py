"""Guest identity binding (#1070) — locked design.

The BACKEND mints the authoritative guest SID and binds it to the browser via
a versioned, signed, HttpOnly capability cookie (`rico_guest_proof`). The
client's localStorage id is correlation-only and carries zero authorization
meaning. Validation enforces every signed field (version, purpose, sid,
issued_at, expiry, nonce) from the payload itself. GUEST_CAPABILITY_SECRET is
a dedicated key (never derived from JWT_SECRET) and its absence in production
fails closed. Failure modes are distinct and observable — no blanket
rotate-and-retry.

All DB access is mocked — no real database, no live provider calls.
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.public_identity import (
    GUEST_CAPABILITY_PURPOSE,
    GUEST_CAPABILITY_VERSION,
    GUEST_PROOF_COOKIE,
    GuestCapabilityUnavailable,
    InvalidGuestCapability,
    _b64url_encode,
    _sign,
    make_guest_capability_for_sid,
    mint_guest_capability,
    parse_guest_capability,
)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from src.api.rate_limit import limiter

    limiter.reset()
    yield


def _forge_token(**overrides) -> str:
    """Build a signed token with arbitrary payload fields (test-only)."""
    now = int(time.time())
    payload = {
        "v": GUEST_CAPABILITY_VERSION,
        "purpose": GUEST_CAPABILITY_PURPOSE,
        "sid": "g-forged-sid-123",
        "iat": now,
        "exp": now + 3600,
        "nonce": "test-nonce",
    }
    payload.update(overrides)
    payload = {k: v for k, v in payload.items() if v is not None}
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"


# ─────────────────────────────────────────────────────────────────────────────
# Token primitives — every field enforced from the SIGNED payload
# ─────────────────────────────────────────────────────────────────────────────

class TestCapabilityToken:
    def test_mint_parse_roundtrip(self):
        sid, token = mint_guest_capability()
        assert parse_guest_capability(token) == sid
        assert sid.startswith("g-") and 8 <= len(sid) <= 64

    def test_expiry_enforced_from_signed_payload(self):
        """A VALIDLY SIGNED but expired token is rejected — expiry lives in the
        payload, not only in the cookie's Max-Age."""
        now = int(time.time())
        token = _forge_token(iat=now - 7200, exp=now - 3600)
        with pytest.raises(InvalidGuestCapability, match="expired"):
            parse_guest_capability(token)

    def test_wrong_purpose_rejected(self):
        with pytest.raises(InvalidGuestCapability, match="purpose"):
            parse_guest_capability(_forge_token(purpose="password-reset"))

    def test_wrong_version_rejected(self):
        with pytest.raises(InvalidGuestCapability, match="version"):
            parse_guest_capability(_forge_token(v=99))

    def test_missing_nonce_rejected(self):
        with pytest.raises(InvalidGuestCapability, match="nonce"):
            parse_guest_capability(_forge_token(nonce=None))

    def test_nonce_differs_between_capabilities(self):
        t1 = make_guest_capability_for_sid("g-same-sid-123")
        t2 = make_guest_capability_for_sid("g-same-sid-123")
        p1 = json.loads(__import__("base64").urlsafe_b64decode(t1.split(".")[0] + "=="))
        p2 = json.loads(__import__("base64").urlsafe_b64decode(t2.split(".")[0] + "=="))
        assert p1["nonce"] != p2["nonce"]
        assert t1 != t2

    def test_tampered_signature_rejected(self):
        _, token = mint_guest_capability()
        payload, _, sig = token.partition(".")
        bad = payload + "." + ("0" if sig[0] != "0" else "1") + sig[1:]
        with pytest.raises(InvalidGuestCapability, match="signature"):
            parse_guest_capability(bad)

    def test_tampered_payload_rejected(self):
        """Editing the payload (e.g. swapping the sid) breaks the signature."""
        _, token = mint_guest_capability()
        payload_b64, _, sig = token.partition(".")
        other = _forge_token(sid="g-attacker-sid-1").partition(".")[0]
        with pytest.raises(InvalidGuestCapability):
            parse_guest_capability(f"{other}.{sig}")

    def test_malformed_tokens_rejected(self):
        for bad in (None, "", "no-dot", "a.b", "!!!.???"):
            with pytest.raises(InvalidGuestCapability):
                parse_guest_capability(bad)


class TestKeySeparation:
    def test_missing_production_secret_fails_closed(self, monkeypatch):
        """No GUEST_CAPABILITY_SECRET in production → nothing minted or
        validated; NO fallback to JWT_SECRET."""
        monkeypatch.delenv("GUEST_CAPABILITY_SECRET", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET", "x" * 64)  # present — must NOT be used
        with pytest.raises(GuestCapabilityUnavailable):
            mint_guest_capability()
        with pytest.raises(GuestCapabilityUnavailable):
            parse_guest_capability("aaaaaaaa.bbbbbbbb")

    def test_dedicated_secret_changes_signatures(self, monkeypatch):
        """Tokens signed under one GUEST_CAPABILITY_SECRET fail under another —
        and JWT_SECRET plays no part."""
        monkeypatch.setenv("GUEST_CAPABILITY_SECRET", "secret-A" * 8)
        _, token = mint_guest_capability()
        assert parse_guest_capability(token)
        monkeypatch.setenv("GUEST_CAPABILITY_SECRET", "secret-B" * 8)
        with pytest.raises(InvalidGuestCapability):
            parse_guest_capability(token)
        # JWT_SECRET rotation must NOT invalidate guest capabilities.
        monkeypatch.setenv("GUEST_CAPABILITY_SECRET", "secret-A" * 8)
        monkeypatch.setenv("JWT_SECRET", "rotated" * 10)
        assert parse_guest_capability(token)


# ─────────────────────────────────────────────────────────────────────────────
# Server authority on the public surfaces
# ─────────────────────────────────────────────────────────────────────────────

def _mock_chat(mock_chat):
    mock_chat.send_message.return_value = {"message": "hi", "type": "conversational"}
    mock_chat.run_chat_preflight.return_value = MagicMock(terminal=None)


class TestPublicChatServerAuthority:
    def test_client_selected_sid_never_becomes_identity(self):
        """A cookie-less request claiming an arbitrary sid gets a SERVER-minted
        identity — the claimed value is correlation-only."""
        client = TestClient(app)
        captured = {}

        def spy_for_public(sid):
            captured["sid"] = sid
            ctx = MagicMock()
            ctx.user_id = f"public:{sid}"
            return ctx

        with patch("src.api.routers.rico_chat.chat_service") as mock_chat, patch(
            "src.api.routers.rico_chat.RicoSessionContext"
        ) as mock_ctx_cls:
            _mock_chat(mock_chat)
            mock_ctx_cls.for_public.side_effect = spy_for_public
            r = client.post(
                "/api/v1/rico/chat/public",
                json={"message": "hello", "session_id": "web-attacker00001"},
            )
        assert r.status_code == 200
        assert captured["sid"] != "web-attacker00001"
        assert captured["sid"].startswith("g-")
        # The authoritative sid is NEVER disclosed to JavaScript — no header
        # or body field carries it; it exists only inside the HttpOnly cookie.
        assert "X-Guest-Sid" not in r.headers
        assert captured["sid"] not in r.text
        assert parse_guest_capability(client.cookies.get(GUEST_PROOF_COOKIE)) == captured["sid"]
        # Exactly ONE capability cookie is emitted.
        set_cookies = [v for k, v in r.headers.multi_items() if k.lower() == "set-cookie"]
        assert sum(GUEST_PROOF_COOKIE in c for c in set_cookies) == 1

    def test_valid_cookie_is_the_identity_across_requests(self):
        client = TestClient(app)
        sid = "g-continuity-123"
        client.cookies.set(GUEST_PROOF_COOKIE, make_guest_capability_for_sid(sid))
        captured = {}

        def spy_for_public(resolved):
            captured["sid"] = resolved
            ctx = MagicMock()
            ctx.user_id = f"public:{resolved}"
            return ctx

        with patch("src.api.routers.rico_chat.chat_service") as mock_chat, patch(
            "src.api.routers.rico_chat.RicoSessionContext"
        ) as mock_ctx_cls:
            _mock_chat(mock_chat)
            mock_ctx_cls.for_public.side_effect = spy_for_public
            r = client.post(
                "/api/v1/rico/chat/public",
                json={"message": "hello", "session_id": "web-whatever12345"},
            )
        assert r.status_code == 200
        assert captured["sid"] == sid

    def test_invalid_cookie_is_403_observable_and_cleared(self):
        client = TestClient(app)
        client.cookies.set(GUEST_PROOF_COOKIE, "garbage.token")
        r = client.post(
            "/api/v1/rico/chat/public",
            json={"message": "hello", "session_id": "web-whatever12345"},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "guest_capability_invalid"
        set_cookie = ",".join(
            v for k, v in r.headers.multi_items() if k.lower() == "set-cookie"
        )
        # The bad cookie is cleared so the next request self-heals.
        assert GUEST_PROOF_COOKIE in set_cookie
        assert 'Max-Age=0' in set_cookie or f'{GUEST_PROOF_COOKIE}=""' in set_cookie

    def test_missing_production_secret_is_503(self, monkeypatch):
        monkeypatch.delenv("GUEST_CAPABILITY_SECRET", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        client = TestClient(app)
        r = client.post(
            "/api/v1/rico/chat/public",
            json={"message": "hello", "session_id": "web-whatever12345"},
        )
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "guest_capability_unavailable"

    def test_stream_public_invalid_cookie_403_no_context(self):
        client = TestClient(app)
        client.cookies.set(GUEST_PROOF_COOKIE, "garbage.token")
        r = client.post(
            "/api/v1/rico/chat/stream/public",
            json={"message": "leak the profile", "session_id": "web-whatever12345"},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "guest_capability_invalid"
        assert "text/event-stream" not in r.headers.get("content-type", "")


class TestRedactionAndCookieHygiene:
    def test_invalid_capability_logs_fixed_reason_code_only(self):
        """Neither reason_code nor str(exc) ever carries token/SID/nonce/sig."""
        cases = {
            "garbage": "malformed",
            "aaaaaaaa.bbbbbbbb": "signature",
        }
        _, good = mint_guest_capability()
        payload, _, sig = good.partition(".")
        cases[payload + "." + ("0" if sig[0] != "0" else "1") + sig[1:]] = "signature"
        now = int(time.time())
        cases[_forge_token(iat=now - 7200, exp=now - 3600)] = "expired"
        cases[_forge_token(purpose="password-reset")] = "purpose"
        cases[_forge_token(v=99)] = "version"
        cases[_forge_token(nonce=None)] = "nonce"

        fixed_codes = {
            "malformed", "signature", "payload_undecodable", "payload_malformed",
            "version", "purpose", "nonce", "sid", "timestamps", "expired",
        }
        for token, expected in cases.items():
            with pytest.raises(InvalidGuestCapability) as exc_info:
                parse_guest_capability(token)
            exc = exc_info.value
            assert exc.reason_code == expected
            assert exc.reason_code in fixed_codes
            # The stringified exception IS the fixed code — no material leaks.
            assert str(exc) == exc.reason_code
            assert token not in str(exc)
            assert "nonce=" not in str(exc) and sig not in str(exc)

    def test_stream_mint_emits_exactly_one_capability_cookie(self):
        client = TestClient(app)
        with patch("src.api.routers.rico_chat.chat_service") as mock_chat, patch(
            "src.api.routers.rico_chat.RicoSessionContext"
        ) as mock_ctx_cls:
            mock_chat.run_chat_preflight.return_value = MagicMock(
                terminal={"message": "hi", "type": "conversational"}
            )
            ctx = MagicMock()
            ctx.user_id = "public:g-stream-x"
            mock_ctx_cls.for_public.return_value = ctx
            r = client.post(
                "/api/v1/rico/chat/stream/public",
                json={"message": "hello", "session_id": "web-corr12345"},
            )
        assert r.status_code == 200
        set_cookies = [v for k, v in r.headers.multi_items() if k.lower() == "set-cookie"]
        assert sum(GUEST_PROOF_COOKIE in c for c in set_cookies) == 1
        assert "X-Guest-Sid" not in r.headers

    def test_stream_invalid_cookie_emits_exactly_one_clearing_cookie(self):
        client = TestClient(app)
        client.cookies.set(GUEST_PROOF_COOKIE, "garbage.token")
        r = client.post(
            "/api/v1/rico/chat/stream/public",
            json={"message": "hello", "session_id": "web-corr12345"},
        )
        assert r.status_code == 403
        set_cookies = [v for k, v in r.headers.multi_items() if k.lower() == "set-cookie"]
        capability_cookies = [c for c in set_cookies if GUEST_PROOF_COOKIE in c]
        assert len(capability_cookies) == 1
        assert 'Max-Age=0' in capability_cookies[0] or f'{GUEST_PROOF_COOKIE}=""' in capability_cookies[0]

    def test_stream_identity_is_server_minted_not_claimed(self):
        """Disclosed-sid probe on the stream surface: the claimed sid never
        becomes the context identity."""
        client = TestClient(app)
        captured = {}

        def spy_for_public(sid):
            captured["sid"] = sid
            ctx = MagicMock()
            ctx.user_id = f"public:{sid}"
            return ctx

        with patch("src.api.routers.rico_chat.chat_service") as mock_chat, patch(
            "src.api.routers.rico_chat.RicoSessionContext"
        ) as mock_ctx_cls:
            mock_chat.run_chat_preflight.return_value = MagicMock(
                terminal={"message": "hi", "type": "conversational"}
            )
            mock_ctx_cls.for_public.side_effect = spy_for_public
            r = client.post(
                "/api/v1/rico/chat/stream/public",
                json={"message": "hello", "session_id": "web-victim000001"},
            )
        assert r.status_code == 200
        assert captured["sid"] != "web-victim000001"
        assert captured["sid"].startswith("g-")


class TestUploadServerAuthority:
    def test_upload_identity_is_token_sid_not_supplied_sid(self):
        from src.api.routers.rico_chat import _resolve_upload_user_id
        from fastapi import HTTPException, Response

        sid = "g-upload-owner-1"
        req = MagicMock()
        req.state.access_token_present = False
        req.cookies = {GUEST_PROOF_COOKIE: make_guest_capability_for_sid(sid)}
        req.url.path = "/api/v1/rico/upload-cv"
        with patch(
            "src.api.deps.get_current_user_id",
            side_effect=HTTPException(status_code=401),
        ):
            resolved = _resolve_upload_user_id(
                req, "public:web-attacker00001", None, Response()
            )
        assert resolved == f"public:{sid}"

    def test_cookieless_upload_gets_fresh_server_identity(self):
        from src.api.routers.rico_chat import _resolve_upload_user_id
        from fastapi import HTTPException, Response

        req = MagicMock()
        req.state.access_token_present = False
        req.cookies = {}
        req.url.path = "/api/v1/rico/upload-cv"
        resp = Response()
        with patch(
            "src.api.deps.get_current_user_id",
            side_effect=HTTPException(status_code=401),
        ):
            resolved = _resolve_upload_user_id(req, "public:web-mine12345", None, resp)
        assert resolved.startswith("public:g-")
        assert resolved != "public:web-mine12345"
        # The authoritative sid is never disclosed via headers.
        assert "X-Guest-Sid" not in resp.headers


# ─────────────────────────────────────────────────────────────────────────────
# Auth merge wiring — token passed, capability rotated on success
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthMergeWiring:
    def _login(self, client, merge_result):
        with patch(
            "src.api.auth.verify_credentials",
            return_value={"email": "user@test.com", "role": "user", "email_verified": True, "id": "u1"},
        ), patch(
            "src.services.identity_merge_service.merge_public_identity_into_auth",
            return_value=merge_result,
        ) as mock_merge:
            r = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "user@test.com",
                    "password": "x" * 12,
                    "public_user_id_to_merge": "public:g-merge-src-1",
                },
            )
        return r, mock_merge

    def test_login_passes_capability_token_to_merge(self):
        client = TestClient(app)
        token = make_guest_capability_for_sid("g-merge-src-1")
        client.cookies.set(GUEST_PROOF_COOKIE, token)
        r, mock_merge = self._login(client, merge_result=True)
        assert r.status_code == 200
        assert mock_merge.call_args.kwargs["guest_capability_token"] == token

    def test_login_without_cookie_passes_none(self):
        client = TestClient(app)
        r, mock_merge = self._login(client, merge_result=False)
        assert r.status_code == 200  # login itself still succeeds
        assert mock_merge.call_args.kwargs["guest_capability_token"] is None

    def test_successful_merge_rotates_guest_capability(self):
        client = TestClient(app)
        client.cookies.set(GUEST_PROOF_COOKIE, make_guest_capability_for_sid("g-merge-src-1"))
        r, _ = self._login(client, merge_result=True)
        set_cookie_headers = ",".join(
            v for k, v in r.headers.multi_items() if k.lower() == "set-cookie"
        )
        assert GUEST_PROOF_COOKIE in set_cookie_headers
        assert f'{GUEST_PROOF_COOKIE}=""' in set_cookie_headers or "Max-Age=0" in set_cookie_headers

    def test_failed_merge_keeps_guest_capability(self):
        client = TestClient(app)
        client.cookies.set(GUEST_PROOF_COOKIE, make_guest_capability_for_sid("g-merge-src-1"))
        r, _ = self._login(client, merge_result=False)
        set_cookie_headers = ",".join(
            v for k, v in r.headers.multi_items() if k.lower() == "set-cookie"
        )
        assert GUEST_PROOF_COOKIE not in set_cookie_headers


# ─────────────────────────────────────────────────────────────────────────────
# Upload/confirm response bodies never disclose the server identity (#1070
# hotfix). The one historical leak: upload-cv echoed resolved_user_id, which
# after #1132 became the SERVER-minted guest sid — production smoke run
# 29582449298 caught it (8a). Guests now get no identity echo at all;
# authenticated uploads keep the field for backward compatibility.
# ─────────────────────────────────────────────────────────────────────────────


def _tiny_cv_pdf() -> bytes:
    """Minimal one-page PDF with enough extractable text to pass the parse
    quality gate (>= 50 readable chars)."""
    lines = [
        "Samira Smoke",
        "Senior Operations Coordinator - Dubai, UAE",
        "PROFESSIONAL SUMMARY",
        "Operations coordinator with 6 years of experience in logistics,",
        "vendor management and process improvement across UAE facilities.",
        "EXPERIENCE",
        "Operations Coordinator, Example Logistics LLC 2019-2025:",
        "coordinated 40+ weekly shipments and owned monthly KPI reporting.",
        "SKILLS",
        "Excel, SAP, scheduling, inventory management, English, Arabic",
    ]
    parts = []
    y = 760
    for line in lines:
        parts.append(f"BT /F1 11 Tf 50 {y} Td ({line}) Tj ET")
        y -= 18
    stream = ("\n".join(parts)).encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF"
    ).encode()
    return bytes(out)


class TestUploadConfirmResponseSecrecy:
    """The server-authoritative sid must not appear in ANY guest-reachable
    upload/confirm response body, header, or echoed field."""

    def test_guest_upload_response_hides_server_identity(self):
        client = TestClient(app)
        sid = "g-upload-secret-001"
        client.cookies.set(GUEST_PROOF_COOKIE, make_guest_capability_for_sid(sid))
        r = client.post(
            "/api/v1/rico/upload-cv",
            files={"file": ("cv.pdf", _tiny_cv_pdf(), "application/pdf")},
            data={"user_id": "public:web-correlation01"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "preview_ready"
        assert sid not in r.text
        assert body.get("user_id") is None

    def test_authenticated_upload_response_keeps_user_id(self):
        client = TestClient(app)
        with patch(
            "src.api.routers.rico_chat.get_current_user_id",
            return_value="auth-user@example.com",
        ), patch("src.services.subscription_gating.enforce_document_quota"):
            r = client.post(
                "/api/v1/rico/upload-cv",
                files={"file": ("cv.pdf", _tiny_cv_pdf(), "application/pdf")},
            )
        assert r.status_code == 200
        assert r.json().get("user_id") == "auth-user@example.com"

    def test_guest_confirm_response_hides_server_identity(self):
        client = TestClient(app)
        sid = "g-confirm-secret-001"
        client.cookies.set(GUEST_PROOF_COOKIE, make_guest_capability_for_sid(sid))
        with patch(
            "src.services.subscription_gating.enforce_profile_optimization_allowed"
        ), patch(
            "src.services.subscription_gating.record_profile_optimization_usage"
        ), patch("src.repositories.profile_repo.upsert_profile"):
            r = client.post(
                "/api/v1/rico/confirm-cv-profile",
                params={"user_id": "public:web-correlation01"},
                json={
                    "preview": {"name": "Samira Smoke", "skills": ["excel"]},
                    "filename": "cv.pdf",
                },
            )
        assert r.status_code == 200
        assert r.json().get("status") == "profile_updated"
        assert sid not in r.text
