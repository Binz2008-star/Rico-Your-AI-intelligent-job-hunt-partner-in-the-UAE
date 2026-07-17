"""
tests/unit/test_upload_image_vision.py

/upload-cv image path — a job-posting screenshot is transcribed by the vision
model, re-classified from the transcript, and returned as a readable classified
response (not a dead-end "Image"). Vision call is mocked; with no HF token the
path degrades gracefully to the format-only image response.
"""
from __future__ import annotations

import io
import os
from unittest.mock import patch

import pytest

@pytest.fixture(autouse=True)
def _guest_capability_owner_browser(monkeypatch):
    """This suite exercises upload mechanics AS the owning guest browser. The
    #1070 ownership boundary is covered by tests/test_1070_guest_identity_binding.py;
    the identity resolution is pinned to the claimed sid."""
    monkeypatch.setattr(
        "src.api.routers.rico_chat._resolve_guest_sid",
        lambda request, response, correlation_sid: correlation_sid,
    )



os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

_PUBLIC_UID = "public:web-imgvision123"
# PNG magic header → classifier detects file_format == "image".
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

_JOB_TEXT = (
    "Product Design Manager (Exchange) at Crypto.com. "
    "Location: Hybrid - Dubai, United Arab Emirates. Posted Sep 17, 2025. "
    "Key responsibilities: lead product design across the exchange. "
    "You will own the design system. Reporting to the Head of Design. "
    "This job is no longer available."
)


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


def _post_image(client):
    return client.post(
        f"/api/v1/rico/upload-cv?user_id={_PUBLIC_UID}",
        files={"file": ("crypto-job.png", io.BytesIO(_PNG), "image/png")},
    )


def test_image_with_vision_returns_readable_classified(client):
    with patch("src.services.image_extractor.extract_text_from_image", return_value=_JOB_TEXT):
        r = _post_image(client)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "classified"
    assert body.get("source") == "image"
    # Re-classified from the transcript — no longer a dead-end "image".
    assert body["document_type"] != "image"
    assert "Crypto.com" in (body.get("extracted_text") or "")
    assert "Crypto.com" in (body.get("message") or "")     # preview shown to the user
    assert "your cv" not in (body.get("message") or "").lower()
    assert body.get("suggested_actions")                    # actionable, not empty


def test_image_without_vision_falls_back_to_image(client):
    with patch("src.services.image_extractor.extract_text_from_image", return_value=None):
        r = _post_image(client)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "classified"
    assert body["document_type"] == "image"
    assert body["display_label"] == "Image"
    assert "extracted_text" not in body


def test_image_vision_graceful_without_token(client, monkeypatch):
    # No HF token (the CI condition) → the real extractor returns None → fallback.
    for k in ("HF_API_TOKEN", "HF_TOKEN", "HF_API_KEY", "HUGGINGFACE_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    r = _post_image(client)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "classified"
    assert body["document_type"] == "image"
