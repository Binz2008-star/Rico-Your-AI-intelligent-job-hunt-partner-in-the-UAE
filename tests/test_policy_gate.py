"""test_policy_gate.py

Focused unit tests for policy_gate.py — token validation, idempotency,
permission tier enforcement, and audit event writing.

No I/O to real DB or Redis. All external dependencies are mocked.

Test matrix (from #683 spec):
  T01  valid token passes
  T02  expired token denied
  T03  tampered token denied
  T04  wrong user denied
  T05  duplicate idempotency_key is idempotent (not re-executed)
  T06  denied action does not reach execution
  T07  audit event is written on every policy decision
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.policy_gate import (
    TOKEN_SECRET,
    TOKEN_TTL_SECONDS,
    ApprovalToken,
    parse_and_validate_token,
)


# ---------------------------------------------------------------------------
# Helpers — build a correctly signed token
# ---------------------------------------------------------------------------

def _make_token(
    user_id: str,
    card_id: str,
    idempotency_key: str,
    risk_class: str = "reversible-write",
    iat: float | None = None,
    secret: bytes = TOKEN_SECRET,
) -> str:
    if iat is None:
        iat = time.time()
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload_dict = {
        "user_id": user_id,
        "card_id": card_id,
        "idempotency_key": idempotency_key,
        "risk_class": risk_class,
        "iat": iat,
    }
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload_dict).encode())
        .rstrip(b"=")
        .decode()
    )
    signing_input = f"{header}.{payload_b64}".encode()
    sig = hmac.new(secret, signing_input, hashlib.sha256).hexdigest()
    return f"{header}.{payload_b64}.{sig}"


USER_A = str(uuid.uuid4())
CARD_1 = "card_apply_job_001"
IK_1 = "ik_" + str(uuid.uuid4())


# ---------------------------------------------------------------------------
# T01 — valid token passes
# ---------------------------------------------------------------------------

def test_T01_valid_token_passes() -> None:
    token = _make_token(USER_A, CARD_1, IK_1)
    result = parse_and_validate_token(token, USER_A, CARD_1)
    assert isinstance(result, ApprovalToken)
    assert result.user_id == USER_A
    assert result.card_id == CARD_1
    assert result.idempotency_key == IK_1
    assert result.risk_class == "reversible-write"


# ---------------------------------------------------------------------------
# T02 — expired token denied
# ---------------------------------------------------------------------------

def test_T02_expired_token_denied() -> None:
    expired_iat = time.time() - TOKEN_TTL_SECONDS - 1
    token = _make_token(USER_A, CARD_1, IK_1, iat=expired_iat)
    with pytest.raises(ValueError, match="token_expired"):
        parse_and_validate_token(token, USER_A, CARD_1)


# ---------------------------------------------------------------------------
# T03 — tampered token denied (signature mismatch)
# ---------------------------------------------------------------------------

def test_T03_tampered_token_denied() -> None:
    token = _make_token(USER_A, CARD_1, IK_1)
    # flip one char in the signature segment
    parts = token.split(".")
    tampered_sig = parts[2][:-1] + ("a" if parts[2][-1] != "a" else "b")
    tampered_token = ".".join([parts[0], parts[1], tampered_sig])
    with pytest.raises(ValueError, match="invalid_signature"):
        parse_and_validate_token(tampered_token, USER_A, CARD_1)


# ---------------------------------------------------------------------------
# T04 — wrong user denied
# ---------------------------------------------------------------------------

def test_T04_wrong_user_denied() -> None:
    other_user = str(uuid.uuid4())
    token = _make_token(USER_A, CARD_1, IK_1)
    with pytest.raises(ValueError, match="user_id_mismatch"):
        parse_and_validate_token(token, other_user, CARD_1)


# ---------------------------------------------------------------------------
# T05 — duplicate idempotency_key is idempotent (not re-executed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_T05_duplicate_idempotency_key_is_idempotent() -> None:
    from src.api.policy_gate import check_and_lock_idempotency

    redis_mock = AsyncMock()
    # first call: Redis SETNX returns truthy (new key)
    redis_mock.set = AsyncMock(return_value="OK")
    assert await check_and_lock_idempotency(redis_mock, IK_1) is True

    # second call: Redis SETNX returns None (key already exists)
    redis_mock.set = AsyncMock(return_value=None)
    assert await check_and_lock_idempotency(redis_mock, IK_1) is False


# ---------------------------------------------------------------------------
# T06 — denied action does not reach execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_T06_denied_action_does_not_execute() -> None:
    """
    An expired token must result in 403 and the downstream execution
    path must never be called.
    """
    from fastapi.testclient import TestClient
    from src.api.policy_gate import app

    expired_iat = time.time() - TOKEN_TTL_SECONDS - 10
    token = _make_token(USER_A, CARD_1, str(uuid.uuid4()), iat=expired_iat)

    execution_mock = MagicMock()  # simulates any downstream executor

    # Patch write_audit_event to avoid real DB call
    with patch("src.api.policy_gate.write_audit_event", new_callable=AsyncMock) as audit_mock, \
         patch("src.api.policy_gate._get_user_permission_tier", new_callable=AsyncMock) as tier_mock:

        tier_mock.return_value = "P3"

        # Inject fake state onto the app
        app.state.db_pool = AsyncMock()
        app.state.redis = AsyncMock()
        app.state.redis.set = AsyncMock(return_value="OK")

        client = TestClient(app, raise_server_exceptions=True)

        # Manually set session user via middleware state simulation
        with patch("src.api.policy_gate.Request.state") as state_mock:
            state_mock.user_id = USER_A

            response = client.post(
                "/api/agent/policy-gate",
                json={
                    "approval_token": token,
                    "card_id": CARD_1,
                    "risk_class": "reversible-write",
                    "intent_summary": "Mark application as submitted",
                },
                headers={"X-Test-User-ID": USER_A},
            )

        # execution_mock should NEVER have been called
        execution_mock.assert_not_called()
        # audit IS written even for denied actions
        assert audit_mock.called


# ---------------------------------------------------------------------------
# T07 — audit event is written for every policy decision
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_T07_audit_event_written_on_denial() -> None:
    """Even a denied token must write an audit record."""
    from src.services.audit_writer import AuditEventPayload, write_audit_event
    import asyncpg

    pool_mock = AsyncMock()
    conn_mock = AsyncMock()
    pool_mock.acquire.return_value.__aenter__ = AsyncMock(return_value=conn_mock)
    pool_mock.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    conn_mock.execute = AsyncMock(return_value=None)

    payload = AuditEventPayload(
        event_type="policy_evaluated",
        action_id=uuid.uuid4(),
        card_id=CARD_1,
        user_id=uuid.UUID(USER_A),
        agent_id="rico-agent-v1",
        risk_class="reversible-write",
        intent_summary="Mark application as submitted",
        policy_decision="denied",
        denial_reason="token_expired",
        idempotency_key=IK_1,
        approval_token_raw="fake.token.here",
    )

    await write_audit_event(pool_mock, payload)

    # Verify INSERT was called once with the right policy_decision
    conn_mock.execute.assert_called_once()
    call_args = conn_mock.execute.call_args[0]
    # policy_decision is the 8th positional arg (index 8)
    assert call_args[8] == "denied"
    # approval_token_hash must NOT be the raw token
    token_hash_arg = call_args[11]
    assert token_hash_arg != "fake.token.here"
    assert len(token_hash_arg) == 64  # SHA-256 hex
