"""
tests/test_memory_engine_m1.py

Unit tests for the Career Memory Engine M1 (ADR-001): MemoryWriter policy —
feature flag, kill switch, circuit breaker, canonical identity, mandatory
provenance, exclusion filter, trust hierarchy, metrics/drift — and the
agent_runtime shadow-write contract (no user-visible behavior change).

Fully offline: the repository layer and RicoDB identity resolution are mocked.
Real-Postgres constraint/history/isolation behavior is covered separately in
tests/integration/test_career_memory_engine_postgres.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.services.memory_writer import (
    MemoryWriter,
    MemoryWriteRejected,
)

NOW = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)

ACCOUNT_UUID = "11111111-1111-1111-1111-111111111111"
OTHER_UUID = "22222222-2222-2222-2222-222222222222"
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


# ── Feature flag and kill switch ─────────────────────────────────────────────

class TestFlagAndKillSwitch:
    def test_disabled_by_default(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.delenv("RICO_MEMORY_ENGINE_ENABLED", raising=False)
        monkeypatch.delenv("RICO_MEMORY_ENGINE_KILL", raising=False)
        writer = make_writer()

        result = writer.record_event(**event_kwargs())

        assert result.status == "skipped_disabled"
        repo_mock["insert_event"].assert_not_called()
        assert writer.metrics_snapshot()["skipped_disabled"] == 1

    def test_enabled_flag_writes(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        writer = make_writer()

        result = writer.record_event(**event_kwargs())

        assert result.status == "written"
        assert result.account_id == ACCOUNT_UUID
        repo_mock["insert_event"].assert_called_once()

    def test_kill_switch_beats_enable_flag(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        monkeypatch.setenv("RICO_MEMORY_ENGINE_KILL", "true")
        writer = make_writer()

        result = writer.record_event(**event_kwargs())

        assert result.status == "skipped_disabled"
        repo_mock["insert_event"].assert_not_called()


# ── Circuit breaker ──────────────────────────────────────────────────────────

class TestCircuitBreaker:
    def test_breaker_opens_after_consecutive_failures(
        self, monkeypatch, repo_mock, rico_db_mock
    ):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        writer = make_writer()
        repo_mock["insert_event"].side_effect = RuntimeError("db down")

        for i in range(5):
            result = writer.record_event(**event_kwargs(idempotency_key=f"k-{i}"))
            assert result.status == "failed"

        # Breaker is now open — no further repo calls are attempted.
        result = writer.record_event(**event_kwargs(idempotency_key="k-after"))
        assert result.status == "skipped_breaker_open"
        assert repo_mock["insert_event"].call_count == 5

        metrics = writer.metrics_snapshot()
        assert metrics["failed"] == 5
        assert metrics["breaker_trips"] == 1
        assert metrics["skipped_breaker_open"] == 1

    def test_breaker_closes_after_cooldown(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        writer = make_writer()
        repo_mock["insert_event"].side_effect = RuntimeError("db down")
        for i in range(5):
            writer.record_event(**event_kwargs(idempotency_key=f"k-{i}"))

        # Simulate the cooldown having elapsed.
        writer._breaker_open_until = 0.0
        repo_mock["insert_event"].side_effect = None
        repo_mock["insert_event"].return_value = "written"

        result = writer.record_event(**event_kwargs(idempotency_key="k-recovered"))
        assert result.status == "written"

    def test_success_resets_failure_streak(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        writer = make_writer()

        repo_mock["insert_event"].side_effect = RuntimeError("blip")
        for i in range(4):
            writer.record_event(**event_kwargs(idempotency_key=f"k-{i}"))
        repo_mock["insert_event"].side_effect = None
        writer.record_event(**event_kwargs(idempotency_key="k-ok"))
        repo_mock["insert_event"].side_effect = RuntimeError("blip")
        result = writer.record_event(**event_kwargs(idempotency_key="k-x"))

        # 4 failures + success + 1 failure — streak was reset, breaker closed.
        assert result.status == "failed"
        assert writer.metrics_snapshot()["breaker_trips"] == 0


# ── Canonical identity (ADR §3) ──────────────────────────────────────────────

class TestCanonicalIdentity:
    def test_email_resolves_to_canonical_uuid(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        writer = make_writer()

        result = writer.record_event(**event_kwargs())

        assert result.account_id == ACCOUNT_UUID
        assert repo_mock["insert_event"].call_args.kwargs["account_id"] == ACCOUNT_UUID

    def test_unresolvable_identity_skips(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        rico_db_mock.get_user_bundle.return_value = None
        writer = make_writer()

        result = writer.record_event(**event_kwargs(external_user_id="ghost@example.com"))

        assert result.status == "skipped_no_account"
        repo_mock["insert_event"].assert_not_called()
        assert writer.metrics_snapshot()["skipped_no_account"] == 1

    def test_public_session_keys_to_its_own_row(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        rico_db_mock.get_user_bundle.return_value = _bundle(
            PUBLIC_UUID, external_id="public:web-abc"
        )
        writer = make_writer()

        result = writer.record_event(**event_kwargs(external_user_id="public:web-abc"))

        assert result.status == "written"
        assert result.account_id == PUBLIC_UUID

    def test_public_session_never_merges_into_account(
        self, monkeypatch, repo_mock, rico_db_mock
    ):
        """ADR §3: if resolution returns anything but the public session's own
        exact row, the write is refused — an implicit public→account merge must
        be impossible."""
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        rico_db_mock.get_user_bundle.return_value = _bundle(
            ACCOUNT_UUID, external_id="ext-1", email="user@example.com"
        )
        writer = make_writer()

        result = writer.record_event(**event_kwargs(external_user_id="public:web-abc"))

        assert result.status == "skipped_no_account"
        repo_mock["insert_event"].assert_not_called()

    def test_db_unavailable_skips(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        rico_db_mock.available = False
        writer = make_writer()

        result = writer.record_event(**event_kwargs())

        assert result.status == "skipped_no_account"


# ── Mandatory provenance (ADR §6) ────────────────────────────────────────────

class TestProvenance:
    @pytest.mark.parametrize("field,value", [
        ("source", "guesswork"),
        ("actor", "cron"),
        ("confidence", 1.5),
        ("confidence", -0.1),
        ("occurred_at", "2026-07-14"),
    ])
    def test_invalid_provenance_rejected(self, field, value):
        writer = make_writer()
        with pytest.raises(MemoryWriteRejected):
            writer.record_event(**event_kwargs(**{field: value}))

    def test_missing_source_pointer_rejected(self):
        writer = make_writer()
        with pytest.raises(MemoryWriteRejected):
            writer.record_event(**event_kwargs(source_record_id=None, source_uri=None))

    def test_source_uri_alone_satisfies_pointer_rule(
        self, monkeypatch, repo_mock, rico_db_mock
    ):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        writer = make_writer()
        result = writer.record_event(
            **event_kwargs(source_record_id=None, source_uri="rico://chat/msg/1")
        )
        assert result.status == "written"

    def test_validation_happens_even_when_disabled(self, monkeypatch):
        """Caller bugs surface in tests/CI regardless of the flag state."""
        monkeypatch.delenv("RICO_MEMORY_ENGINE_ENABLED", raising=False)
        writer = make_writer()
        with pytest.raises(MemoryWriteRejected):
            writer.record_event(**event_kwargs(source="guesswork"))


# ── Exclusion filter (ADR §8) ────────────────────────────────────────────────

class TestExclusionFilter:
    @pytest.mark.parametrize("payload", [
        {"api_key": "sk-123"},
        {"nested": {"authorization": "Bearer x"}},
        {"items": [{"card_number": "4111"}]},
        {"password": "hunter2"},
        {"billing": {"plan": "pro"}},
        {"document_text": "full CV body"},
    ])
    def test_excluded_payload_rejected(self, monkeypatch, repo_mock, rico_db_mock, payload):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        writer = make_writer()

        result = writer.record_event(**event_kwargs(payload=payload))

        assert result.status == "rejected_excluded"
        repo_mock["insert_event"].assert_not_called()

    def test_normal_career_payload_passes(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        writer = make_writer()

        result = writer.record_event(**event_kwargs(
            payload={"action": "apply", "title": "Engineer", "company": "Acme",
                     "job_key": "j1", "surface": "api"}
        ))

        assert result.status == "written"


# ── Facts: trust hierarchy and class rules (ADR §7) ──────────────────────────

def fact_kwargs(**overrides):
    base = dict(
        external_user_id="user@example.com",
        fact_key="identity.notice_period",
        fact_class="replaceable",
        value={"weeks": 4},
        idempotency_key="f-1",
        occurred_at=NOW,
        actor="user",
        source="user_stated",
        confidence=1.0,
        source_record_id="chat:msg-9",
    )
    base.update(overrides)
    return base


class TestFactPolicy:
    def test_lower_tier_never_supersedes_higher(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        repo_mock["get_current_fact"].return_value = {
            "id": 1, "value": {"weeks": 4}, "source": "user_stated",
            "confidence": 1.0, "effective_from": NOW,
        }
        writer = make_writer()

        result = writer.record_fact(**fact_kwargs(
            source="cv_extracted", confidence=0.8, idempotency_key="f-2"
        ))

        assert result.status == "rejected_lower_tier"
        repo_mock["insert_fact"].assert_not_called()

    def test_same_or_higher_tier_supersedes(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        repo_mock["get_current_fact"].return_value = {
            "id": 1, "value": {"weeks": 4}, "source": "cv_extracted",
            "confidence": 0.8, "effective_from": NOW,
        }
        writer = make_writer()

        result = writer.record_fact(**fact_kwargs(source="user_stated"))

        assert result.status == "written"
        repo_mock["insert_fact"].assert_called_once()

    def test_verified_only_rejects_unverified_source(
        self, monkeypatch, repo_mock, rico_db_mock
    ):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        writer = make_writer()

        result = writer.record_fact(**fact_kwargs(
            fact_key="identity.verified_email",
            fact_class="verified_only",
            source="user_stated",
        ))

        assert result.status == "rejected_unverified_tier"
        repo_mock["insert_fact"].assert_not_called()

    def test_invalid_fact_class_rejected(self):
        writer = make_writer()
        with pytest.raises(MemoryWriteRejected):
            writer.record_fact(**fact_kwargs(fact_class="mutable"))


# ── Shadow write + drift metrics ─────────────────────────────────────────────

class TestShadowWrite:
    JOB = {"title": "Ops Manager", "company": "Acme", "id": "job-1"}

    def test_shadow_disabled_is_noop(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.delenv("RICO_MEMORY_ENGINE_ENABLED", raising=False)
        writer = make_writer()

        writer.record_job_action_shadow(
            external_user_id="user@example.com", action="save", job=self.JOB,
            action_id="a1", surface="api", legacy_write_ok=True,
        )

        repo_mock["insert_event"].assert_not_called()
        # Drift is not measured while the engine is off.
        metrics = writer.metrics_snapshot()
        assert metrics["drift_engine_miss"] == 0
        assert metrics["drift_legacy_miss"] == 0

    def test_shadow_writes_event_with_audit_provenance(
        self, monkeypatch, repo_mock, rico_db_mock
    ):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        writer = make_writer()

        writer.record_job_action_shadow(
            external_user_id="user@example.com", action="apply", job=self.JOB,
            action_id="a1", surface="telegram", legacy_write_ok=True,
        )

        kwargs = repo_mock["insert_event"].call_args.kwargs
        assert kwargs["event_type"] == "job_action.apply"
        assert kwargs["source"] == "verified_event"
        assert kwargs["actor"] == "user"
        assert kwargs["source_record_id"] == "action_audit_log:a1"
        assert kwargs["idempotency_key"].startswith("job_action:a1:")
        assert kwargs["payload"]["company"] == "Acme"
        assert kwargs["payload"]["surface"] == "telegram"

    def test_non_memory_action_not_shadowed(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        writer = make_writer()

        writer.record_job_action_shadow(
            external_user_id="user@example.com", action="why", job=self.JOB,
            action_id="a1", surface="api", legacy_write_ok=False,
        )

        repo_mock["insert_event"].assert_not_called()

    def test_drift_engine_miss_counted(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        repo_mock["insert_event"].side_effect = RuntimeError("db down")
        writer = make_writer()

        writer.record_job_action_shadow(
            external_user_id="user@example.com", action="save", job=self.JOB,
            action_id="a1", surface="api", legacy_write_ok=True,
        )

        assert writer.metrics_snapshot()["drift_engine_miss"] == 1

    def test_drift_legacy_miss_counted(self, monkeypatch, repo_mock, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        writer = make_writer()

        writer.record_job_action_shadow(
            external_user_id="user@example.com", action="save", job=self.JOB,
            action_id="a1", surface="api", legacy_write_ok=False,
        )

        assert writer.metrics_snapshot()["drift_legacy_miss"] == 1

    def test_shadow_never_raises(self, monkeypatch, rico_db_mock):
        monkeypatch.setenv("RICO_MEMORY_ENGINE_ENABLED", "true")
        writer = make_writer()
        with patch.object(writer, "record_event", side_effect=RuntimeError("boom")):
            # Must not propagate.
            writer.record_job_action_shadow(
                external_user_id="user@example.com", action="save", job=self.JOB,
                action_id="a1", surface="api", legacy_write_ok=True,
            )


# ── agent_runtime integration: zero user-visible change ─────────────────────

class TestRuntimeIntegration:
    JOB = {"title": "Ops Manager", "company": "Acme", "id": "job-1"}

    def _run_action(self, monkeypatch, shadow_mock):
        """Run one successful 'save' through the real agent_runtime with the
        tool layer and persistence mocked out."""
        from src.agent.runtime import agent_runtime

        tool_result = MagicMock()
        tool_result.success = True
        tool_result.error = None
        tool_result.data = {}
        tool_def = MagicMock()
        tool_def.fn = MagicMock(return_value=tool_result)
        # Tool fn signature must accept one arg (the job dict).
        tool_def.fn.__signature__ = None

        with patch("src.agent.registry.tool_registry.get", return_value=tool_def), \
             patch("src.agent.runtime.is_duplicate", return_value=False), \
             patch("src.agent.runtime.log_action"), \
             patch("src.repositories.user_job_context_repo.record_interaction"), \
             patch("src.repositories.user_job_context_repo.set_lifecycle_status"), \
             patch("src.repositories.learning_repo.get_learning_repository"), \
             patch("src.services.career_memory.record_action", return_value=True), \
             patch("src.services.memory_writer.memory_writer.record_job_action_shadow",
                   shadow_mock):
            return agent_runtime.handle_action(
                user_id="user@example.com", action="save",
                job_key="job-1", job=dict(self.JOB), source="test",
            )

    def test_shadow_called_with_action_context(self, monkeypatch):
        shadow = MagicMock()
        result = self._run_action(monkeypatch, shadow)

        assert result.ok is True
        shadow.assert_called_once()
        kwargs = shadow.call_args.kwargs
        assert kwargs["external_user_id"] == "user@example.com"
        assert kwargs["action"] == "save"
        assert kwargs["legacy_write_ok"] is True
        assert kwargs["surface"] == "test"

    def test_result_identical_when_shadow_raises(self, monkeypatch):
        ok_result = self._run_action(monkeypatch, MagicMock())
        boom_result = self._run_action(
            monkeypatch, MagicMock(side_effect=RuntimeError("boom"))
        )

        # M1 contract: no user-visible behavior change from the shadow path.
        assert boom_result.ok == ok_result.ok
        assert boom_result.message == ok_result.message
        assert boom_result.action == ok_result.action
        assert boom_result.error == ok_result.error
