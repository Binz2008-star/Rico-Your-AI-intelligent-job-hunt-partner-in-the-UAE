"""
tests/test_avatar_endpoints.py

Profile avatar endpoints (migration 050; owner request 2026-07-21).

Pins:
  1. GET without an avatar → {"avatar": None} (never 500 pre-migration).
  2. POST a valid PNG → 201, stored as a data URL via avatar_repo.set_avatar.
  3. POST a non-image (magic-byte sniff) → 400, nothing stored.
  4. POST oversize (>500 KB) → 413 via the bounded reader.
  5. DELETE routes to avatar_repo.delete_avatar.
  6. Storage outage (RuntimeError) → 503, never a crash or fake success.
  7. All routes require auth (401 without a JWT cookie).
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)
os.environ.setdefault("ADMIN_EMAIL", "test@rico.ai")
os.environ.setdefault("ADMIN_PASSWORD", "testpass123")

PNG_1PX = (
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 32  # magic + filler; sniff only needs the signature
)
JPEG_STUB = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP_STUB = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 8


@pytest.fixture(scope="module")
def auth_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": "avatar-test@rico.ai", "role": "user"})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


@pytest.fixture()
def anon_client():
    from fastapi.testclient import TestClient
    from src.api.app import app

    return TestClient(app, raise_server_exceptions=False)


class TestGetAvatar:
    def test_no_avatar_returns_null_never_500(self, auth_client):
        with patch("src.api.routers.avatar.avatar_repo.get_avatar", return_value=None):
            r = auth_client.get("/api/v1/user/avatar")
        assert r.status_code == 200
        assert r.json() == {"avatar": None}

    def test_existing_avatar_returned(self, auth_client):
        row = {"data_url": "data:image/png;base64,QUJD", "content_type": "image/png", "updated_at": None}
        with patch("src.api.routers.avatar.avatar_repo.get_avatar", return_value=row):
            r = auth_client.get("/api/v1/user/avatar")
        assert r.status_code == 200
        assert r.json()["avatar"] == "data:image/png;base64,QUJD"


class TestUploadAvatar:
    @pytest.mark.parametrize("payload,ctype", [
        (PNG_1PX, "image/png"),
        (JPEG_STUB, "image/jpeg"),
        (WEBP_STUB, "image/webp"),
    ])
    def test_valid_image_stored_as_data_url(self, auth_client, payload, ctype):
        with patch("src.api.routers.avatar.avatar_repo.set_avatar") as set_mock:
            r = auth_client.post(
                "/api/v1/user/avatar",
                files={"file": ("me.img", payload, "application/octet-stream")},
            )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["avatar"].startswith(f"data:{ctype};base64,")
        args = set_mock.call_args[0]
        assert args[0] == "avatar-test@rico.ai"
        assert args[1].startswith(f"data:{ctype};base64,")
        assert args[2] == ctype
        assert args[3] == len(payload)

    def test_non_image_rejected_400(self, auth_client):
        with patch("src.api.routers.avatar.avatar_repo.set_avatar") as set_mock:
            r = auth_client.post(
                "/api/v1/user/avatar",
                files={"file": ("evil.pdf", b"%PDF-1.4 not an image", "image/png")},
            )
        assert r.status_code == 400
        set_mock.assert_not_called()

    def test_oversize_rejected_413(self, auth_client):
        big = PNG_1PX + b"\x00" * (500 * 1024 + 1)
        with patch("src.api.routers.avatar.avatar_repo.set_avatar") as set_mock:
            r = auth_client.post(
                "/api/v1/user/avatar",
                files={"file": ("big.png", big, "image/png")},
            )
        assert r.status_code == 413
        set_mock.assert_not_called()

    def test_storage_outage_503_never_fake_success(self, auth_client):
        with patch(
            "src.api.routers.avatar.avatar_repo.set_avatar",
            side_effect=RuntimeError("db down"),
        ):
            r = auth_client.post(
                "/api/v1/user/avatar",
                files={"file": ("me.png", PNG_1PX, "image/png")},
            )
        assert r.status_code == 503


class TestDeleteAvatar:
    def test_delete_routes_to_repo(self, auth_client):
        with patch("src.api.routers.avatar.avatar_repo.delete_avatar", return_value=True) as del_mock:
            r = auth_client.delete("/api/v1/user/avatar")
        assert r.status_code == 200
        assert r.json() == {"ok": True, "deleted": True}
        del_mock.assert_called_once_with("avatar-test@rico.ai")

    def test_storage_outage_503(self, auth_client):
        with patch(
            "src.api.routers.avatar.avatar_repo.delete_avatar",
            side_effect=RuntimeError("db down"),
        ):
            r = auth_client.delete("/api/v1/user/avatar")
        assert r.status_code == 503


class TestAuthRequired:
    def test_all_routes_reject_anonymous(self, anon_client):
        assert anon_client.get("/api/v1/user/avatar").status_code == 401
        assert anon_client.post(
            "/api/v1/user/avatar", files={"file": ("a.png", PNG_1PX, "image/png")}
        ).status_code == 401
        assert anon_client.delete("/api/v1/user/avatar").status_code == 401
