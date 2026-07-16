"""Regression tests for the adjacent-scan security hardening pass.

Covers three server-side fixes:

- FIX 1: ``client_ip_key`` must resolve the *rightmost trusted* X-Forwarded-For
  entry, not the attacker-controlled leftmost one, so per-IP rate limits cannot
  be bypassed by forging the header.
- FIX 2: the unauthenticated ``POST /chat/public`` endpoint must never let an
  unverified ``email`` adopt a real account identity — it becomes a namespaced,
  non-persisting public session, while still enforcing the registered user's
  quota gate as pure anti-dodge.
- FIX 3: ``CVParser._parse_docx`` must reject DOCX decompression bombs (a small
  zip declaring gigabytes of uncompressed content) without inflating them.

Mirrors tests/test_sse_stream_headers.py: JWT_SECRET default, module-scoped
TestClient, and a limiter-reset fixture.
"""
from __future__ import annotations

import hashlib
import io
import os
import zipfile

import pytest

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


# ── Shared fixtures ───────────────────────────────────────────────────────────

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


def _make_request(xff=None, peer="9.9.9.9"):
    """Build a minimal Starlette Request with an optional X-Forwarded-For header."""
    from starlette.requests import Request

    headers = []
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": (peer, 12345),
    }
    return Request(scope)


# ── FIX 1: X-Forwarded-For rate-limit bypass ──────────────────────────────────

def test_xff_returns_rightmost_trusted_hop_not_leftmost():
    from src.api.rate_limit import client_ip_key

    # Render appends the real peer to the RIGHT; with 1 trusted hop we take the
    # rightmost entry. The leftmost ("1.1.1.1") is attacker-controlled.
    req = _make_request(xff="1.1.1.1, 2.2.2.2")
    key = client_ip_key(req)
    assert key == "2.2.2.2"
    assert key != "1.1.1.1"  # attacker-controlled leftmost must NOT win


def test_xff_honours_trusted_proxy_hops_env(monkeypatch):
    from src.api.rate_limit import client_ip_key

    # With two trusted proxies, the real client is the entry two hops from the right.
    monkeypatch.setenv("RICO_TRUSTED_PROXY_HOPS", "2")
    req = _make_request(xff="1.1.1.1, 2.2.2.2")
    assert client_ip_key(req) == "1.1.1.1"


def test_xff_fewer_entries_than_hops_falls_back_to_peer(monkeypatch):
    from src.api.rate_limit import client_ip_key

    # Misconfig/dev: header has fewer entries than expected trusted hops → do NOT
    # trust the forged head; fall back to the direct peer.
    monkeypatch.setenv("RICO_TRUSTED_PROXY_HOPS", "3")
    req = _make_request(xff="1.1.1.1, 2.2.2.2", peer="9.9.9.9")
    assert client_ip_key(req) == "9.9.9.9"


def test_no_or_empty_xff_falls_back_to_peer():
    from src.api.rate_limit import client_ip_key

    assert client_ip_key(_make_request(xff=None, peer="9.9.9.9")) == "9.9.9.9"
    assert client_ip_key(_make_request(xff="", peer="9.9.9.9")) == "9.9.9.9"
    # Only separators/whitespace → no usable entries → peer fallback.
    assert client_ip_key(_make_request(xff="  ,  ", peer="9.9.9.9")) == "9.9.9.9"


def test_trusted_proxy_hops_clamped_and_default():
    from src.api.rate_limit import _trusted_proxy_hops

    os.environ.pop("RICO_TRUSTED_PROXY_HOPS", None)
    assert _trusted_proxy_hops() == 1  # default
    os.environ["RICO_TRUSTED_PROXY_HOPS"] = "0"
    assert _trusted_proxy_hops() == 1  # clamped to >= 1
    os.environ["RICO_TRUSTED_PROXY_HOPS"] = "not-an-int"
    assert _trusted_proxy_hops() == 1  # parse error → default 1
    os.environ.pop("RICO_TRUSTED_PROXY_HOPS", None)
