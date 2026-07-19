"""Analytics emitters v1 (owner gate: minimal wiring, two events).

Pins the emitter contracts:

1. FAIL-SOFT — emitters never raise, even when the foundation itself throws;
   the runtime action path and the chat finalize path are unaffected.
2. NO PII / NO FREE TEXT — emitted properties are exactly the allowlisted
   token/count set; the emitter signatures have no parameter that could carry
   message text, CV text, or a search query.
3. SCOPE — authenticated users only in v1: ``public:`` guest sessions and
   missing identities emit nothing.
4. WIRING — runtime.handle_action emits job_action on success only;
   _finalize emits search_performed for job_matches responses only.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.services import analytics_emitters as em

_JOB = {
    "id": "job-an-001",
    "title": "ESG Manager",
    "company": "Acme Corp",
    "location": "Dubai, UAE",
    "link": "https://example.com/job/an-001",
    "score": 88,
}


# ── 1+2. Emitter-level contracts ─────────────────────────────────────────────

def test_job_action_emits_exact_allowlisted_payload():
    with patch("src.repositories.analytics_events_repo.record_event") as rec:
        em.emit_job_action("user@x.com", "save")
    rec.assert_called_once()
    args, kwargs = rec.call_args
    assert args == ("job_action",)
    assert kwargs["user_id"] == "user@x.com"
    assert kwargs["surface"] == "command"
    assert kwargs["properties"] == {"action": "save"}  # nothing else — ever


def test_search_emits_counts_only_never_query_text():
    with patch("src.repositories.analytics_events_repo.record_event") as rec:
        em.emit_search_performed("user@x.com", 7)
    args, kwargs = rec.call_args
    assert args == ("search_performed",)
    assert kwargs["properties"] == {"surface": "command", "results_count": 7}


def test_emitter_interfaces_expose_no_free_text_path():
    """Owner review pin: NO emitter parameter may carry caller-supplied text.
    search has no string parameter at all (surface fixed internally); action
    is constrained to the explicit _ALLOWED_ACTIONS set below."""
    import inspect
    assert set(inspect.signature(em.emit_search_performed).parameters) == {
        "user_id", "results_count",
    }
    assert set(inspect.signature(em.emit_job_action).parameters) == {
        "user_id", "action",
    }
    assert em._ALLOWED_ACTIONS == {"apply", "save", "skip", "block", "not_relevant"}


def test_unapproved_action_values_are_dropped_not_recorded():
    """Free text or unknown tokens passed as `action` never reach the store."""
    with patch("src.repositories.analytics_events_repo.record_event") as rec:
        em.emit_job_action("user@x.com", "find me a job at ACME please")
        em.emit_job_action("user@x.com", "why")
        em.emit_job_action("user@x.com", "")
        em.emit_job_action("user@x.com", None)
        em.emit_job_action("user@x.com", "SAVE")  # not coerced — exact set only
    assert not rec.called


def test_emitters_never_raise_when_foundation_throws():
    with patch("src.repositories.analytics_events_repo.record_event",
               side_effect=RuntimeError("boom")):
        em.emit_job_action("user@x.com", "save")          # must not raise
        em.emit_search_performed("user@x.com", 3)          # must not raise


# ── 3. v1 scope: authenticated only ──────────────────────────────────────────

def test_public_guest_sessions_and_missing_identity_emit_nothing():
    with patch("src.repositories.analytics_events_repo.record_event") as rec:
        em.emit_job_action("public:sid-123", "save")
        em.emit_job_action(None, "save")
        em.emit_job_action("   ", "save")
        em.emit_search_performed("public:sid-123", 5)
        em.emit_search_performed(None, 5)
    assert not rec.called


# ── 4. Wiring: runtime handle_action ─────────────────────────────────────────

def _run_action(action="save"):
    from src.agent.runtime import agent_runtime
    with patch("src.agent.runtime.log_action"), \
         patch("src.agent.runtime.is_duplicate", return_value=False):
        return agent_runtime.handle_action(
            user_id="user-analytics-test",
            action=action,
            job_key=f"an-key-{action}",
            job=_JOB,
            source="test",
        )


def test_runtime_success_emits_job_action():
    with patch("src.services.analytics_emitters.emit_job_action") as emit:
        result = _run_action("save")
    assert result.ok is True
    emit.assert_called_once_with("user-analytics-test", "save")


def test_runtime_result_unaffected_when_emitter_raises():
    with patch("src.services.analytics_emitters.emit_job_action",
               side_effect=RuntimeError("emitter bug")):
        result = _run_action("save")
    assert result.ok is True  # analytics can never break the action


# ── 4. Wiring: chat _finalize ────────────────────────────────────────────────

def _finalize(response, profile):
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI.__new__(RicoChatAPI)  # skip heavy __init__
    with patch.object(RicoChatAPI, "_get_openai_agent", return_value=MagicMock(model="m")):
        return api._finalize(response, "test", profile=profile)


def test_finalize_emits_search_performed_for_job_matches():
    profile = MagicMock()
    profile.user_id = "user@x.com"
    with patch("src.services.analytics_emitters.emit_search_performed") as emit:
        out = _finalize({"type": "job_matches", "matches": [{}, {}, {}]}, profile)
    emit.assert_called_once_with("user@x.com", 3)
    assert out["type"] == "job_matches"


def test_finalize_does_not_emit_for_other_response_types():
    with patch("src.services.analytics_emitters.emit_search_performed") as emit:
        _finalize({"type": "chat", "matches": []}, MagicMock(user_id="u@x.com"))
    assert not emit.called


def test_finalize_response_unaffected_when_emitter_raises():
    profile = MagicMock()
    profile.user_id = "user@x.com"
    with patch("src.services.analytics_emitters.emit_search_performed",
               side_effect=RuntimeError("emitter bug")):
        out = _finalize({"type": "job_matches", "matches": [{}]}, profile)
    assert out["type"] == "job_matches"  # chat response never broken
