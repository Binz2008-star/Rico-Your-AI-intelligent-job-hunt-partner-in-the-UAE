"""
tests/test_gmail_connector_m0.py

Gmail read-only connector M0 — route gating, state signing, token crypto,
status normalization, and review-item approval. No live Google or DB calls:
repositories and the Google client boundary are mocked; the feature flag is
driven through the RICO_ENABLE_GMAIL_SYNC env var (default off).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

_USER = "gmail-m0-user@example.com"

GMAIL = "/api/v1/integrations/gmail"


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


@pytest.fixture(autouse=True)
def flag_off_by_default(monkeypatch):
    monkeypatch.delenv("RICO_ENABLE_GMAIL_SYNC", raising=False)
    yield


@pytest.fixture()
def auth_client(client):
    from src.api.auth import create_access_token

    token = create_access_token({"sub": _USER, "role": "user"})
    client.cookies.set("access_token", token)
    yield client
    client.cookies.clear()


def _active_connection(**overrides):
    row = {
        "id": "11111111-1111-1111-1111-111111111111",
        "user_id": _USER,
        "provider": "gmail",
        "provider_account_email": "someone@gmail.com",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        "encrypted_refresh_token": "ciphertext",
        "token_encryption_key_version": "v1",
        "status": "active",
        "last_connected_at": None,
        "last_refresh_at": None,
        "last_sync_at": datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
        "last_error": None,
        "created_at": None,
        "updated_at": None,
    }
    row.update(overrides)
    return row


# ── Flag off (default): clear 503s ────────────────────────────────────────────


def test_connect_503_when_flag_off(auth_client):
    r = auth_client.get(f"{GMAIL}/connect")
    assert r.status_code == 503
    assert "not enabled" in r.json()["detail"].lower()


def test_sync_503_when_flag_off(auth_client):
    r = auth_client.post(f"{GMAIL}/sync")
    assert r.status_code == 503
    assert "not enabled" in r.json()["detail"].lower()


def test_callback_503_when_flag_off(client):
    r = client.get(f"{GMAIL}/callback?state=x&code=y", follow_redirects=False)
    assert r.status_code == 503


def test_review_actions_503_when_flag_off(auth_client):
    for action in ("approve", "dismiss"):
        r = auth_client.post(f"{GMAIL}/review-items/some-id/{action}")
        assert r.status_code == 503
        assert "not enabled" in r.json()["detail"].lower()


def test_sync_all_503_when_flag_off_even_with_valid_secret(client, monkeypatch):
    monkeypatch.setenv("RICO_CRON_SECRET", "cron-secret-123")
    r = client.post(f"{GMAIL}/sync-all", headers={"X-Cron-Secret": "cron-secret-123"})
    assert r.status_code == 503
    assert "not enabled" in r.json()["detail"].lower()


# ── Cron guard on /sync-all ───────────────────────────────────────────────────


def test_sync_all_503_when_cron_secret_unconfigured(client, monkeypatch):
    monkeypatch.delenv("RICO_CRON_SECRET", raising=False)
    r = client.post(f"{GMAIL}/sync-all")
    assert r.status_code == 503  # fail-closed: endpoint not configured


def test_sync_all_403_on_wrong_secret(client, monkeypatch):
    monkeypatch.setenv("RICO_CRON_SECRET", "cron-secret-123")
    r = client.post(f"{GMAIL}/sync-all", headers={"X-Cron-Secret": "wrong"})
    assert r.status_code == 403


def test_sync_all_runs_sweep_with_valid_secret_and_flag(client, monkeypatch):
    monkeypatch.setenv("RICO_CRON_SECRET", "cron-secret-123")
    monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "true")
    sweep_result = {"status": "completed", "users_processed": 0}
    with patch(
        "src.services.gmail_sync_service.run_fleet_sweep", return_value=sweep_result
    ) as sweep:
        r = client.post(
            f"{GMAIL}/sync-all", headers={"X-Cron-Secret": "cron-secret-123"}
        )
    assert r.status_code == 200
    assert r.json() == sweep_result
    sweep.assert_called_once()


# ── Status endpoint shapes ────────────────────────────────────────────────────


def test_status_requires_auth(client):
    r = client.get(f"{GMAIL}/status")
    assert r.status_code == 401


def test_status_shape_flag_off(auth_client):
    # No connection row (DB unavailable in tests) → not connected, sync off.
    r = auth_client.get(f"{GMAIL}/status")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "sync_enabled": False,
        "enabled": False,
        "connected": False,
        "provider_email": None,
        "scopes": [],
        "needs_reauth": False,
        "recurring_sync_consent": False,
        "last_sync_at": None,
    }


def test_status_reports_connection_even_when_flag_off(auth_client):
    """Privacy/revocation (BLOCKER 1): a user with a live connection must see it
    and be able to revoke it even while RICO_ENABLE_GMAIL_SYNC is off — /status
    is truthful independent of the flag; the flag only gates sync."""
    # Flag stays OFF (default fixture), but an active connection row exists.
    with patch(
        "src.repositories.gmail_repo.get_connection",
        return_value=_active_connection(),
    ):
        r = auth_client.get(f"{GMAIL}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["connected"] is True            # visible despite the flag being off
    assert body["sync_enabled"] is False        # sync itself stays disabled
    assert body["enabled"] is False             # back-compat alias tracks the flag
    assert body["provider_email"] == "someone@gmail.com"
    assert body["needs_reauth"] is False

    # Disconnect must remain available while the flag is off (it is ungated).
    with patch(
        "src.services.gmail_oauth.disconnect", return_value=(True, False)
    ) as dc:
        d = auth_client.post(f"{GMAIL}/disconnect")
    assert d.status_code == 200
    assert d.json()["disconnected"] is True
    dc.assert_called_once()


def test_status_shape_connected(auth_client, monkeypatch):
    monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "true")
    with patch(
        "src.repositories.gmail_repo.get_connection",
        return_value=_active_connection(),
    ):
        r = auth_client.get(f"{GMAIL}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["connected"] is True
    assert body["provider_email"] == "someone@gmail.com"
    assert body["scopes"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert body["needs_reauth"] is False
    assert body["last_sync_at"].startswith("2026-07-01T12:00:00")
    # The ciphertext must never leak through the status payload.
    assert "encrypted_refresh_token" not in body


def test_status_shape_needs_reauth(auth_client, monkeypatch):
    monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "true")
    with patch(
        "src.repositories.gmail_repo.get_connection",
        return_value=_active_connection(status="needs_reauth", last_sync_at=None),
    ):
        r = auth_client.get(f"{GMAIL}/status")
    body = r.json()
    assert body["connected"] is False
    assert body["needs_reauth"] is True
    assert body["last_sync_at"] is None


# ── Signed OAuth state ────────────────────────────────────────────────────────


def test_state_round_trip():
    from src.services.gmail_oauth import make_state, verify_state

    state = make_state(_USER)
    assert verify_state(state) == _USER


def test_state_expiry_rejected():
    from src.services.gmail_oauth import make_state, verify_state

    expired = make_state(_USER, ttl_seconds=-1)
    assert verify_state(expired) is None


def test_state_tamper_rejected():
    from src.services.gmail_oauth import make_state, verify_state

    state = make_state(_USER)
    payload, _, sig = state.rpartition(".")
    # Flip a character in the signed payload — the HMAC must break.
    flipped = ("A" if payload[0] != "A" else "B") + payload[1:]
    assert verify_state(f"{flipped}.{sig}") is None
    # Garbage and empty inputs are rejected, not raised.
    assert verify_state("") is None
    assert verify_state("no-dot-here") is None
    assert verify_state(f"{payload}.") is None


# ── Token crypto ──────────────────────────────────────────────────────────────


def test_token_crypto_round_trip(monkeypatch):
    from cryptography.fernet import Fernet

    from src.services.token_crypto import decrypt_token, encrypt_token

    monkeypatch.setenv("GMAIL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    ciphertext = encrypt_token("1//refresh-token-value")
    assert ciphertext != "1//refresh-token-value"
    assert decrypt_token(ciphertext) == "1//refresh-token-value"


def test_token_crypto_missing_key_fails_closed(monkeypatch):
    from src.services.token_crypto import (
        TokenCryptoError,
        decrypt_token,
        encrypt_token,
        encryption_key_present,
    )

    monkeypatch.delenv("GMAIL_TOKEN_ENCRYPTION_KEY", raising=False)
    assert encryption_key_present() is False
    with pytest.raises(TokenCryptoError):
        encrypt_token("1//refresh-token-value")
    with pytest.raises(TokenCryptoError):
        decrypt_token("gAAAAA-not-decryptable")


def test_token_crypto_error_never_contains_token(monkeypatch):
    from src.services.token_crypto import TokenCryptoError, encrypt_token

    monkeypatch.delenv("GMAIL_TOKEN_ENCRYPTION_KEY", raising=False)
    secret_value = "1//super-secret-refresh"
    try:
        encrypt_token(secret_value)
        raise AssertionError("expected TokenCryptoError")
    except TokenCryptoError as exc:
        assert secret_value not in str(exc)


# ── Sync-service status normalization ─────────────────────────────────────────


def test_normalize_status_maps_legacy_classifier_statuses():
    from src.repositories.applications_repo import _VALID_STATUSES
    from src.services.gmail_sync_service import normalize_status

    assert normalize_status("interview_scheduled") == "interview"
    assert normalize_status("offer_extended") == "offer"
    # Already-valid statuses pass through unchanged.
    assert normalize_status("applied") == "applied"
    assert normalize_status("rejected") == "rejected"
    assert normalize_status(None) is None
    # Everything the map emits must be a valid SaaS application status.
    for target in ("interview", "offer", "applied", "rejected"):
        assert target in _VALID_STATUSES


# ── Manual sync route ─────────────────────────────────────────────────────────


def test_sync_409_when_not_connected(auth_client, monkeypatch):
    monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "true")
    with patch("src.repositories.gmail_repo.get_connection", return_value=None):
        r = auth_client.post(f"{GMAIL}/sync")
    assert r.status_code == 409


def test_sync_starts_background_task(auth_client, monkeypatch):
    monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "true")
    with patch(
        "src.repositories.gmail_repo.get_connection",
        return_value=_active_connection(),
    ), patch(
        "src.services.gmail_sync_service.run_user_sync",
        return_value={"status": "completed"},
    ) as run_sync:
        r = auth_client.post(f"{GMAIL}/sync")
    assert r.status_code == 200
    assert r.json()["status"] == "started"
    # TestClient executes BackgroundTasks after the response.
    run_sync.assert_called_once_with(_USER, "manual")


# ── Review item approval ──────────────────────────────────────────────────────


def _pending_item(**overrides):
    item = {
        "id": "22222222-2222-2222-2222-222222222222",
        "user_id": _USER,
        "gmail_message_id": "msg-1",
        "subject_snippet": "Interview invitation — Sustainability Lead",
        "sender": "HR <hr@acme.com>",
        "matched_job_id": "job-key-1",
        "matched_company": "Acme",
        "matched_title": "Sustainability Lead",
        "proposed_status": "interview_scheduled",
        "review_status": "pending",
    }
    item.update(overrides)
    return item


def test_approve_applies_normalized_status(auth_client, monkeypatch):
    monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "true")
    with patch(
        "src.repositories.gmail_repo.get_review_item", return_value=_pending_item()
    ), patch(
        "src.repositories.applications_repo.update_status", return_value=True
    ) as update_status, patch(
        "src.repositories.gmail_repo.set_review_item_status", return_value=True
    ) as set_status, patch(
        "src.repositories.gmail_repo.insert_audit_event", return_value=True
    ):
        r = auth_client.post(
            f"{GMAIL}/review-items/22222222-2222-2222-2222-222222222222/approve"
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["applied_status"] == "interview"  # normalized, not interview_scheduled

    args, kwargs = update_status.call_args
    assert args[0] == {"job_id": "job-key-1"}
    assert args[1] == "interview"
    assert kwargs["user_id"] == _USER  # identity from JWT, never from the body
    set_status.assert_called_once_with(
        _USER, "22222222-2222-2222-2222-222222222222", "approved"
    )


def test_approve_404_on_unknown_item(auth_client, monkeypatch):
    monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "true")
    with patch("src.repositories.gmail_repo.get_review_item", return_value=None):
        r = auth_client.post(f"{GMAIL}/review-items/nope/approve")
    assert r.status_code == 404


def test_approve_422_when_unmatched(auth_client, monkeypatch):
    monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "true")
    with patch(
        "src.repositories.gmail_repo.get_review_item",
        return_value=_pending_item(matched_job_id=None),
    ):
        r = auth_client.post(
            f"{GMAIL}/review-items/22222222-2222-2222-2222-222222222222/approve"
        )
    assert r.status_code == 422


def test_approve_409_when_already_resolved(auth_client, monkeypatch):
    monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "true")
    with patch(
        "src.repositories.gmail_repo.get_review_item",
        return_value=_pending_item(review_status="approved"),
    ):
        r = auth_client.post(
            f"{GMAIL}/review-items/22222222-2222-2222-2222-222222222222/approve"
        )
    assert r.status_code == 409


def test_dismiss_marks_item(auth_client, monkeypatch):
    monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "true")
    with patch(
        "src.repositories.gmail_repo.get_review_item", return_value=_pending_item()
    ), patch(
        "src.repositories.gmail_repo.set_review_item_status", return_value=True
    ) as set_status, patch(
        "src.repositories.gmail_repo.insert_audit_event", return_value=True
    ):
        r = auth_client.post(
            f"{GMAIL}/review-items/22222222-2222-2222-2222-222222222222/dismiss"
        )
    assert r.status_code == 200
    set_status.assert_called_once_with(
        _USER, "22222222-2222-2222-2222-222222222222", "dismissed"
    )
