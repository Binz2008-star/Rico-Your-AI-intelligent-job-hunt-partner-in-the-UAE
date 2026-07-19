"""
tests/test_reasoning_layer.py
External reasoning layer (src/agent/reasoning + migration 047).

Covers:
  - ReasoningTrace lifecycle: evidence → contradictions → decision → outcome
  - Rendered execution state (the user-visible alternative to chain-of-thought)
  - Deterministic confidence derivation
  - Serialization roundtrip / resume-from-state (from_dict)
  - Bounded state (item caps, text clipping)
  - reasoning_repo fail-soft contract: never raises, 42P01 self-disable,
    RICO_REASONING_TRACES kill switch
  - AgentRuntime integration: every decision path persists a trace and
    attaches the reasoning summary; trace failures never affect the action
  - Content privacy: draft/why outcomes never store generated user content
  - GET /api/v1/agent/reasoning endpoints: auth, user scoping, 404

All users are synthetic; no live DB or third-party API is touched.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("ADMIN_EMAIL",    "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET",     "x" * 32)

from src.agent.reasoning import (  # noqa: E402
    STATUS_BLOCKED,
    STATUS_DECIDED,
    STATUS_EXECUTED,
    STATUS_GATHERING,
    ReasoningTrace,
)

_JOB = {
    "id":       "job-rl-001",
    "title":    "ESG Manager",
    "company":  "Acme Corp",
    "location": "Dubai, UAE",
    "link":     "https://example.com/job/rl-001",
    "score":    88,
    "match_reason":        "Strong HSE background",
    "profile_explanation": "Matches your senior sustainability experience.",
}

_USER = "reasoning-test@synthetic.local"


def _run(action, job=None, job_key="rl-key", source="test", dry_run=False, user_id=_USER):
    from src.agent.runtime import agent_runtime
    return agent_runtime.handle_action(
        user_id=user_id, action=action, job_key=job_key,
        job=job if job is not None else _JOB, source=source, dry_run=dry_run,
    )


def _patch_audit():
    return patch("src.agent.runtime.log_action")


def _patch_is_duplicate(value=False):
    return patch("src.agent.runtime.is_duplicate", return_value=value)


def _patch_save_trace(**kwargs):
    return patch("src.repositories.reasoning_repo.save_trace", **kwargs)


# ── ReasoningTrace: structured execution state ────────────────────────────────

class TestReasoningTrace:
    def test_lifecycle_gathering_to_executed(self):
        t = ReasoningTrace(goal="test goal", user_id=_USER)
        assert t.status == STATUS_GATHERING
        t.add_evidence("gate", "passed", verified=True)
        t.decide("do_thing", "evidence supports it")
        assert t.status == STATUS_DECIDED
        t.record_outcome(ok=True, summary="done")
        assert t.status == STATUS_EXECUTED
        assert t.outcome["ok"] is True

    def test_block_state_is_preserved(self):
        t = ReasoningTrace(goal="apply to job")
        t.decide("apply_job", "user asked")
        t.block("waiting for explicit user approval", next_action="surface card")
        assert t.status == STATUS_BLOCKED
        # Outcome on a blocked trace must not overwrite blocked status
        t.record_outcome(ok=True, summary="approval pending")
        assert t.status == STATUS_BLOCKED
        assert t.blocked_on == "waiting for explicit user approval"

    def test_every_conclusion_traceable_to_evidence(self):
        t = ReasoningTrace(goal="g")
        e1 = t.add_evidence("a", 1, verified=True)
        e2 = t.add_evidence("b", 2)
        d = t.decide("act", "because")
        assert set(d.evidence_ids) == {e1.id, e2.id}

    def test_confidence_penalizes_unresolved_conflicts(self):
        t = ReasoningTrace(goal="g")
        t.add_evidence("a", 1, verified=True)
        assert t.derived_confidence() == 1.0
        c = t.add_contradiction("evidence disagrees")
        assert t.derived_confidence() == 0.85
        t.resolve_contradiction(c.id, "verified against source")
        assert t.derived_confidence() == 1.0

    def test_confidence_penalizes_pending_verification_and_unverified_evidence(self):
        t = ReasoningTrace(goal="g")
        t.add_evidence("unverified fact", "x")           # -0.05
        t.require_verification("compare base blob")      # -0.20
        assert t.derived_confidence() == 0.75
        v = t.verifications[0]
        t.satisfy_verification(v.id, "e1")
        assert t.derived_confidence() == 0.95

    def test_confidence_floor(self):
        t = ReasoningTrace(goal="g")
        for i in range(10):
            t.add_contradiction(f"conflict {i}")
        assert t.derived_confidence() == 0.05

    def test_render_contains_all_visible_sections(self):
        t = ReasoningTrace(goal="Verify TASKS.md formatting")
        t.add_evidence("PR base SHA", "d5f96f1e", verified=True)
        t.add_evidence("Uploaded file", "present")
        t.assume("base branch is main")
        t.add_contradiction("Git checkout says A; uploaded file says B")
        t.require_verification("Compare base blob using git show")
        t.set_next_action("Compare base blob directly.")
        t.block("Waiting for evidence.")
        out = t.render()
        assert "Goal:" in out and "Verify TASKS.md formatting" in out
        assert "✓ PR base SHA: d5f96f1e" in out
        assert "• Uploaded file: present" in out
        assert "Assumptions:" in out
        assert "Conflicts:" in out
        assert "Required verification:" in out
        assert "Confidence:" in out and "%" in out
        assert "Next action:" in out
        assert "Blocked:" in out and "Waiting for evidence." in out

    def test_render_omits_empty_sections(self):
        t = ReasoningTrace(goal="g")
        out = t.render()
        assert "Conflicts:" not in out
        assert "Assumptions:" not in out
        assert "Blocked:" not in out
        assert "Outcome:" not in out
        assert "Confidence:" in out  # always shown

    def test_serialization_roundtrip(self):
        t = ReasoningTrace(goal="g", user_id=_USER, source="test")
        t.add_evidence("k", "v", source="s", verified=True)
        t.assume("hypothesis")
        t.add_contradiction("conflict", ["e1"])
        t.require_verification("check")
        t.decide("act", "why", confidence=0.9)
        t.record_outcome(ok=True, summary="done")
        d = t.to_dict()
        assert ReasoningTrace.from_dict(d).to_dict() == d

    def test_resume_from_state(self):
        # A trace persisted by one agent can be resumed by another
        t = ReasoningTrace(goal="multi-agent goal")
        t.add_evidence("step 1", "done", verified=True)
        resumed = ReasoningTrace.from_dict(t.to_dict())
        assert resumed.trace_id == t.trace_id
        resumed.add_evidence("step 2", "done", verified=True)
        resumed.decide("finish", "both steps verified")
        assert len(resumed.evidence) == 2
        assert resumed.decision.confidence == 1.0

    def test_state_is_bounded(self):
        t = ReasoningTrace(goal="x" * 2000)
        assert len(t.goal) == 500
        for i in range(60):
            t.add_evidence(f"e{i}", "v" * 2000)
        assert len(t.evidence) == 50
        assert t.dropped_items == 10
        assert len(t.evidence[0].value) == 300

    def test_summary_dict_shape(self):
        t = ReasoningTrace(goal="g")
        t.decide("act", "why")
        s = t.summary_dict()
        assert set(s) == {"trace_id", "goal", "status", "decision", "confidence", "state"}
        assert s["decision"] == "act"


# ── reasoning_repo: fail-soft persistence ─────────────────────────────────────

class TestReasoningRepoFailSoft:
    def setup_method(self):
        from src.repositories import reasoning_repo
        reasoning_repo._reset_state_for_tests()

    def _trace(self):
        t = ReasoningTrace(goal="g", user_id=_USER, source="test")
        t.decide("act", "why")
        return t

    def test_no_db_is_noop(self):
        from src.repositories import reasoning_repo
        with patch.object(reasoning_repo, "is_db_available", return_value=False):
            assert reasoning_repo.save_trace(self._trace()) is False
            assert reasoning_repo.list_recent(_USER) == []
            assert reasoning_repo.get_trace("x" * 32, _USER) is None

    def test_db_error_never_raises(self):
        from src.repositories import reasoning_repo
        conn = MagicMock()
        conn.cursor.side_effect = RuntimeError("boom")
        with patch.object(reasoning_repo, "is_db_available", return_value=True), \
             patch.object(reasoning_repo, "get_db_connection", return_value=conn):
            assert reasoning_repo.save_trace(self._trace()) is False
            assert reasoning_repo.list_recent(_USER) == []
            assert reasoning_repo.get_trace("x" * 32, _USER) is None

    def test_missing_table_self_disables(self):
        from src.repositories import reasoning_repo

        class MissingTable(Exception):
            pgcode = "42P01"

        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.execute.side_effect = MissingTable()
        with patch.object(reasoning_repo, "is_db_available", return_value=True), \
             patch.object(reasoning_repo, "get_db_connection", return_value=conn) as mock_conn:
            assert reasoning_repo.save_trace(self._trace()) is False
            assert mock_conn.call_count == 1
            # Second write is refused before touching the DB
            assert reasoning_repo.save_trace(self._trace()) is False
            assert mock_conn.call_count == 1

    def test_kill_switch(self):
        from src.repositories import reasoning_repo
        with patch.dict(os.environ, {"RICO_REASONING_TRACES": "false"}), \
             patch.object(reasoning_repo, "get_db_connection") as mock_conn:
            assert reasoning_repo.save_trace(self._trace()) is False
            assert reasoning_repo.list_recent(_USER) == []
            mock_conn.assert_not_called()

    def test_upsert_row_shape(self):
        from src.repositories import reasoning_repo
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        with patch.object(reasoning_repo, "is_db_available", return_value=True), \
             patch.object(reasoning_repo, "get_db_connection", return_value=conn):
            t = self._trace()
            assert reasoning_repo.save_trace(t) is True
        row = cursor.execute.call_args.args[1]
        assert row[0] == t.trace_id
        assert row[1] == _USER
        assert row[3] == STATUS_DECIDED
        assert row[4] == "act"
        conn.commit.assert_called_once()


# ── AgentRuntime integration ──────────────────────────────────────────────────

class TestRuntimeReasoningIntegration:
    def test_successful_action_persists_executed_trace(self):
        with _patch_audit(), _patch_is_duplicate(), _patch_save_trace() as mock_save:
            with patch("src.applications.mark_applied", return_value=True):
                result = _run("save")
        assert result.ok is True
        mock_save.assert_called_once()
        trace = mock_save.call_args.args[0]
        assert trace.status == STATUS_EXECUTED
        assert trace.outcome["ok"] is True
        assert trace.decision is not None
        assert trace.user_id == _USER
        # Idempotency and job resolution were recorded as evidence
        labels = [e.label for e in trace.evidence]
        assert "job" in labels
        assert "idempotency guard" in labels

    def test_reasoning_summary_attached_to_result(self):
        with _patch_audit(), _patch_is_duplicate(), _patch_save_trace():
            with patch("src.applications.mark_applied", return_value=True):
                result = _run("save")
        reasoning = result.data.get("reasoning")
        assert reasoning
        assert reasoning["trace_id"]
        assert reasoning["status"] == STATUS_EXECUTED
        assert reasoning["confidence"] == 1.0
        assert "Goal:" in reasoning["state"]
        assert "Evidence:" in reasoning["state"]

    def test_unknown_action_records_reject_decision(self):
        with _patch_audit(), _patch_save_trace() as mock_save:
            result = _run("hack_the_planet")
        assert result.ok is False
        trace = mock_save.call_args.args[0]
        assert trace.decision.action == "reject"
        assert trace.outcome["ok"] is False

    def test_duplicate_records_skip_decision(self):
        with _patch_audit(), _patch_is_duplicate(True), _patch_save_trace() as mock_save:
            result = _run("save")
        assert result.ok is True
        trace = mock_save.call_args.args[0]
        assert trace.decision.action == "skip_duplicate"
        labels = [e.label for e in trace.evidence]
        assert "idempotency guard" in labels

    def test_dry_run_records_dry_run_decision(self):
        with _patch_audit(), _patch_is_duplicate(), _patch_save_trace() as mock_save:
            result = _run("save", dry_run=True)
        assert result.ok is True and result.dry_run is True
        trace = mock_save.call_args.args[0]
        assert trace.decision.action.startswith("dry_run:")

    def test_trace_persistence_failure_never_affects_action(self):
        with _patch_audit(), _patch_is_duplicate(), \
             _patch_save_trace(side_effect=RuntimeError("db down")):
            with patch("src.applications.mark_applied", return_value=True):
                result = _run("save")
        assert result.ok is True

    def test_draft_outcome_never_stores_generated_content(self):
        secret_draft = "Dear Hiring Manager, please consider my unique profile."
        with _patch_audit(), _patch_is_duplicate(), _patch_save_trace() as mock_save:
            with patch("src.message_generator.generate_message", return_value=secret_draft):
                result = _run("draft")
        assert result.ok is True
        trace = mock_save.call_args.args[0]
        assert secret_draft not in str(trace.to_dict())
        assert trace.outcome["summary"] == "generated response delivered"


# ── API endpoints ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token

    token = create_access_token({"sub": _USER})
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", token)
    return tc


@pytest.fixture(scope="module")
def anon_client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    return TestClient(app, raise_server_exceptions=False)


class TestReasoningEndpoints:
    _LIST_URL = "/api/v1/agent/reasoning"

    def test_list_requires_auth(self, anon_client):
        assert anon_client.get(self._LIST_URL).status_code == 401

    def test_get_requires_auth(self, anon_client):
        assert anon_client.get(f"{self._LIST_URL}/abc123").status_code == 401

    def test_list_returns_user_scoped_summaries(self, client):
        rows = [{
            "trace_id": "a" * 32, "goal": "Execute user action 'save'",
            "status": "executed", "decision": "save_job", "confidence": 1.0,
            "source": "api", "created_at": None, "updated_at": None,
        }]
        with patch("src.repositories.reasoning_repo.list_recent", return_value=rows) as mock_list:
            r = client.get(self._LIST_URL)
        assert r.status_code == 200
        assert r.json() == {"traces": rows, "count": 1}
        assert mock_list.call_args.kwargs["user_id"] == _USER

    def test_get_returns_full_trace_with_rendered_state(self, client):
        t = ReasoningTrace(goal="Execute user action 'save'", user_id=_USER, source="api")
        t.add_evidence("idempotency guard", "no prior execution", verified=True)
        t.decide("save_job", "explicit user action")
        row = {
            "trace_id": t.trace_id, "goal": t.goal, "status": t.status,
            "decision": "save_job", "confidence": 1.0, "source": "api",
            "trace": t.to_dict(), "created_at": None, "updated_at": None,
        }
        with patch("src.repositories.reasoning_repo.get_trace", return_value=row) as mock_get:
            r = client.get(f"{self._LIST_URL}/{t.trace_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["trace_id"] == t.trace_id
        assert "Goal:" in body["state"]
        assert "✓ idempotency guard: no prior execution" in body["state"]
        assert mock_get.call_args.kwargs["user_id"] == _USER

    def test_get_unknown_or_foreign_trace_is_404(self, client):
        with patch("src.repositories.reasoning_repo.get_trace", return_value=None):
            r = client.get(f"{self._LIST_URL}/{'f' * 32}")
        assert r.status_code == 404
