"""Regression: the canonical identity endpoint ``GET /api/v1/me`` (``user.py``)
— the one the frontend actually reads (``fetchMe()`` → ``OwnerNavEntry`` and the
``/admin/subscribers`` gate) — must expose the server-computed ``is_owner`` flag.

PR #1372 added ``is_owner`` to ``/api/v1/auth/me`` (``auth.py``) instead, a
different endpoint the UI never calls, so the owner surface never activated
despite correct ``RICO_OWNER_USER_ID`` config. These pins keep ``is_owner`` on
the endpoint the UI reads.

The flag stays keyed on the immutable ``users.id`` vs ``RICO_OWNER_USER_ID``
(``deps.is_owner``) — never a hardcoded account/email — and fails closed.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api import deps


class _FakeUser:
    def __init__(self, uid: int):
        self.id = uid


def _make_token(email: str, role: str = "user") -> str:
    from src.api.auth import create_access_token
    return create_access_token({"sub": email, "role": role})


def _auth_and_resolve(monkeypatch, email: str, uid: int):
    """Decouple /me's full-verification call from the DB and wire the
    canonical-id resolution used by deps.is_owner. A real cookie (set by the
    caller) still passes /me's claims-only middleware guest-gate."""
    monkeypatch.setattr(deps, "get_current_user", lambda request: {"email": email, "role": "user"})
    monkeypatch.setattr("src.db.is_db_available", lambda: True)
    monkeypatch.setattr(
        "src.repositories.users_repo.get_user_by_email",
        lambda e: _FakeUser(uid) if e == email else None,
    )


@pytest.fixture
def client():
    return TestClient(app)


def test_me_exposes_is_owner_true_for_owner(client, monkeypatch):
    monkeypatch.setenv("RICO_OWNER_USER_ID", "42")
    _auth_and_resolve(monkeypatch, "owner@x.com", 42)  # canonical id matches owner
    client.cookies.set("access_token", _make_token("owner@x.com"))
    r = client.get("/api/v1/me")
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is True
    assert body["is_owner"] is True


def test_me_is_owner_false_for_non_owner(client, monkeypatch):
    monkeypatch.setenv("RICO_OWNER_USER_ID", "42")
    _auth_and_resolve(monkeypatch, "user@x.com", 7)  # id 7 != owner 42
    client.cookies.set("access_token", _make_token("user@x.com"))
    r = client.get("/api/v1/me")
    assert r.status_code == 200
    assert r.json()["is_owner"] is False


def test_me_is_owner_fails_closed_when_owner_unconfigured(client, monkeypatch):
    monkeypatch.delenv("RICO_OWNER_USER_ID", raising=False)
    _auth_and_resolve(monkeypatch, "owner@x.com", 42)
    client.cookies.set("access_token", _make_token("owner@x.com"))
    r = client.get("/api/v1/me")
    assert r.status_code == 200
    assert r.json()["is_owner"] is False


def test_me_email_is_not_the_authorization_key(client, monkeypatch):
    """Right email but a non-matching canonical id must NOT be owner (id is the key)."""
    monkeypatch.setenv("RICO_OWNER_USER_ID", "42")
    _auth_and_resolve(monkeypatch, "owner@x.com", 99)  # right email, wrong id
    client.cookies.set("access_token", _make_token("owner@x.com"))
    r = client.get("/api/v1/me")
    assert r.status_code == 200
    assert r.json()["is_owner"] is False
