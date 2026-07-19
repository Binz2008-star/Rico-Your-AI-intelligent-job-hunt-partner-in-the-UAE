"""src/api/cache_privacy.py

Private-response cache boundary (#1101).

Every response this API serves is account-scoped or operational — the
backend serves no public immutable assets — so the safe default is that
NOTHING it returns may be stored by a browser, proxy, or CDN cache. This
middleware stamps ``Cache-Control: private, no-store, max-age=0`` (plus the
legacy ``Pragma: no-cache`` / ``Expires: 0`` pair) on every HTTP response
whose route did not explicitly choose its own ``Cache-Control`` — the SSE
chat stream sets ``no-cache, no-transform`` (rico_chat.SSE_HEADERS) and
keeps it untouched.

``Cookie``, ``Authorization``, and ``Origin`` are merged into ``Vary`` as
defense in depth against cache-key drift in intermediaries that ignore
storage directives. Vary is never a substitute for no-store (#1101 rule 4).

Pure ASGI on purpose (not BaseHTTPMiddleware): headers are rewritten on the
``http.response.start`` message only, so streaming/SSE bodies pass through
unbuffered.
"""
from __future__ import annotations

from starlette.datastructures import MutableHeaders

PRIVATE_CACHE_CONTROL = "private, no-store, max-age=0"
VARY_TOKENS = ("Cookie", "Authorization", "Origin")


class PrivateCacheHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_cache_boundary(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if "cache-control" not in headers:
                    headers["Cache-Control"] = PRIVATE_CACHE_CONTROL
                    headers["Pragma"] = "no-cache"
                    headers["Expires"] = "0"
                existing_vary = headers.get("vary", "")
                if existing_vary.strip() != "*":
                    tokens = [t.strip() for t in existing_vary.split(",") if t.strip()]
                    present = {t.lower() for t in tokens}
                    tokens.extend(t for t in VARY_TOKENS if t.lower() not in present)
                    headers["Vary"] = ", ".join(tokens)
            await send(message)

        await self.app(scope, receive, send_with_cache_boundary)
