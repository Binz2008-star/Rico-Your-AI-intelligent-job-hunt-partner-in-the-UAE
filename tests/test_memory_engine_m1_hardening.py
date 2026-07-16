"""
tests/test_memory_engine_m1_hardening.py

Hardening tests for the Career Memory Engine M1 (ADR-001), added by the
independent security audit of PR #1025. They cover gaps that the original
M1 suite did not exercise:

1. Value-level secret scan — the key filter (_EXCLUDED_KEY_RE) only inspects
   field NAMES; these tests prove secret/credential/PAN material is rejected
   even when it hides under an innocuous key, and that the sanctioned shadow
   payload is minimized (whole-write reject, never a trim).
2. Isolation / public-merge guard — a public:* session can never write under a
   real account's id, and the blocked merge is logged.
3. Failure containment — when the writer raises internally (DB error),
   agent_runtime.handle_action still returns the correct action result and the
   circuit breaker counts the failure.

Fully offline: the repository layer and RicoDB identity resolution are mocked.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

import src.services.memory_writer as mw
from src.services.memory_writer import MemoryWriter, _SHADOW_PAYLOAD_KEYS

NOW = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)

ACCOUNT_UUID = "11111111-1111-1111-1111-111111111111"
PUBLIC_UUID = "33333333-3333-3333-3333-333333333333"


def make_writer() -> MemoryWriter:
    """Fresh writer per test — isolated metrics and breaker state."""
    return MemoryWriter()


def event_kwargs(**overrides):
    base = dict(
        external_user_id="user@example.com",
        event_type="job_action.save",
        idempotency_key="k-1",
        occurred_at=NOW,
        actor="user",
        source="verified_event",
        confidence=1.0,
        payload={"action": "save", "title": "Ops Manager", "company": "Acme"},
        source_record_id="action_audit_log:abc123",
    )
    base.update(overrides)
    return base


def _bundle(uuid_value: str, external_id: str = "", email: str = ""):
    return {"id": uuid_value, "external_user_id": external_id, "email": email}


@pytest.fixture
def rico_db_mock():
    """RicoDB that resolves user@example.com to ACCOUNT_UUID."""
    with patch("src.rico_db.RicoDB") as cls:
        instance = cls.return_value
        instance.available = True
        instance.get_user_bundle.return_value = _bundle(
            ACCOUNT_UUID, external_id="ext-1", email="user@example.com"
        )
        yield instance


@pytest.fixture
def repo_mock():
    with patch("src.repositories.career_memory_repo.insert_event") as ins_event, \
         patch("src.repositories.career_memory_repo.insert_fact") as ins_fact, \
         patch("src.repositories.career_memory_repo.get_current_fact") as get_fact:
        ins_event.return_value = "written"
        ins_fact.return_value = "written"
        get_fact.return_value = None
        yield {"insert_event": ins_event, "insert_fact": ins_fact,
               "get_current_fact": get_fact}


@pytest.fixture(autouse=True)
def _enable_engine(monkeypatch):
    monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
    monkeypatch.delenv("RICO_MEMORY_ENGINE_KILL", raising=False)


# ── Task 1a: value-level secret scan (secret hidden under an innocuous key) ───

class TestValueLevelSecretScan:
    # Every key below is *not* matched by _EXCLUDED_KEY_RE, so only a
    # value-level scan can catch these — the exact gap this hardening closes.
    @pytest.mark.parametrize("payload,label", [
        ({"company": "sk-abcdefghij0123456789KLMNOP"}, "secret_key_prefix"),
        ({"company": "whsec_abcdefghij0123456789ABCD"}, "webhook_secret"),
        ({"title": "Bearer abcdefghijklmnop0123456789"}, "bearer_token"),
        ({"note": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9.SflKxwRJSMeKKF2QT4"}, "jwt"),
        ({"ref": "DE89370400440532013000"}, "iban"),
        ({"memo": "4111 1111 1111 1111"}, "card_number"),
        ({"blob": "AKIAIOSFODNN7EXAMPLEwJalrXUtnFEMIK7MDENGbPxRfiCYEX"}, "opaque_token"),
        ({"pem": "-----BEGIN RSA PRIVATE KEY-----\nMIIEabc"}, "private_key_block"),
        # Nested and list-embedded secrets are caught by the recursive walk.
        ({"meta": {"company": "sk-abcdefghij0123456789KLMNOP"}}, "secret_key_prefix"),
        ({"items": [{"company": "Acme"}, {"x": "4111111111111111"}]}, "card_number"),
    ])
    def test_secret_value_rejects_whole_write(
        self, payload, label, repo_mock, rico_db_mock
    ):
        writer = make_writer()
        result = writer.record_event(**event_kwargs(payload=payload))

        assert result.status == "rejected_excluded"
        repo_mock["insert_event"].assert_not_called()
        assert writer.metrics_snapshot()["rejected_excluded"] == 1

    def test_scan_labels_the_offending_path(self):
        writer = make_writer()
        offending = writer._scan_secret_values(
            {"meta": {"company": "sk-abcdefghij0123456789KLMNOP"}}
        )
        assert offending is not None
        assert offending.startswith("secret_key_prefix@")
        assert "meta.company" in offending

    def test_clean_career_values_still_write(self, repo_mock, rico_db_mock):
        """Real job-action fields (16-char hex job_key, human text) must pass —
        the value scan must not over-reject the sanctioned payload."""
        writer = make_writer()
        result = writer.record_event(**event_kwargs(payload={
            "action": "apply",
            "title": "Senior Data Engineer",
            "company": "Emirates Group",
            "job_key": "a1b2c3d4e5f60789",  # SHA-256[:16], the canonical shape
            "surface": "api",
        }))
        assert result.status == "written"

    def test_secret_in_fact_value_rejected(self, repo_mock, rico_db_mock):
        writer = make_writer()
        from src.services.memory_writer import MemoryWriteResult  # noqa: F401
        result = writer.record_fact(
            external_user_id="user@example.com",
            fact_key="identity.headline",  # innocuous key
            fact_class="replaceable",
            value="token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.SflKxwRJSMe",
            idempotency_key="f-secret",
            occurred_at=NOW,
            actor="user",
            source="user_stated",
            confidence=1.0,
            source_record_id="chat:msg-1",
        )
        assert result.status == "rejected_excluded"
        repo_mock["insert_fact"].assert_not_called()

    def test_booleans_and_short_numbers_are_not_secrets(self):
        writer = make_writer()
        assert writer._scan_secret_values({"a": True, "b": False, "n": 4, "y": 2026}) is None


# ── Task 1b: shadow payload minimization (reject, never trim) ─────────────────

class TestShadowPayloadMinimization:
    JOB = {"title": "Ops Manager", "company": "Acme", "id": "job-1"}

    def test_allowlist_is_exactly_the_sanctioned_fields(self):
        assert _SHADOW_PAYLOAD_KEYS == frozenset(
            {"action", "title", "company", "job_key", "surface"}
        )

    def test_shadow_payload_carries_only_allowlisted_keys(self, repo_mock, rico_db_mock):
        """Fails if a future edit ever widens the built shadow payload."""
        writer = make_writer()
        writer.record_job_action_shadow(
            external_user_id="user@example.com", action="apply", job=self.JOB,
            action_id="a1", surface="telegram", legacy_write_ok=True,
        )
        payload = repo_mock["insert_event"].call_args.kwargs["payload"]
        assert set(payload) == _SHADOW_PAYLOAD_KEYS

    def test_widened_payload_is_rejected_not_trimmed(
        self, monkeypatch, repo_mock, rico_db_mock
    ):
        """If the built payload ever exceeds the allowlist, the write is dropped
        whole — never silently trimmed. Simulated by narrowing the allowlist so
        the (unchanged) 5-key payload becomes 'wider' than sanctioned."""
        monkeypatch.setattr(mw, "_SHADOW_PAYLOAD_KEYS", frozenset({"action"}))
        writer = make_writer()

        writer.record_job_action_shadow(
            external_user_id="user@example.com", action="save", job=self.JOB,
            action_id="a1", surface="api", legacy_write_ok=True,
        )

        repo_mock["insert_event"].assert_not_called()
        assert writer.metrics_snapshot()["rejected_excluded"] == 1


# ── Task 2: isolation + public→account merge guard (via the shadow path) ──────

class TestIsolationAndPublicMerge:
    JOB = {"title": "Ops Manager", "company": "Acme", "id": "job-1"}

    def test_public_shadow_write_cannot_land_under_real_account(
        self, repo_mock, rico_db_mock, caplog
    ):
        """A public:* session resolving to anything but its own exact row (here
        a real account row) must be refused — the shadow write can never merge
        public activity into an account, and the refusal is logged."""
        rico_db_mock.get_user_bundle.return_value = _bundle(
            ACCOUNT_UUID, external_id="ext-1", email="user@example.com"
        )
        writer = make_writer()

        with caplog.at_level(logging.WARNING, logger="src.services.memory_writer"):
            writer.record_job_action_shadow(
                external_user_id="public:web-abc", action="save", job=self.JOB,
                action_id="a1", surface="public", legacy_write_ok=False,
            )

        repo_mock["insert_event"].assert_not_called()
        assert writer.metrics_snapshot()["skipped_no_account"] == 1
        assert any("memory_engine_public_merge_blocked" in r.message for r in caplog.records)

    def test_public_shadow_write_lands_on_its_own_row_only(self, repo_mock, rico_db_mock):
        rico_db_mock.get_user_bundle.return_value = _bundle(
            PUBLIC_UUID, external_id="public:web-abc"
        )
        writer = make_writer()

        writer.record_job_action_shadow(
            external_user_id="public:web-abc", action="save", job=self.JOB,
            action_id="a1", surface="public", legacy_write_ok=True,
        )

        assert repo_mock["insert_event"].call_args.kwargs["account_id"] == PUBLIC_UUID

    def test_write_is_keyed_to_resolved_uuid_not_external_identity(
        self, repo_mock, rico_db_mock
    ):
        """The row is keyed by the canonical UUID, never the email/external id."""
        writer = make_writer()
        writer.record_event(**event_kwargs(external_user_id="user@example.com"))

        account_id = repo_mock["insert_event"].call_args.kwargs["account_id"]
        assert account_id == ACCOUNT_UUID
        assert account_id != "user@example.com"


# ── Task 3: failure containment + breaker counting ───────────────────────────

class TestFailureContainment:
    JOB = {"title": "Ops Manager", "company": "Acme", "id": "job-1"}

    def test_record_event_absorbs_repo_error_into_failed_status(
        self, repo_mock, rico_db_mock
    ):
        """A DB failure never propagates out of the writer; it becomes a
        'failed' result and increments the breaker's failure counter."""
        repo_mock["insert_event"].side_effect = RuntimeError("db down")
        writer = make_writer()

        result = writer.record_event(**event_kwargs())  # must not raise

        assert result.status == "failed"
        assert writer.metrics_snapshot()["failed"] == 1

    def test_handle_action_result_unchanged_and_failure_counted_on_db_error(
        self, monkeypatch
    ):
        """End-to-end: an internal writer DB error leaves the action result
        untouched (M1 contract) while the real singleton counts the failure."""
        from src.services.memory_writer import memory_writer as singleton
        from src.agent.runtime import agent_runtime

        # Deterministic breaker state; measure the failure counter as a delta.
        with singleton._lock:
            singleton._consecutive_failures = 0
            singleton._breaker_open_until = 0.0
        before_failed = singleton.metrics_snapshot()["failed"]

        tool_result = MagicMock()
        tool_result.success = True
        tool_result.error = None
        tool_result.data = {}
        tool_def = MagicMock()
        tool_def.fn = MagicMock(return_value=tool_result)
        tool_def.fn.__signature__ = None

        bundle = _bundle(ACCOUNT_UUID, external_id="ext-1", email="user@example.com")

        with patch("src.agent.registry.tool_registry.get", return_value=tool_def), \
             patch("src.agent.runtime.is_duplicate", return_value=False), \
             patch("src.agent.runtime.log_action"), \
             patch("src.repositories.user_job_context_repo.record_interaction"), \
             patch("src.repositories.user_job_context_repo.set_lifecycle_status"), \
             patch("src.repositories.learning_repo.get_learning_repository"), \
             patch("src.services.career_memory.record_action", return_value=True), \
             patch("src.rico_db.RicoDB") as db_cls, \
             patch("src.repositories.career_memory_repo.insert_event",
                   side_effect=RuntimeError("db down")):
            db_cls.return_value.available = True
            db_cls.return_value.get_user_bundle.return_value = bundle

            result = agent_runtime.handle_action(
                user_id="user@example.com", action="save",
                job_key="job-1", job=dict(self.JOB), source="test",
            )

        # Action result is exactly what it would be with no engine at all.
        assert result.ok is True
        assert result.action == "save"
        assert result.error is None
        # The DB error was contained AND counted by the breaker.
        assert singleton.metrics_snapshot()["failed"] == before_failed + 1
