"""Repo-wide pytest defaults.

Operation-ownership backend: the whole historical suite was written against
the in-process operation store, and unit tests must never touch a real
database (OPERATING_RULES). Force the memory backend for tests by default;
suites that exercise the shared Postgres store (e.g.
tests/integration/test_operation_ownership_postgres.py) opt back in
explicitly with monkeypatch.setenv("RICO_OPERATION_STORE", "postgres"),
which overrides this default for the duration of the test.
"""
from __future__ import annotations

import os

os.environ["RICO_OPERATION_STORE"] = "memory"


# ── #1072 default auth-store health ──────────────────────────────────────────
# get_current_user now verifies every request against the users table
# (auth_version / is_active / DB-authoritative role) and fails CLOSED when the
# configured store is unreachable. Unit tests set a fake DATABASE_URL, so
# without a default fake store every authenticated route test would get 503,
# and every admin route test would 403 because the DB-authoritative role would
# not match the token's admin claim.
#
# The default fake store echoes a healthy account at auth_version 1 whose role
# mirrors the role each test baked into its token (captured by wrapping
# create_access_token below). This preserves the pre-#1072 assumption that a
# test's minted role IS the effective role, while the real DB-authoritative /
# revocation / outage behavior is exercised explicitly by the classes marked
# `@pytest.mark.real_auth_store` or with their own inner `with patch(...)`.
import pytest as _pytest
from unittest.mock import patch as _patch

import src.api.auth as _auth

_TEST_TOKEN_ROLES: dict[str, str] = {}
_real_create_access_token = _auth.create_access_token


def _recording_create_access_token(data):
    sub = data.get("sub") if isinstance(data, dict) else None
    if sub:
        _TEST_TOKEN_ROLES[str(sub).strip().lower()] = (data.get("role") or "user")
    return _real_create_access_token(data)


# Persistent for the whole session so module-scoped client fixtures (which mint
# their token once, on first use) stay recognized across every test that reuses
# them. create_access_token only records role → sub; it never changes token
# contents or signing.
_auth.create_access_token = _recording_create_access_token


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "real_auth_store: disable the default healthy-auth-store patch so the "
        "test exercises the real users_repo.get_auth_snapshot implementation",
    )


@_pytest.fixture(autouse=True)
def _healthy_auth_store_default(request):
    if request.node.get_closest_marker("real_auth_store"):
        yield
        return

    def _snapshot(email: str):
        return ("found", {
            "auth_version": 1,
            "is_active": True,
            "role": _TEST_TOKEN_ROLES.get(email.strip().lower(), "user"),
            "email_verified": True,
        })

    with _patch("src.repositories.users_repo.get_auth_snapshot", side_effect=_snapshot):
        yield
