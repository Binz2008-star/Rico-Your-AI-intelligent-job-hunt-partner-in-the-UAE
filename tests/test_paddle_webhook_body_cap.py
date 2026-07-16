"""
Paddle webhook body cap (#1073).

The unauthenticated /api/v1/billing/paddle/webhook must reject an oversized body
BEFORE buffering it in full / before signature verification, so a network client
cannot force each worker to allocate a large payload without knowing the secret.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

_MAX = 256 * 1024


class _FakeStreamRequest:
    def __init__(self, chunks, headers):
        self.headers = headers
        self._chunks = chunks

    async def stream(self):
        for c in self._chunks:
            yield c


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.api.app import app

    return TestClient(app, raise_server_exceptions=False)


class TestWebhookBodyCapRoute:
    def test_oversized_body_rejected_413(self, client):
        big = b"x" * (_MAX + 1)
        r = client.post(
            "/api/v1/billing/paddle/webhook",
            content=big,
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 413

    def test_normal_body_not_413(self, client):
        # A small body passes the cap and reaches signature verification (which
        # fails with 400 for a forged/absent signature). The point: it is NOT 413.
        r = client.post(
            "/api/v1/billing/paddle/webhook",
            content=b'{"event_id":"x"}',
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code != 413


class TestReadBoundedBodyUnit:
    @pytest.mark.asyncio
    async def test_streamed_bytes_over_limit_rejected(self):
        from fastapi import HTTPException
        from src.api.routers.paddle_billing import _read_bounded_body

        req = _FakeStreamRequest([b"a" * 60, b"b" * 60], headers={})  # 120 > 100, no length
        with pytest.raises(HTTPException) as ei:
            await _read_bounded_body(req, max_bytes=100)
        assert ei.value.status_code == 413

    @pytest.mark.asyncio
    async def test_declared_content_length_over_limit_rejected(self):
        from fastapi import HTTPException
        from src.api.routers.paddle_billing import _read_bounded_body

        req = _FakeStreamRequest([b"x"], headers={"content-length": "999999"})
        with pytest.raises(HTTPException) as ei:
            await _read_bounded_body(req, max_bytes=100)
        assert ei.value.status_code == 413

    @pytest.mark.asyncio
    async def test_under_limit_returns_exact_bytes(self):
        from src.api.routers.paddle_billing import _read_bounded_body

        req = _FakeStreamRequest([b"hello ", b"world"], headers={})
        body = await _read_bounded_body(req, max_bytes=100)
        assert body == b"hello world"
