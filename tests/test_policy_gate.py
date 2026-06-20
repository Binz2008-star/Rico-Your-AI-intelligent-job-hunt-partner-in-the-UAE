"""tests/test_policy_gate.py

Focused tests for src/api/policy_gate.py.

All 7 required cases:
  1. valid token passes
  2. expired token denied
  3. tampered token denied
  4. wrong user denied
  5. duplicate idempotency_key is idempotent (ALLOWED, skip=True)
  6. denied action does NOT execute (caller checks PolicyResult.allowed)
  7. audit event is written for every policy decision

Design:
  - No real DB: audit_writer is monkeypatched to a spy.
  - No real clock: _now is injected.
  - No real secrets: AGENT_TOKEN_SECRET is set in environment fixture.
  - Tokens are built with the helper `_make_token()` to avoid repetition.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

import pytest

SECRET = "test-secret-key-do-not-use-in-production"
NOW = int(time.time())

os.environ["AGENT_TOKEN_SECRET"] = SECRET
os.environ["DATABASE_URL"] = "postgresql://unused-in-tests"

from src.api.policy_gate import evaluate_token, PolicyResult  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_token(
    *,
    user_id: str = "user-001",
    card_id: str = "card-abc",
    idempotency_key: str = "idem-001",
    risk_class: str = "draft-write",
    requested_scopes: list[str] | None = None,
    intent_summary: str = "Draft reply to candidate",
    undo_capable: bool = True,
    issued_at: int | None = None,
    expires_at: int | None = None,
    agent_id: str = "rico-agent-v1",
    secret: str = SECRET,
    tamper_sig: bool = False,
) -> str:
    issued_at = issued_at if issued_at is not None else NOW - 60
    expires_at = expires_at if expires_at is not None else NOW + 300
    if requested_scopes is None:
        requested_scopes = ["draft-write"]

    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "APT"}).encode())
    payload_dict = {
        "user_id": user_id,
        "card_id": card_id,
        "idempotency_key": idempotency_key,
        "risk_class": risk_class,
        "requested_scopes": requested_scopes,
        "intent_summary": intent_summary,
        "undo_capable": undo_capable,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "agent_id": agent_id,
    }
    payload = _b64url_encode(json.dumps(payload_dict).encode())
    signing_input = f"{header}.{payload}".encode()
    sig_bytes = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    sig = _b64url_encode(sig_bytes if not tamper_sig else b"badbadbadbad")
    return f"{header}.{payload}.{sig}"


class _AuditSpy:
    """Records every call to write_audit_event without touching the DB."""
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


@pytest.fixture(autouse=True)
def _patch_audit(monkeypatch: pytest.MonkeyPatch) -> _AuditSpy:
    spy = _AuditSpy()
    monkeypatch.setattr("src.api.policy_gate.write_audit_event", spy)
    return spy  # type: ignore[return-value]


@pytest.fixture()
def audit_spy(_patch_audit: _AuditSpy) -> _AuditSpy:
    return _patch_audit


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_token_passes(audit_spy: _AuditSpy) -> None:
    """Case 1: A valid token issued to the correct user/card passes."""
    token = _make_token()
    result = await evaluate_token(
        raw_token=token,
        expected_user_id="user-001",
        expected_card_id="card-abc",
        permission_tier="assisted",
        seen_idempotency_keys=set(),
        _now=NOW,
    )
    assert result.allowed is True
    assert result.reason is None
    # Audit must have been written.
    assert len(audit_spy.calls) == 1
    assert audit_spy.calls[0]["policy_decision"] == "ALLOWED"


@pytest.mark.asyncio
async def test_expired_token_denied(audit_spy: _AuditSpy) -> None:
    """Case 2: A token whose expires_at is in the past is rejected."""
    token = _make_token(expires_at=NOW - 1)  # already expired
    result = await evaluate_token(
        raw_token=token,
        expected_user_id="user-001",
        expected_card_id="card-abc",
        permission_tier="assisted",
        seen_idempotency_keys=set(),
        _now=NOW,
    )
    assert result.allowed is False
    assert result.reason == "TOKEN_EXPIRED"
    assert audit_spy.calls[0]["policy_decision"] == "DENIED"
    assert audit_spy.calls[0]["denial_reason"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_tampered_token_denied(audit_spy: _AuditSpy) -> None:
    """Case 3: A token with a bad signature is rejected immediately."""
    token = _make_token(tamper_sig=True)
    result = await evaluate_token(
        raw_token=token,
        expected_user_id="user-001",
        expected_card_id="card-abc",
        permission_tier="assisted",
        seen_idempotency_keys=set(),
        _now=NOW,
    )
    assert result.allowed is False
    assert "SIGNATURE_INVALID" in (result.reason or "")
    assert audit_spy.calls[0]["policy_decision"] == "DENIED"


@pytest.mark.asyncio
async def test_wrong_user_denied(audit_spy: _AuditSpy) -> None:
    """Case 4: Token issued to user-001 cannot be used by user-999."""
    token = _make_token(user_id="user-001")
    result = await evaluate_token(
        raw_token=token,
        expected_user_id="user-999",   # different user from authenticated session
        expected_card_id="card-abc",
        permission_tier="assisted",
        seen_idempotency_keys=set(),
        _now=NOW,
    )
    assert result.allowed is False
    assert result.reason == "USER_ID_MISMATCH"
    assert audit_spy.calls[0]["policy_decision"] == "DENIED"


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_is_idempotent(audit_spy: _AuditSpy) -> None:
    """Case 5: Second call with same idempotency_key returns allowed=True with skip=True.
    No second audit row is written (in-process guard; DB guard is ON CONFLICT DO NOTHING).
    """
    token = _make_token(idempotency_key="idem-dup")
    seen: set[str] = {"idem-dup"}  # already processed

    result = await evaluate_token(
        raw_token=token,
        expected_user_id="user-001",
        expected_card_id="card-abc",
        permission_tier="assisted",
        seen_idempotency_keys=seen,
        _now=NOW,
    )
    assert result.allowed is True
    assert result.idempotent_skip is True
    # No audit write for the in-process skip path.
    assert len(audit_spy.calls) == 0


@pytest.mark.asyncio
async def test_denied_action_does_not_execute(audit_spy: _AuditSpy) -> None:
    """Case 6: Caller never calls execute() when result.allowed is False.
    The gate itself does not execute anything — this test confirms the contract.
    """
    executed = False

    async def fake_execute() -> None:
        nonlocal executed
        executed = True

    token = _make_token(risk_class="destructive")
    result = await evaluate_token(
        raw_token=token,
        expected_user_id="user-001",
        expected_card_id="card-abc",
        permission_tier="autonomous",  # highest tier still blocks 'destructive'
        seen_idempotency_keys=set(),
        _now=NOW,
    )
    # Caller pattern: only execute if allowed.
    if result.allowed:
        await fake_execute()

    assert result.allowed is False
    assert executed is False
    assert "RISK_CLASS_NOT_ALLOWED" in (result.reason or "")
    assert audit_spy.calls[0]["policy_decision"] == "DENIED"


@pytest.mark.asyncio
async def test_audit_event_written_for_every_decision(audit_spy: _AuditSpy) -> None:
    """Case 7: Both ALLOWED and DENIED decisions produce exactly one audit record each."""
    valid_token = _make_token(idempotency_key="idem-a")
    bad_token = _make_token(idempotency_key="idem-b", expires_at=NOW - 1)

    r1 = await evaluate_token(
        raw_token=valid_token,
        expected_user_id="user-001",
        expected_card_id="card-abc",
        permission_tier="assisted",
        seen_idempotency_keys=set(),
        _now=NOW,
    )
    r2 = await evaluate_token(
        raw_token=bad_token,
        expected_user_id="user-001",
        expected_card_id="card-abc",
        permission_tier="assisted",
        seen_idempotency_keys=set(),
        _now=NOW,
    )

    assert r1.allowed is True
    assert r2.allowed is False
    assert len(audit_spy.calls) == 2
    decisions = {c["policy_decision"] for c in audit_spy.calls}
    assert decisions == {"ALLOWED", "DENIED"}
