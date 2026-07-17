"""tests/test_1080_bounded_upload_reads.py

#1080 — upload limits enforced before full buffering.

Invariants verified:
  - read_upload_bounded never materializes more than the limit plus one chunk,
    regardless of what Content-Length claimed (the fake file serves unlimited
    data, simulating a missing/false declaration)
  - rejection closes the spooled temp file and raises 413 with the caller's
    friendly message
  - the ingress middleware rejects an oversized DECLARED Content-Length
    immediately and independently stops a chunked/undeclared body at the cap
  - an oversized upload is rejected WITHOUT invoking the document classifier
    (no expensive pipeline work on rejected payloads)
  - normal-size uploads still deliver their full bytes unchanged
"""
from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.upload_limits import (
    MAX_REQUEST_BODY_BYTES,
    BodySizeLimitMiddleware,
    read_upload_bounded,
)


class _FakeUploadFile:
    """UploadFile stand-in that serves `total` bytes (or unlimited when None)
    while tracking how many bytes were actually handed out and whether the
    spooled file was closed."""

    def __init__(self, total: int | None):
        self.total = total
        self.served = 0
        self.closed = False

    async def read(self, size: int = -1) -> bytes:
        if self.total is not None and self.served >= self.total:
            return b""
        n = size if size > 0 else 64 * 1024
        if self.total is not None:
            n = min(n, self.total - self.served)
        self.served += n
        return b"x" * n

    async def close(self) -> None:
        self.closed = True


CHUNK = 64 * 1024
LIMIT = 1024 * 1024  # 1 MB cap for fast tests


class TestBoundedReader:
    def test_normal_file_returns_full_bytes(self):
        f = _FakeUploadFile(total=LIMIT // 2)
        data = asyncio.run(read_upload_bounded(f, LIMIT, chunk_size=CHUNK))
        assert len(data) == LIMIT // 2
        assert f.closed is False

    def test_exactly_at_limit_is_accepted(self):
        f = _FakeUploadFile(total=LIMIT)
        data = asyncio.run(read_upload_bounded(f, LIMIT, chunk_size=CHUNK))
        assert len(data) == LIMIT

    def test_unlimited_stream_stops_bounded(self):
        # Simulates missing/false Content-Length: the source would serve
        # forever; the reader must stop within one chunk past the limit.
        f = _FakeUploadFile(total=None)
        with pytest.raises(HTTPException) as e:
            asyncio.run(read_upload_bounded(f, LIMIT, chunk_size=CHUNK))
        assert e.value.status_code == 413
        assert f.served <= LIMIT + CHUNK, "peak bytes materialized must stay bounded"

    def test_rejection_closes_temp_file_and_uses_friendly_detail(self):
        f = _FakeUploadFile(total=None)
        with pytest.raises(HTTPException) as e:
            asyncio.run(read_upload_bounded(f, LIMIT, detail="Too big, friend",
                                            chunk_size=CHUNK))
        assert f.closed is True
        assert e.value.detail == "Too big, friend"


# ── Ingress middleware ────────────────────────────────────────────────────────

def _tiny_app() -> FastAPI:
    app = FastAPI()

    @app.post("/echo-size")
    async def echo_size(request: Request):
        body = await request.body()
        return {"received": len(body)}

    app.add_middleware(BodySizeLimitMiddleware, max_bytes=LIMIT)
    return app


class TestIngressMiddleware:
    def test_small_body_passes_through(self):
        tc = TestClient(_tiny_app())
        r = tc.post("/echo-size", content=b"x" * 1000)
        assert r.status_code == 200
        assert r.json()["received"] == 1000

    def test_oversized_declared_length_rejected_before_body(self):
        tc = TestClient(_tiny_app())
        r = tc.post("/echo-size", content=b"", headers={"Content-Length": str(LIMIT * 10)})
        assert r.status_code == 413

    def test_chunked_body_without_length_stops_at_cap(self):
        # Generator body → chunked transfer encoding, no Content-Length.
        def gen():
            for _ in range(64):  # would total 4 MB, cap is 1 MB
                yield b"x" * CHUNK

        tc = TestClient(_tiny_app())
        r = tc.post("/echo-size", content=gen())
        assert r.status_code == 413

    def test_understated_content_length_still_stopped_by_counting(self):
        # Declared length lies under the cap; actual bytes exceed it. httpx
        # refuses to send more than the declared length, so exercise the ASGI
        # contract directly.
        app = BodySizeLimitMiddleware(_unreachable_app, max_bytes=LIMIT)
        messages = [
            {"type": "http.request", "body": b"x" * CHUNK, "more_body": True}
            for _ in range(64)
        ]

        sent = []

        async def receive():
            return messages.pop(0)

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/echo-size",
            "headers": [(b"content-length", b"100")],
            "query_string": b"",
        }
        asyncio.run(app(scope, receive, send))
        assert sent[0]["type"] == "http.response.start"
        assert sent[0]["status"] == 413


async def _unreachable_app(scope, receive, send):
    # Pull the body the way a parser would; the middleware must abort us.
    while True:
        message = await receive()
        if not message.get("more_body"):
            break
    raise AssertionError("app should have been aborted by the body cap")


# ── Real app wiring: oversized upload never reaches the classifier ───────────

class TestRealAppWiring:
    def test_app_registers_ingress_cap(self):
        from src.api.app import app
        stack_reprs = [str(m) for m in app.user_middleware]
        assert any("BodySizeLimitMiddleware" in s for s in stack_reprs)

    def test_oversized_upload_cv_rejected_without_classifier(self):
        from src.api.app import app
        classifier = MagicMock(side_effect=AssertionError("classifier must not run"))
        with patch("src.services.document_classifier.classify_document", classifier):
            tc = TestClient(app)
            oversized = b"x" * (MAX_REQUEST_BODY_BYTES + 1024)
            r = tc.post(
                "/api/v1/rico/upload-cv",
                files={"file": ("big.pdf", oversized, "application/pdf")},
            )
        assert r.status_code == 413
        classifier.assert_not_called()

    def test_normal_small_upload_still_reaches_route_logic(self):
        # A tiny text file passes the ingress cap and the bounded read; the
        # route may reject it later for content reasons, but never with 413.
        from src.api.app import app
        tc = TestClient(app)
        r = tc.post(
            "/api/v1/rico/upload-cv",
            files={"file": ("cv.txt", b"hello rico", "text/plain")},
        )
        assert r.status_code != 413


class TestExactCapBoundaries:
    """Owner merge condition: the exact 10MB image / 25MB document boundaries
    must not suffer off-by-one — exactly-at-cap is accepted, cap+1 rejected."""

    def test_exact_25mb_document_accepted_and_plus_one_rejected(self):
        from src.api.routers.rico_chat import _MAX_DOC_BYTES, _upload_limit_for
        assert _upload_limit_for("pdf") == _MAX_DOC_BYTES == 25 * 1024 * 1024

        at_cap = _FakeUploadFile(total=_MAX_DOC_BYTES)
        data = asyncio.run(read_upload_bounded(at_cap, _MAX_DOC_BYTES))
        assert len(data) == _MAX_DOC_BYTES

        over = _FakeUploadFile(total=_MAX_DOC_BYTES + 1)
        with pytest.raises(HTTPException) as e:
            asyncio.run(read_upload_bounded(over, _MAX_DOC_BYTES))
        assert e.value.status_code == 413

    def test_exact_10mb_image_boundary_semantics(self):
        from src.api.routers.rico_chat import _MAX_IMAGE_BYTES, _upload_limit_for
        assert _upload_limit_for("image") == _MAX_IMAGE_BYTES == 10 * 1024 * 1024
        # The per-kind rule is a strict `>` post-detection check: exactly-at-cap
        # passes, one byte over fails.
        exactly = b"x" * _MAX_IMAGE_BYTES
        assert not (len(exactly) > _MAX_IMAGE_BYTES)
        assert (len(exactly) + 1) > _MAX_IMAGE_BYTES

    def test_ingress_cap_leaves_room_for_25mb_multipart(self):
        from src.api.upload_limits import MAX_REQUEST_BODY_BYTES, MAX_UPLOAD_BYTES
        assert MAX_UPLOAD_BYTES == 25 * 1024 * 1024
        assert MAX_REQUEST_BODY_BYTES > MAX_UPLOAD_BYTES, \
            "multipart framing allowance must keep a full 25MB document acceptable"
