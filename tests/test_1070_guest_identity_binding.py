"""Guest identity binding (#1070).

A `public:*` session id is a client-minted string — possession of the string
alone must not read, write, confirm, or merge a guest's temporary context.
Ownership is a browser-bound, signed, HttpOnly capability cookie
(`rico_guest_proof`), endorsed on the session's FIRST use and required for
every later claim. The public→auth merge additionally consumes a one-time,
account-bound claim.

All DB access is mocked — no real database, no live provider calls.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.public_identity import (
    GUEST_NEW,
    GUEST_PROOF_COOKIE,
    GUEST_REJECTED,
    GUEST_VERIFIED,
    check_guest_capability,
    make_guest_proof,
    verify_guest_proof,
)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from src.api.rate_limit import limiter

    limiter.reset()
    yield


# ─────────────────────────────────────────────────────────────────────────────
# Proof primitives
# ─────────────────────────────────────────────────────────────────────────────

class TestProofPrimitives:
    def test_roundtrip(self):
        sid = "web-abc12345"
        assert verify_guest_proof(sid, make_guest_proof(sid)) is True

    def test_tampered_proof_fails(self):
        sid = "web-abc12345"
        proof = make_guest_proof(sid)
        bad = ("0" if proof[0] != "0" else "1") + proof[1:]
        assert verify_guest_proof(sid, bad) is False

    def test_proof_is_session_bound(self):
        assert verify_guest_proof("web-abc12345", make_guest_proof("web-other999")) is False

    def test_missing_or_unsafe_inputs_fail_closed(self):
        assert verify_guest_proof(None, None) is False
        assert verify_guest_proof("web-abc12345", None) is False
        assert verify_guest_proof("bad/sid", "anything") is False
        with pytest.raises(ValueError):
            make_guest_proof("nope")  # under 8 chars


class _FakeRequest:
    def __init__(self, cookies=None):
        self.cookies = cookies or {}


class TestCapabilityCheck:
    def test_valid_proof_is_verified(self):
        sid = "web-abc12345"
        req = _FakeRequest({GUEST_PROOF_COOKIE: make_guest_proof(sid)})
        assert check_guest_capability(req, sid) == GUEST_VERIFIED

    def test_no_state_endorses_new_browser(self):
        with patch("src.api.public_identity.guest_state_exists", return_value=False):
            assert check_guest_capability(_FakeRequest(), "web-abc12345") == GUEST_NEW

    def test_existing_state_without_proof_is_rejected(self):
        with patch("src.api.public_identity.guest_state_exists", return_value=True):
            assert check_guest_capability(_FakeRequest(), "web-abc12345") == GUEST_REJECTED

    def test_state_check_fails_closed_on_db_error(self):
        """A DB error during the existence check must reject, never endorse."""
        from src.api import public_identity as pi

        with patch.object(pi, "RicoDB", create=True):
            with patch("src.rico_memory.RicoMemoryStore") as mock_store, patch(
                "src.rico_db.RicoDB"
            ) as mock_db:
                mock_store.return_value.load_profile.return_value = None
                mock_db.side_effect = RuntimeError("db exploded")
                assert pi.guest_state_exists("public:web-abc12345") is True


# ─────────────────────────────────────────────────────────────────────────────
# Public chat endpoints — string alone must not retrieve context
# ─────────────────────────────────────────────────────────────────────────────

_SID = "web-11112222"


class TestPublicChatCapability:
    def test_unproved_claim_over_existing_session_is_403(self):
        client = TestClient(app)
        with patch("src.api.public_identity.guest_state_exists", return_value=True):
            r = client.post(
                "/api/v1/rico/chat/public",
                json={"message": "what do you know about me?", "session_id": _SID},
            )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "guest_session_unverified"

    def test_fresh_session_is_endorsed_with_cookie(self):
        client = TestClient(app)
        with patch("src.api.public_identity.guest_state_exists", return_value=False), patch(
            "src.api.routers.rico_chat.chat_service"
        ) as mock_chat:
            mock_chat.send_message.return_value = {"message": "hi", "type": "conversational"}
            mock_chat.run_chat_preflight.return_value = MagicMock(terminal=None)
            r = client.post(
                "/api/v1/rico/chat/public",
                json={"message": "hello", "session_id": _SID},
            )
        assert r.status_code == 200
        assert client.cookies.get(GUEST_PROOF_COOKIE) == make_guest_proof(_SID)

    def test_valid_proof_over_existing_session_is_allowed(self):
        client = TestClient(app)
        client.cookies.set(GUEST_PROOF_COOKIE, make_guest_proof(_SID))
        with patch("src.api.public_identity.guest_state_exists", return_value=True), patch(
            "src.api.routers.rico_chat.chat_service"
        ) as mock_chat:
            mock_chat.send_message.return_value = {"message": "hi", "type": "conversational"}
            mock_chat.run_chat_preflight.return_value = MagicMock(terminal=None)
            r = client.post(
                "/api/v1/rico/chat/public",
                json={"message": "hello again", "session_id": _SID},
            )
        assert r.status_code == 200

    def test_stream_public_unproved_claim_is_403_with_no_context(self):
        client = TestClient(app)
        with patch("src.api.public_identity.guest_state_exists", return_value=True):
            r = client.post(
                "/api/v1/rico/chat/stream/public",
                json={"message": "leak the profile", "session_id": _SID},
            )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "guest_session_unverified"
        assert "text/event-stream" not in r.headers.get("content-type", "")


# ─────────────────────────────────────────────────────────────────────────────
# Upload / confirm — same capability boundary
# ─────────────────────────────────────────────────────────────────────────────

class TestUploadCapability:
    def test_unproved_guest_upload_is_403(self):
        import io

        client = TestClient(app)
        with patch("src.api.public_identity.guest_state_exists", return_value=True):
            r = client.post(
                f"/api/v1/rico/upload-cv?user_id=public:{_SID}",
                files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
            )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "guest_session_unverified"

    def test_unproved_guest_confirm_is_403(self):
        client = TestClient(app)
        with patch("src.api.public_identity.guest_state_exists", return_value=True):
            r = client.post(
                f"/api/v1/rico/confirm-cv-profile?user_id=public:{_SID}",
                json={"preview": {"skills": ["hse"]}, "filename": "cv.pdf"},
            )
        assert r.status_code == 403

    def test_proved_guest_passes_resolver(self):
        from src.api.routers.rico_chat import _resolve_upload_user_id

        req = MagicMock()
        req.state.access_token_present = False
        req.cookies = {GUEST_PROOF_COOKIE: make_guest_proof(_SID)}
        with patch(
            "src.api.deps.get_current_user_id",
            side_effect=__import__("fastapi").HTTPException(status_code=401),
        ):
            resolved = _resolve_upload_user_id(req, f"public:{_SID}", None)
        assert resolved == f"public:{_SID}"


# ─────────────────────────────────────────────────────────────────────────────
# Auth merge wiring — proof passed, capability rotated on success
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
                    "public_user_id_to_merge": f"public:{_SID}",
                },
            )
        return r, mock_merge

    def test_login_passes_browser_proof_to_merge(self):
        client = TestClient(app)
        proof = make_guest_proof(_SID)
        client.cookies.set(GUEST_PROOF_COOKIE, proof)
        r, mock_merge = self._login(client, merge_result=True)
        assert r.status_code == 200
        assert mock_merge.call_args.kwargs["guest_proof"] == proof

    def test_login_without_cookie_passes_no_proof(self):
        client = TestClient(app)
        r, mock_merge = self._login(client, merge_result=False)
        assert r.status_code == 200  # login itself still succeeds
        assert mock_merge.call_args.kwargs["guest_proof"] is None

    def test_successful_merge_rotates_guest_capability(self):
        client = TestClient(app)
        client.cookies.set(GUEST_PROOF_COOKIE, make_guest_proof(_SID))
        r, _ = self._login(client, merge_result=True)
        set_cookie_headers = ",".join(
            v for k, v in r.headers.multi_items() if k.lower() == "set-cookie"
        )
        assert GUEST_PROOF_COOKIE in set_cookie_headers
        assert f'{GUEST_PROOF_COOKIE}=""' in set_cookie_headers or "Max-Age=0" in set_cookie_headers

    def test_failed_merge_keeps_guest_capability(self):
        client = TestClient(app)
        client.cookies.set(GUEST_PROOF_COOKIE, make_guest_proof(_SID))
        r, _ = self._login(client, merge_result=False)
        set_cookie_headers = ",".join(
            v for k, v in r.headers.multi_items() if k.lower() == "set-cookie"
        )
        # Only the auth JWT cookie is set; the guest capability is untouched.
        assert GUEST_PROOF_COOKIE not in set_cookie_headers
