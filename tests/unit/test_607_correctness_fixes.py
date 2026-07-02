"""tests/unit/test_607_correctness_fixes.py

Focused regression tests for the correctness fixes re-delivered from the
(closed) PR #607 after its CV ``run_in_executor`` hunk was dropped — that hunk
already landed on ``main`` via #609.

Covered fixes:
  1. src/scoring.py                 — hard-reject keyword matches as a whole
                                       word only, not as a bare title prefix.
  2. src/agent/runtime.py           — apply reply surfaces the tool's real
                                       status message instead of the static
                                       ``_REPLY["apply"]``.
  3. src/repositories/audit_repo.py — ``not_relevant`` is idempotency-enforced
                                       and the dedup primitive catches a repeat.
"""
from unittest.mock import patch


class TestScoringHardRejectFalsePositive:
    """A reject keyword must match as a whole word, not as a bare prefix."""

    @patch("src.scoring.get_hard_reject_keywords", return_value=["architect"])
    def test_prefix_share_is_not_hard_rejected(self, _kw, monkeypatch):
        monkeypatch.setenv("EXCLUDE_KEYWORDS", "")
        from src.scoring import score_job

        job = {
            "title": "Architecture Software Sales Engineer",
            "description": "Enterprise software sales role.",
        }
        score_job(job)
        # "Architecture..." shares the prefix "architect" but is not the word
        # "architect"; it must not be hard-rejected.
        assert job.get("hard_reject_reason") is None

    @patch("src.scoring.get_hard_reject_keywords", return_value=["architect"])
    def test_exact_reject_keyword_still_rejected(self, _kw, monkeypatch):
        monkeypatch.setenv("EXCLUDE_KEYWORDS", "")
        from src.scoring import score_job

        job = {"title": "Architect", "description": "Design buildings."}
        score = score_job(job)
        assert score == 0
        assert "architect" in (job.get("hard_reject_reason") or "")


class TestApplyReplyMessage:
    """Apply replies must surface the tool's real status message."""

    def test_apply_uses_status_message_when_present(self):
        from src.agent.runtime import AgentRuntime

        msg = AgentRuntime._build_message(
            "apply", True, {"message": "Approval required before applying."}, None
        )
        assert msg == "Approval required before applying."

    def test_apply_falls_back_to_static_reply_when_no_message(self):
        from src.agent.runtime import AgentRuntime, _REPLY

        msg = AgentRuntime._build_message("apply", True, {}, None)
        assert msg == _REPLY["apply"]

    def test_apply_failure_path_unchanged(self):
        from src.agent.runtime import AgentRuntime

        msg = AgentRuntime._build_message("apply", False, {}, "engine down")
        assert msg == "Action failed: engine down"

    def test_known_internal_error_code_is_mapped_not_leaked(self):
        # QA BUG #15: raw internal codes like no_apply_link_available must never
        # reach the chat UI — they are mapped to a user-safe message.
        from src.agent.runtime import AgentRuntime

        msg = AgentRuntime._build_message("apply", False, {}, "no_apply_link_available")
        assert "no_apply_link_available" not in msg
        assert "Action failed" not in msg
        assert msg  # non-empty, human-facing

    def test_unknown_error_still_raw_for_operators(self):
        # Regression guard: free-text/unknown errors keep the existing format.
        from src.agent.runtime import AgentRuntime

        assert (
            AgentRuntime._build_message("apply", False, {}, "engine down")
            == "Action failed: engine down"
        )


class TestNotRelevantIdempotency:
    """``not_relevant`` shares the negative-learning side effect with ``skip``,
    so it must be subject to idempotency enforcement."""

    def test_not_relevant_is_idempotent_action_type(self):
        from src.repositories.audit_repo import IDEMPOTENT_ACTION_TYPES

        assert "not_relevant" in IDEMPOTENT_ACTION_TYPES
        # Existing members must be preserved.
        assert {"apply", "skip", "save", "block"} <= IDEMPOTENT_ACTION_TYPES

    @patch("src.repositories.audit_repo.is_db_available", return_value=False)
    def test_repeated_not_relevant_action_id_is_duplicate(self, _db):
        from src.repositories.audit_repo import is_duplicate, log_action

        action_id = "test-not-relevant-dedup-0001"
        # First sighting: not a duplicate.
        assert is_duplicate(action_id) is False
        # Record a successful not_relevant action -> seeds the dedup cache.
        log_action(
            {
                "action_id": action_id,
                "action_type": "not_relevant",
                "result_status": "success",
            }
        )
        # Second sighting within the TTL window: now a duplicate.
        assert is_duplicate(action_id) is True
