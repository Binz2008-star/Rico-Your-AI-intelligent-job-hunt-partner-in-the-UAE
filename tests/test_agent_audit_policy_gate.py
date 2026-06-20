"""
tests/test_agent_audit_policy_gate.py
Unit tests for:
  - src/services/audit_writer.py  (append-only event writer)
  - src/api/policy_gate.py        (approval token validation + policy gate)

Tests do NOT require a production DB — all DB calls are mocked or DB is
reported as unavailable so the code falls through to the structured-log path.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Required env vars so imports don't explode
os.environ.setdefault("JWT_SECRET",                 "x" * 32)
os.environ.setdefault("ADMIN_EMAIL",                "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD",             "TestPass123")
os.environ.setdefault("RICO_APPROVAL_HMAC_SECRET",  "test-hmac-secret-32chars-padded!!")

_UTC = timezone.utc

# ── Helpers ───────────────────────────────────────────────────────────────────

def _no_db():
    """Patch is_db_available to return False (no-DB path)."""
    return patch("src.services.audit_writer.is_db_available", return_value=False)


def _no_db_gate():
    """Patch is_db_available inside policy_gate to return False."""
    return patch("src.api.policy_gate.is_db_available", return_value=False)


def _make_req(
    *,
    user_id="user-001",
    card_id="card-abc",
    idempotency_key="idem-001",
    action_type="save",
    risk_class="low",
    permission_level="write",
    approval_token_id=None,
    hmac_signature=None,
):
    from src.api.policy_gate import ApprovalRequest, compute_hmac
    req = ApprovalRequest(
        user_id=user_id,
        card_id=card_id,
        idempotency_key=idempotency_key,
        action_type=action_type,
        risk_class=risk_class,
        permission_level=permission_level,
        approval_token_id=approval_token_id or "tok-" + idempotency_key,
        hmac_signature="placeholder",
    )
    # compute real HMAC then set it (or override with a bad value)
    if hmac_signature is None:
        req.hmac_signature = compute_hmac(req)
    else:
        req.hmac_signature = hmac_signature
    return req


# ── audit_writer tests ────────────────────────────────────────────────────────

class TestAuditWriterNoDB:
    """Audit writer falls back to structured logging when DB unavailable."""

    def test_write_event_no_db_emits_log(self):
        from src.services.audit_writer import AuditEvent, write_event
        event = AuditEvent(
            correlation_id="corr-1",
            idempotency_key="idem-1",
            user_id="user-1",
            event_type="action_created",
            action_type="save",
        )
        with _no_db():
            with patch("src.services.audit_writer.logger") as mock_log:
                write_event(event)
        mock_log.info.assert_called_once()
        args = mock_log.info.call_args[0]
        assert "action_created" in args[0] or "action_created" in str(args)

    def test_unknown_event_type_raises(self):
        from src.services.audit_writer import AuditEvent, write_event
        event = AuditEvent(
            correlation_id="corr-x",
            idempotency_key="idem-x",
            user_id="user-x",
            event_type="not_a_real_event",
        )
        with _no_db():
            with pytest.raises(ValueError, match="Unknown event_type"):
                write_event(event)

    def test_write_event_uses_only_insert(self):
        """audit_writer must never send an UPDATE SQL statement to agent_audit_events."""
        from src.services import audit_writer
        import inspect
        source = inspect.getsource(audit_writer)
        # No SQL UPDATE targeting the audit events table
        assert "UPDATE agent_audit_events" not in source, \
            "audit_writer must not UPDATE agent_audit_events"
        # The writer must contain INSERT
        assert "INSERT INTO agent_audit_events" in source


class TestAuditWriterWithDB:
    """audit_writer DB path inserts correctly and handles errors."""

    def _mock_conn(self):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return conn, cur

    def test_db_insert_called_with_insert_sql(self):
        from src.services.audit_writer import AuditEvent, write_event
        event = AuditEvent(
            correlation_id="corr-db-1",
            idempotency_key="idem-db-1",
            user_id="user-db-1",
            event_type="policy_evaluated",
            action_type="apply",
        )
        conn, cur = self._mock_conn()
        with patch("src.services.audit_writer.is_db_available", return_value=True):
            with patch("src.services.audit_writer.get_db_connection", return_value=conn):
                write_event(event)

        assert cur.execute.called
        sql_called = cur.execute.call_args[0][0]
        assert "INSERT INTO agent_audit_events" in sql_called
        assert "UPDATE" not in sql_called
        conn.commit.assert_called_once()

    def test_db_insert_error_raises_audit_write_error(self):
        from src.services.audit_writer import AuditEvent, AuditWriteError, write_event
        event = AuditEvent(
            correlation_id="corr-err",
            idempotency_key="idem-err",
            user_id="user-err",
            event_type="action_created",
        )
        conn, cur = self._mock_conn()
        cur.execute.side_effect = Exception("DB exploded")
        with patch("src.services.audit_writer.is_db_available", return_value=True):
            with patch("src.services.audit_writer.get_db_connection", return_value=conn):
                with pytest.raises(AuditWriteError):
                    write_event(event)


# ── policy_gate: token validation tests ──────────────────────────────────────

class TestTokenValidation:
    """Valid token passes; various invalid tokens are rejected."""

    def _evaluate_no_db(self, req):
        from src.api.policy_gate import evaluate
        with _no_db_gate():
            with patch("src.services.audit_writer.is_db_available", return_value=False):
                return evaluate(req)

    def test_valid_token_passes(self):
        req = _make_req()
        result = self._evaluate_no_db(req)
        assert result.allowed is True
        assert result.policy_decision == "allowed"

    def test_tampered_token_denied(self):
        req = _make_req(hmac_signature="000000000000000000000000000000000000000000000000000000000000dead")
        result = self._evaluate_no_db(req)
        assert result.allowed is False
        assert result.error_code == "INVALID_SIGNATURE"

    def test_risk_class_higher_than_permission_tier_denied(self):
        # "read" tier only allows "low" risk; "high" must be denied
        req = _make_req(risk_class="high", permission_level="read")
        result = self._evaluate_no_db(req)
        assert result.allowed is False
        assert result.error_code == "RISK_EXCEEDS_TIER"

    def test_critical_risk_denied_for_write_tier(self):
        req = _make_req(risk_class="critical", permission_level="write")
        result = self._evaluate_no_db(req)
        assert result.allowed is False
        assert result.error_code == "RISK_EXCEEDS_TIER"

    def test_critical_risk_allowed_for_irreversible_tier(self):
        req = _make_req(risk_class="critical", permission_level="irreversible")
        result = self._evaluate_no_db(req)
        assert result.allowed is True

    def _db_validate_evaluate(self, req, token_row):
        """
        Helper: run evaluate() with DB available.
        - Idempotency check (first get_db_connection call) returns no prior decision.
        - Token validation (second call) returns token_row.
        - Mark-token-used (third call) is a no-op MagicMock.
        """
        from src.api.policy_gate import evaluate

        def _conn_factory():
            conn = MagicMock()
            cur = MagicMock()
            conn.cursor.return_value.__enter__ = lambda s: cur
            conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            return conn, cur

        idem_conn, idem_cur = _conn_factory()
        idem_cur.fetchone.return_value = None       # no prior decision

        token_conn, token_cur = _conn_factory()
        token_cur.fetchone.return_value = token_row # token DB row

        mark_conn, _ = _conn_factory()              # mark-token-used (UPDATE on tokens table)

        call_count = []
        conns = [idem_conn, token_conn, mark_conn]

        def get_conn():
            idx = len(call_count)
            call_count.append(idx)
            return conns[idx] if idx < len(conns) else MagicMock()

        with patch("src.api.policy_gate.is_db_available", return_value=True):
            with patch("src.api.policy_gate.get_db_connection", side_effect=get_conn):
                with patch("src.services.audit_writer.is_db_available", return_value=False):
                    return evaluate(req)

    def test_wrong_user_denied(self):
        req = _make_req(user_id="user-A")
        token_row = (
            "user-B",         # db_user  ← mismatch
            req.card_id,
            req.idempotency_key,
            req.risk_class,
            req.permission_level,
            datetime.now(_UTC) + timedelta(hours=1),
            None,
            False,
        )
        result = self._db_validate_evaluate(req, token_row)
        assert result.allowed is False
        assert result.error_code == "USER_MISMATCH"

    def test_wrong_card_id_denied(self):
        req = _make_req(card_id="card-real")
        token_row = (
            req.user_id,
            "card-WRONG",     # ← mismatch
            req.idempotency_key,
            req.risk_class,
            req.permission_level,
            datetime.now(_UTC) + timedelta(hours=1),
            None,
            False,
        )
        result = self._db_validate_evaluate(req, token_row)
        assert result.allowed is False
        assert result.error_code == "CARD_MISMATCH"

    def test_expired_token_denied(self):
        req = _make_req()
        token_row = (
            req.user_id,
            req.card_id,
            req.idempotency_key,
            req.risk_class,
            req.permission_level,
            datetime.now(_UTC) - timedelta(seconds=1),  # ← expired
            None,
            False,
        )
        result = self._db_validate_evaluate(req, token_row)
        assert result.allowed is False
        assert result.error_code == "TOKEN_EXPIRED"

    def test_already_used_token_denied(self):
        req = _make_req()
        token_row = (
            req.user_id,
            req.card_id,
            req.idempotency_key,
            req.risk_class,
            req.permission_level,
            datetime.now(_UTC) + timedelta(hours=1),
            datetime.now(_UTC) - timedelta(minutes=5),  # ← used_at set
            False,
        )
        result = self._db_validate_evaluate(req, token_row)
        assert result.allowed is False
        assert result.error_code == "TOKEN_ALREADY_USED"

    def test_invalidated_token_denied(self):
        req = _make_req()
        token_row = (
            req.user_id,
            req.card_id,
            req.idempotency_key,
            req.risk_class,
            req.permission_level,
            datetime.now(_UTC) + timedelta(hours=1),
            None,
            True,   # ← invalidated
        )
        result = self._db_validate_evaluate(req, token_row)
        assert result.allowed is False
        assert result.error_code == "TOKEN_INVALIDATED"


# ── policy_gate: idempotency tests ────────────────────────────────────────────

class TestIdempotency:
    """Duplicate idempotency_key does not execute twice."""

    def test_duplicate_idempotency_key_returns_cached_decision(self):
        from src.api.policy_gate import evaluate

        req = _make_req(idempotency_key="idem-dup-1")

        # Simulate DB returning an existing approval_granted decision
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = ("allowed",)  # existing decision
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.policy_gate.is_db_available", return_value=True):
            with patch("src.api.policy_gate.get_db_connection", return_value=conn):
                with patch("src.services.audit_writer.is_db_available", return_value=False):
                    result = evaluate(req)

        # Returns the cached decision without re-evaluating
        assert result.idempotency_key == "idem-dup-1"
        assert result.policy_decision == "allowed"
        assert "Duplicate" in result.reason

    def test_duplicate_denied_idempotency_key_stays_denied(self):
        from src.api.policy_gate import evaluate

        req = _make_req(idempotency_key="idem-dup-2")
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = ("denied",)
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.policy_gate.is_db_available", return_value=True):
            with patch("src.api.policy_gate.get_db_connection", return_value=conn):
                with patch("src.services.audit_writer.is_db_available", return_value=False):
                    result = evaluate(req)

        assert result.allowed is False
        assert result.error_code == "IDEMPOTENCY_REPLAY"


# ── policy_gate: audit event sequence tests ───────────────────────────────────

class TestAuditEventSequence:
    """Correct events are written in the correct order."""

    def test_allowed_flow_writes_created_evaluated_granted(self):
        from src.api.policy_gate import evaluate
        from src.services import audit_writer

        req = _make_req()
        written: list = []

        def capture_write(event):
            written.append(event.event_type)

        with _no_db_gate():
            with patch("src.api.policy_gate.write_event", side_effect=capture_write):
                evaluate(req)

        assert written[0] == "action_created"
        assert written[1] == "policy_evaluated"
        assert written[2] == "approval_granted"

    def test_denied_flow_writes_created_evaluated_denied(self):
        from src.api.policy_gate import evaluate

        req = _make_req(hmac_signature="badhash" + "0" * 57)
        written: list = []

        def capture_write(event):
            written.append(event.event_type)

        with _no_db_gate():
            with patch("src.api.policy_gate.write_event", side_effect=capture_write):
                evaluate(req)

        assert written[0] == "action_created"
        assert written[1] == "policy_evaluated"
        assert written[2] == "approval_denied"

    def test_denied_action_does_not_execute(self):
        """A side-effecting callable must NOT be called when policy denies."""
        from src.api.policy_gate import evaluate

        req = _make_req(hmac_signature="bad" + "0" * 61)
        side_effect_called = []

        def fake_side_effect():
            side_effect_called.append(True)

        with _no_db_gate():
            with patch("src.services.audit_writer.is_db_available", return_value=False):
                result = evaluate(req)

        # Caller should check result.allowed before calling side effects
        if not result.allowed:
            pass  # side effect intentionally not called
        else:
            fake_side_effect()

        assert result.allowed is False
        assert len(side_effect_called) == 0

    def test_no_update_in_audit_events_table(self):
        """DB trigger blocks UPDATE; ensure our code never sends UPDATE to agent_audit_events."""
        import inspect
        from src.services import audit_writer

        source = inspect.getsource(audit_writer)
        # No raw SQL UPDATE targeting agent_audit_events
        assert "UPDATE agent_audit_events" not in source


# ── HMAC secret env var enforcement ──────────────────────────────────────────

class TestHmacSecretEnforcement:
    def test_missing_hmac_secret_raises_runtime_error(self):
        from src.api.policy_gate import _hmac_secret

        with patch.dict(os.environ, {"RICO_APPROVAL_HMAC_SECRET": ""}):
            with pytest.raises(RuntimeError, match="RICO_APPROVAL_HMAC_SECRET"):
                _hmac_secret()
