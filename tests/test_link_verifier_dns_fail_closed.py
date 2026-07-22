"""SSRF DNS fail-closed regression (LOW-3).

Before the fix, both _is_safe_url_sync and _is_safe_url_async caught every
DNS-resolution error and returned True ("allow URL but note limitation") —
so ANY URL whose hostname failed to resolve (NXDOMAIN, resolver error,
timeout, or a rebinding attempt racing the check) sailed through the SSRF
guard. These tests pin the corrected contract:

    a hostname that cannot be resolved to a provably-public IP is REJECTED,
    identically on the sync and async paths.

Acceptance criterion (owner): no URL with an unresolvable hostname may pass
the SSRF check on either path.

All DNS is mocked — deterministic, no network. Every test asserts the
PRE-FIX behavior would have differed (the allow-list cases still pass, the
resolver-failure cases now return False) so the file is a true regression
guard, not just a smoke test.
"""
from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from src.services.link_verifier import _is_safe_url_async, _is_safe_url_sync


# Public hostname → public IP: getaddrinfo returns a routable address.
_PUBLIC_ADDRINFO = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
# Public hostname → private IP (DNS-rebinding shape): must be rejected by the
# existing private-range guard (unchanged by this fix, re-pinned here).
_PRIVATE_ADDRINFO = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))]
# Public hostname → cloud metadata IP.
_METADATA_ADDRINFO = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 0))]

_URL = "https://jobs.example.com/posting/123"


# ── async path ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_async_nxdomain_is_rejected():
    """socket.gaierror / NXDOMAIN → fail closed (was: allowed)."""
    with patch("socket.getaddrinfo", side_effect=socket.gaierror(-2, "Name or service not known")):
        assert await _is_safe_url_async(_URL) is False


@pytest.mark.asyncio
async def test_async_generic_resolver_exception_is_rejected():
    """Any resolver exception (timeout, transient failure) → fail closed."""
    with patch("socket.getaddrinfo", side_effect=OSError("resolver unavailable")):
        assert await _is_safe_url_async(_URL) is False


@pytest.mark.asyncio
async def test_async_public_hostname_public_ip_is_allowed():
    """A hostname that resolves to a public IP still passes."""
    with patch("socket.getaddrinfo", return_value=_PUBLIC_ADDRINFO):
        assert await _is_safe_url_async(_URL) is True


@pytest.mark.asyncio
async def test_async_public_hostname_private_ip_is_rejected():
    """DNS-rebinding shape: resolves to a private IP → rejected."""
    with patch("socket.getaddrinfo", return_value=_PRIVATE_ADDRINFO):
        assert await _is_safe_url_async(_URL) is False


@pytest.mark.asyncio
async def test_async_public_hostname_metadata_ip_is_rejected():
    with patch("socket.getaddrinfo", return_value=_METADATA_ADDRINFO):
        assert await _is_safe_url_async(_URL) is False


# ── sync path ────────────────────────────────────────────────────────────────

def test_sync_nxdomain_is_rejected():
    with patch("socket.getaddrinfo", side_effect=socket.gaierror(-2, "Name or service not known")):
        assert _is_safe_url_sync(_URL) is False


def test_sync_generic_resolver_exception_is_rejected():
    with patch("socket.getaddrinfo", side_effect=OSError("resolver unavailable")):
        assert _is_safe_url_sync(_URL) is False


def test_sync_public_hostname_public_ip_is_allowed():
    with patch("socket.getaddrinfo", return_value=_PUBLIC_ADDRINFO):
        assert _is_safe_url_sync(_URL) is True


def test_sync_public_hostname_private_ip_is_rejected():
    with patch("socket.getaddrinfo", return_value=_PRIVATE_ADDRINFO):
        assert _is_safe_url_sync(_URL) is False


def test_sync_public_hostname_metadata_ip_is_rejected():
    with patch("socket.getaddrinfo", return_value=_METADATA_ADDRINFO):
        assert _is_safe_url_sync(_URL) is False


# ── sync/async parity ────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "getaddrinfo_kwargs, expected",
    [
        ({"side_effect": socket.gaierror(-2, "NXDOMAIN")}, False),
        ({"side_effect": OSError("resolver down")}, False),
        ({"return_value": _PUBLIC_ADDRINFO}, True),
        ({"return_value": _PRIVATE_ADDRINFO}, False),
        ({"return_value": _METADATA_ADDRINFO}, False),
    ],
)
async def test_sync_and_async_agree(getaddrinfo_kwargs, expected):
    """The two code paths must reach the SAME verdict for every DNS outcome."""
    with patch("socket.getaddrinfo", **getaddrinfo_kwargs):
        sync_result = _is_safe_url_sync(_URL)
    with patch("socket.getaddrinfo", **getaddrinfo_kwargs):
        async_result = await _is_safe_url_async(_URL)
    assert sync_result == async_result == expected


# ── caller contract: an unresolvable host yields an honest BLOCKED result ─────

@pytest.mark.asyncio
async def test_verify_link_blocks_unresolvable_host_without_fetch():
    """verify_link() self-protects via _is_safe_url_async: an unresolvable
    host is a clean BLOCKED result (no 500, no HTTP fetch attempted)."""
    from src.services.link_verifier import LinkVerifier, LinkStatus

    verifier = LinkVerifier()
    with patch("socket.getaddrinfo", side_effect=socket.gaierror(-2, "NXDOMAIN")), \
         patch.object(verifier, "_get_client") as get_client:
        result = await verifier.verify_link(_URL)
    assert result.status is LinkStatus.BLOCKED
    assert get_client.called is False  # never reached the HTTP path
