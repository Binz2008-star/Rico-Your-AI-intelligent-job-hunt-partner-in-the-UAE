"""#1101 — private-response cache boundary.

Pins the contract that no account-scoped API response can be stored or
shared through browser, proxy, or CDN caches:

1. DEFAULT BOUNDARY — every response whose route did not set its own
   Cache-Control carries ``private, no-store, max-age=0`` plus the legacy
   ``Pragma: no-cache`` / ``Expires: 0`` pair.
2. ROUTE OPT-OUT PRESERVED — a route that sets Cache-Control explicitly
   (the SSE stream's ``no-cache, no-transform``) is left untouched.
3. VARY DEFENSE — ``Cookie``, ``Authorization``, ``Origin`` are merged into
   Vary without clobbering existing tokens; a ``Vary: *`` is left alone.
   Vary is defense in depth, never a substitute for no-store.
4. REPLAY REGRESSION — a standards-honoring shared cache, even one with a
   degenerate URL-only cache key (worst-case CDN key drift), can never
   store account A's response, so it can never replay it to account B or
   to an anonymous client after logout.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.cache_privacy import (
    PRIVATE_CACHE_CONTROL,
    PrivateCacheHeadersMiddleware,
)

client = TestClient(app)


def _make_token(email: str, role: str = "user") -> str:
    from src.api.auth import create_access_token

    return create_access_token({"sub": email, "role": role})


def _assert_private_no_store(resp) -> None:
    assert resp.headers.get("Cache-Control") == PRIVATE_CACHE_CONTROL
    assert resp.headers.get("Pragma") == "no-cache"
    assert resp.headers.get("Expires") == "0"
    vary = {t.strip().lower() for t in resp.headers.get("Vary", "").split(",")}
    assert {"cookie", "authorization", "origin"} <= vary


# ── 1. Default boundary on representative account-scoped endpoints ────────────
# The middleware stamps every response regardless of status, so these pins
# hold with or without a live DB behind the route.

def test_me_authenticated_is_private_no_store():
    client.cookies.set("access_token", _make_token("cache-a@test.local"))
    try:
        resp = client.get("/api/v1/me")
    finally:
        client.cookies.clear()
    assert resp.status_code == 200
    _assert_private_no_store(resp)


def test_me_unauthenticated_is_private_no_store():
    resp = client.get("/api/v1/me")
    _assert_private_no_store(resp)


def test_representative_sensitive_endpoints_are_private_no_store():
    for path in (
        "/api/v1/rico/profile",
        "/api/v1/user/files",
        "/api/v1/applications",
        "/api/v1/rico/settings/saved-searches",
        "/api/v1/stats/dashboard",
    ):
        resp = client.get(path)
        _assert_private_no_store(resp)


def test_health_and_version_are_not_publicly_cacheable():
    for path in ("/health", "/version"):
        resp = client.get(path)
        cc = resp.headers.get("Cache-Control", "")
        assert "no-store" in cc and "public" not in cc


# ── 2. Route-set Cache-Control is preserved (SSE contract) ────────────────────

def test_sse_stream_keeps_no_cache_no_transform():
    from src.api.routers.rico_chat import SSE_HEADERS

    assert SSE_HEADERS["Cache-Control"] == "no-cache, no-transform"
    resp = client.post(
        "/api/v1/rico/chat/stream",
        json={"message": "hello", "session_id": "cache-test"},
    )
    cc = resp.headers.get("Cache-Control", "")
    # Whether the route streamed (its own header) or was rejected before the
    # route ran (middleware default), the response must never be storable
    # and a route-set header must never be rewritten by the middleware.
    if resp.status_code == 200:
        assert cc == "no-cache, no-transform"
    else:
        assert cc == PRIVATE_CACHE_CONTROL


def test_middleware_never_overrides_route_set_cache_control():
    from fastapi import FastAPI, Response

    mini = FastAPI()

    @mini.get("/custom")
    def custom() -> Response:
        return Response(content="x", headers={"Cache-Control": "no-cache, no-transform"})

    @mini.get("/default")
    def default() -> dict:
        return {"ok": True}

    mini.add_middleware(PrivateCacheHeadersMiddleware)
    mini_client = TestClient(mini)

    custom_resp = mini_client.get("/custom")
    assert custom_resp.headers["Cache-Control"] == "no-cache, no-transform"
    assert "Pragma" not in custom_resp.headers  # opt-out is total, not partial

    default_resp = mini_client.get("/default")
    _assert_private_no_store(default_resp)


# ── 3. Vary merge semantics ───────────────────────────────────────────────────

def test_vary_merges_without_clobbering_existing_tokens():
    from fastapi import FastAPI, Response

    mini = FastAPI()

    @mini.get("/varied")
    def varied() -> Response:
        return Response(content="x", headers={"Vary": "Accept-Encoding, Origin"})

    mini.add_middleware(PrivateCacheHeadersMiddleware)
    vary = TestClient(mini).get("/varied").headers["Vary"]
    tokens = [t.strip().lower() for t in vary.split(",")]
    assert tokens.count("origin") == 1  # merged, not duplicated
    assert "accept-encoding" in tokens and "cookie" in tokens and "authorization" in tokens


def test_vary_star_is_left_alone():
    from fastapi import FastAPI, Response

    mini = FastAPI()

    @mini.get("/star")
    def star() -> Response:
        return Response(content="x", headers={"Vary": "*"})

    mini.add_middleware(PrivateCacheHeadersMiddleware)
    assert TestClient(mini).get("/star").headers["Vary"] == "*"


# ── 4. Replay regression: account A can never reach account B ────────────────

class _SharedCache:
    """A standards-honoring shared cache with the WORST possible cache key:
    URL only — no Vary, no cookie partitioning. If headers permit storage,
    cross-user replay WILL happen here. The only thing standing between
    account A and account B is the response's storage directives."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def offer(self, url: str, resp) -> None:
        cc = resp.headers.get("Cache-Control", "").lower()
        if "no-store" in cc or "private" in cc:
            return  # a compliant shared cache MUST NOT store this
        self.store[url] = resp.text

    def replay(self, url: str) -> str | None:
        return self.store.get(url)


def test_account_a_response_cannot_replay_for_account_b_or_after_logout():
    cache = _SharedCache()
    url = "/api/v1/me"

    # Account A, authenticated, passes through the shared cache.
    client.cookies.set("access_token", _make_token("cache-a@test.local"))
    try:
        resp_a = client.get(url)
    finally:
        client.cookies.clear()
    assert resp_a.status_code == 200
    assert "cache-a@test.local" in resp_a.text
    cache.offer(url, resp_a)

    # Account B requests the same URL: the cache must have nothing to serve.
    assert cache.replay(url) is None
    client.cookies.set("access_token", _make_token("cache-b@test.local"))
    try:
        resp_b = client.get(url)
    finally:
        client.cookies.clear()
    cache.offer(url, resp_b)
    assert "cache-a@test.local" not in resp_b.text

    # After logout (no cookie), the same URL replays nothing from either user.
    assert cache.replay(url) is None
    resp_anon = client.get(url)
    cache.offer(url, resp_anon)
    assert cache.replay(url) is None
    assert "cache-a@test.local" not in resp_anon.text
    assert "cache-b@test.local" not in resp_anon.text
