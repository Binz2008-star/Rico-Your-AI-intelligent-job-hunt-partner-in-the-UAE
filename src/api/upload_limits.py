"""src/api/upload_limits.py

Centralized upload-size enforcement (#1080).

Two layers, both required:

1. ``BodySizeLimitMiddleware`` — the earliest in-app ingress boundary. It
   rejects an oversized DECLARED Content-Length before the body is pulled, and
   independently counts the bytes actually received so a missing, understated,
   or chunked Content-Length still stops at the cap BEFORE Starlette's
   multipart parser can spool an unbounded payload to memory/temp disk.

2. ``read_upload_bounded()`` — bounded chunked reading of an accepted
   ``UploadFile``. Route code must never call unbounded ``file.read()``; this
   helper reads at most ``limit`` bytes plus one chunk, closes the spooled
   temp file on rejection, and raises 413 with the caller's friendly message.

The global hard cap stays 25 MB (documents); the stricter 10 MB image rule is
applied by the route AFTER bounded magic-byte detection, exactly as before.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

_MB = 1024 * 1024

# Mirror of the route-level caps (routes import their own constants for
# messages); the middleware allows multipart framing overhead on top so a
# legitimate 25 MB document inside a multipart envelope is never rejected.
MAX_UPLOAD_BYTES = 25 * _MB
MULTIPART_OVERHEAD_BYTES = 2 * _MB
MAX_REQUEST_BODY_BYTES = MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES

_DEFAULT_CHUNK = 64 * 1024

_GENERIC_413_DETAIL = (
    "This file is too large. You can upload documents up to 25MB. "
    "If your file is larger, please compress it or upload a lighter PDF version."
)


async def read_upload_bounded(
    file: UploadFile,
    limit: int,
    *,
    detail: Optional[str] = None,
    chunk_size: int = _DEFAULT_CHUNK,
) -> bytes:
    """Read an UploadFile in bounded chunks, never materializing more than
    ``limit`` plus one chunk.

    Raises HTTPException 413 (with ``detail`` or the generic message) as soon
    as the cap is crossed, closing the underlying spooled temp file first so
    rejection releases its resources. Returns the complete bytes otherwise.
    """
    buf = bytearray()
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > limit:
            try:
                await file.close()
            except Exception:
                logger.warning("upload_limits: temp-file close failed on rejection")
            raise HTTPException(status_code=413, detail=detail or _GENERIC_413_DETAIL)
    return bytes(buf)


class _BodyTooLarge(Exception):
    """Internal signal: counted request bytes crossed the ingress cap."""


class BodySizeLimitMiddleware:
    """Pure-ASGI request body cap — runs before any body parsing.

    - Declared Content-Length above the cap → immediate 413, body never pulled.
    - Regardless of the declared value, received bytes are counted and the
      request is aborted at the cap (chunked/missing/false Content-Length).
    - Non-HTTP scopes and bodiless requests pass through untouched.
    """

    def __init__(self, app: Callable, max_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        declared = self._declared_length(scope)
        if declared is not None and declared > self.max_bytes:
            await self._send_413(send)
            return

        received = 0
        response_started = False

        async def limited_receive() -> dict:
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message: dict) -> None:
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if response_started:
                # Too late for a clean 413 — surface as a broken response
                # rather than a silent success.
                raise
            await self._send_413(send)

    @staticmethod
    def _declared_length(scope: dict) -> Optional[int]:
        for name, value in scope.get("headers") or []:
            if name == b"content-length":
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
        return None

    async def _send_413(self, send: Callable) -> None:
        import json

        body = json.dumps({"detail": _GENERIC_413_DETAIL}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
