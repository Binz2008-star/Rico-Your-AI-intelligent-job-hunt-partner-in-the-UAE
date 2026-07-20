"""Regression: /agent/chat idempotency is scoped per acting user.

The orchestrator dedups direct job actions via audit_repo.is_duplicate, whose
store is keyed on action_id only. The client-supplied action_id comes from
response_builder._deterministic_action_id = sha256(action_type:link) — it has NO
user in it — so two different users acting on the same job link shared one id.
An unscoped global dedup then let one user's action suppress another user's
identical action ("Duplicate action …"). The fix folds the acting user into the
idempotency key inside the orchestrator (mirroring agent_runtime's user-scoped
scheme), so cross-user collisions are impossible while same-user double-clicks
still dedup.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import src.agent.orchestrator.orchestrator as orch
from src.agent.orchestrator.orchestrator import _user_scoped_action_id, process
from src.schemas.agent import AgentAction, ToolExecutionResult


def test_scoped_id_differs_across_users_same_job():
    a = AgentAction(action_id="linkhash", type="save", label="Save", job_id="job-1")
    id_user_a = _user_scoped_action_id("alice@x.com", a)
    id_user_b = _user_scoped_action_id("bob@x.com", a)
    assert id_user_a != id_user_b


def test_scoped_id_stable_for_same_user_and_job():
    a1 = AgentAction(action_id="linkhash", type="save", label="Save", job_id="job-1")
    a2 = AgentAction(action_id="linkhash", type="save", label="Save", job_id="job-1")
    assert _user_scoped_action_id("alice@x.com", a1) == _user_scoped_action_id(
        "alice@x.com", a2
    )


def _fake_tool():
    tool = MagicMock()
    tool.fn = lambda job: ToolExecutionResult(
        success=True, tool_name="save_job", data={"saved": True}
    )
    return tool


def _new_action():
    # Same client-supplied (link-derived) id and job for both users — the
    # collision the fix targets.
    return AgentAction(
        action_id="sha256linkhash", type="save", label="Save", job_id="job-42"
    )


class _FakeDedupStore:
    def __init__(self):
        self.seen = set()

    def is_duplicate(self, action_id):
        return action_id in self.seen

    def log_action(self, log):
        if log.get("result_status") in ("success", "duplicate"):
            self.seen.add(log.get("action_id"))


def _run(action, user_email):
    store = _FAKE
    with patch.object(orch, "is_duplicate", store.is_duplicate), patch.object(
        orch, "log_action", store.log_action
    ), patch.object(orch.tool_registry, "get", return_value=_fake_tool()):
        return process(message="", action=action, user_email=user_email)


_FAKE = _FakeDedupStore()


def test_same_user_second_action_is_deduped():
    global _FAKE
    _FAKE = _FakeDedupStore()
    first = _run(_new_action(), "alice@x.com")
    second = _run(_new_action(), "alice@x.com")
    # First succeeds, identical repeat by the same user is rejected as duplicate.
    assert not _is_duplicate_response(first)
    assert _is_duplicate_response(second)


def test_other_user_same_job_is_not_deduped():
    global _FAKE
    _FAKE = _FakeDedupStore()
    a = _run(_new_action(), "alice@x.com")   # Alice acts first
    b = _run(_new_action(), "bob@x.com")     # Bob acts on the SAME job/link
    assert not _is_duplicate_response(a)
    # The cross-user fix: Bob's action must NOT be suppressed by Alice's.
    assert not _is_duplicate_response(b)


def _is_duplicate_response(response) -> bool:
    """A duplicate rejection surfaces as an error component / message."""
    text = ""
    for comp in getattr(response, "components", []) or []:
        data = getattr(comp, "data", {}) or {}
        text += " ".join(str(v) for v in data.values())
    text += str(getattr(response, "message", "") or "")
    return "Duplicate action" in text or "already executed" in text
