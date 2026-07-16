"""
SSE transport contract for the chat stream endpoints.

Locks the header set that keeps proxies from caching, transforming, or
buffering the stream (Cache-Control: no-cache, no-transform;
X-Accel-Buffering: no), the immediate `: connected` comment that flushes the
response start before any heavy work, chunked transfer (no Content-Length),
and status 200 on the streaming response.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


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


def _assert_sse_transport(res):
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert res.headers["cache-control"] == "no-cache, no-transform"
    assert res.headers["x-accel-buffering"] == "no"
    assert "content-length" not in res.headers


def test_public_stream_headers_and_early_flush(client):
    res = client.post(
        "/api/v1/rico/chat/stream/public",
        json={"message": "hello", "session_id": "web-ssetest0001"},
    )
    _assert_sse_transport(res)
    # The very first bytes must be the SSE comment — before intent routing,
    # DB, or provider work — so proxies flush the response start immediately.
    assert res.text.startswith(": connected\n\n")


def test_public_stream_missing_session_error_keeps_sse_headers(client):
    # No session_id: passes model validation (Optional), hits the route's
    # invalid-session error stream — which must carry the same SSE headers.
    res = client.post(
        "/api/v1/rico/chat/stream/public",
        json={"message": "hello"},
    )
    _assert_sse_transport(res)
    assert '"type": "error"' in res.text or '"type":"error"' in res.text


def test_authenticated_stream_unauthorized_error_keeps_sse_headers(client):
    res = client.post("/api/v1/rico/chat/stream", json={"message": "hello"})
    _assert_sse_transport(res)
    assert '"type": "error"' in res.text or '"type":"error"' in res.text
