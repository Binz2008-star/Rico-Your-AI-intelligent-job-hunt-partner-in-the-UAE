"""
tests/test_agentic_ui_composer.py
Unit tests for src/services/agentic_ui_composer.compose().

compose() returns a plain dict (serialized from RicoAgenticUi) or None.
Pure Pydantic/domain tests — no HTTP, no database, no external services.

PR-C additions: response-type–based action card injection tests.
"""
from __future__ import annotations

import os
import sys

import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "x" * 32)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_result(**data_kwargs):
    """Build a minimal stub that looks like RuntimeResult."""
    class _Stub:
        data = data_kwargs
    return _Stub()


def _action_ids(result: dict | None) -> list[str]:
    if result is None:
        return []
    return [a["id"] for a in result.get("actions", [])]


def _sample_permission_request() -> dict:
    return {
        "id": "perm-test-abc123",
        "title": "Apply to Risk Manager",
        "summary": "Rico will submit your application on your behalf.",
        "risk_level": "high",
        "data_used": ["Your CV", "Your contact details"],
        "effects": ["Application submitted for Risk Manager at Gulf Corp"],
        "approve_action": {
            "id": "approve-001",
            "label": "Apply now",
            "kind": "approve",
            "impact": "high",
            "requires_confirmation": False,
            "endpoint": "/api/v1/rico/actions/execute",
            "payload": {
                "permission_id": "perm-test-abc123",
                "action": "apply",
                "job_key": "risk-manager-gulf-corp",
            },
        },
        "cancel_action": {
            "id": "cancel-001",
            "label": "Cancel",
            "kind": "cancel",
            "impact": "low",
            "requires_confirmation": False,
            "payload": {},
        },
    }


# ── Original runtime-result tests (updated for dict return type) ──────────────

class TestAgenticUiComposer:
    def test_none_result_returns_none(self):
        from src.services.agentic_ui_composer import compose
        assert compose(None) is None

    def test_empty_data_returns_none(self):
        from src.services.agentic_ui_composer import compose
        assert compose(_make_result()) is None

    def test_unknown_data_keys_return_none(self):
        from src.services.agentic_ui_composer import compose
        assert compose(_make_result(unknown_key="hello", another=42)) is None

    def test_permission_request_maps_to_agentic_ui(self):
        from src.services.agentic_ui_composer import compose
        result = _make_result(permission_request=_sample_permission_request())
        ui = compose(result)
        assert ui is not None
        assert isinstance(ui, dict)
        assert "permission_request" in ui
        assert ui["permission_request"]["id"] == "perm-test-abc123"
        assert ui["permission_request"]["risk_level"] == "high"

    def test_permission_request_approve_action_preserved(self):
        from src.services.agentic_ui_composer import compose
        result = _make_result(permission_request=_sample_permission_request())
        ui = compose(result)
        assert ui["permission_request"]["approve_action"]["kind"] == "approve"
        assert ui["permission_request"]["approve_action"]["endpoint"] == "/api/v1/rico/actions/execute"

    def test_empty_actions_list_returns_none(self):
        """An empty actions list carries no UI artifacts — skip it."""
        from src.services.agentic_ui_composer import compose
        assert compose(_make_result(actions=[])) is None

    def test_actions_list_maps_to_agentic_ui(self):
        from src.services.agentic_ui_composer import compose
        actions = [
            {
                "id": "act-001",
                "label": "Save",
                "kind": "chat_continue",
                "impact": "low",
                "requires_confirmation": False,
                "payload": {},
            }
        ]
        result = _make_result(actions=actions)
        ui = compose(result)
        assert ui is not None
        assert isinstance(ui, dict)
        assert len(ui["actions"]) == 1
        assert ui["actions"][0]["label"] == "Save"

    def test_permission_request_and_actions_both_mapped(self):
        from src.services.agentic_ui_composer import compose
        actions = [
            {
                "id": "act-002",
                "label": "Skip",
                "kind": "navigate",
                "impact": "low",
                "requires_confirmation": False,
                "payload": {},
            }
        ]
        result = _make_result(
            permission_request=_sample_permission_request(),
            actions=actions,
        )
        ui = compose(result)
        assert ui is not None
        assert "permission_request" in ui
        assert len(ui["actions"]) == 1

    def test_result_with_no_data_attr_returns_none(self):
        """Gracefully handle objects that lack a .data attribute."""
        from src.services.agentic_ui_composer import compose

        class _NoData:
            pass

        assert compose(_NoData()) is None

    def test_result_data_none_returns_none(self):
        """RuntimeResult.data defaults to {} but guard against None too."""
        from src.services.agentic_ui_composer import compose

        class _NoneData:
            data = None

        assert compose(_NoneData()) is None

    def test_compose_is_idempotent(self):
        """Calling compose() twice with the same result produces equal dicts."""
        from src.services.agentic_ui_composer import compose
        result = _make_result(permission_request=_sample_permission_request())
        ui1 = compose(result)
        ui2 = compose(result)
        assert ui1 == ui2

    def test_malformed_permission_request_returns_none(self):
        """If the permission_request dict doesn't match the schema, compose() returns None."""
        from src.services.agentic_ui_composer import compose
        result = _make_result(permission_request={"bad": "data", "no_id": True})
        ui = compose(result)
        assert ui is None


# ── PR-C: job_matches action cards ────────────────────────────────────────────

class TestJobMatchesActions:

    def test_with_matches_includes_view_save_refine(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {
            "type": "job_matches",
            "matches": [{"title": "HSE Manager"}],
            "search_query": "HSE Manager",
        })
        ids = _action_ids(r)
        assert "view-jobs" in ids
        assert "save-search" in ids
        assert "refine-search" in ids

    def test_without_matches_omits_save_search(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": "job_matches", "matches": [], "search_query": "PM"})
        ids = _action_ids(r)
        assert "view-jobs" in ids
        assert "save-search" not in ids
        assert "refine-search" in ids

    def test_view_jobs_navigates_to_flow(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": "job_matches", "matches": [{}]})
        view = next(a for a in r["actions"] if a["id"] == "view-jobs")
        assert view["kind"] == "navigate"
        assert view["href"] == "/flow"

    def test_save_search_uses_search_query_in_prompt(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {
            "type": "job_matches",
            "matches": [{"title": "x"}],
            "search_query": "QHSE Engineer",
        })
        save = next(a for a in r["actions"] if a["id"] == "save-search")
        assert "QHSE Engineer" in save["payload"]["prompt"]
        assert save["kind"] == "chat_continue"

    def test_save_search_falls_back_to_entities_job_title(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {
            "type": "job_matches",
            "matches": [{}],
            "entities": {"job_title": "Safety Officer"},
        })
        save = next(a for a in r["actions"] if a["id"] == "save-search")
        assert "Safety Officer" in save["payload"]["prompt"]

    def test_refine_is_chat_continue_with_prompt(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": "job_matches", "matches": [{}]})
        refine = next(a for a in r["actions"] if a["id"] == "refine-search")
        assert refine["kind"] == "chat_continue"
        assert "prompt" in refine["payload"]

    def test_returns_plain_dict_not_pydantic_model(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": "job_matches", "matches": [{}]})
        assert isinstance(r, dict)
        assert isinstance(r["actions"], list)
        assert isinstance(r["actions"][0], dict)


# ── PR-C: delete_saved_jobs_confirm ───────────────────────────────────────────

class TestDeleteConfirmActions:

    def test_has_yes_and_no_actions(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": "delete_saved_jobs_confirm"})
        ids = _action_ids(r)
        assert "confirm-delete-jobs" in ids
        assert "cancel-delete-jobs" in ids

    def test_both_are_chat_continue(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": "delete_saved_jobs_confirm"})
        assert all(a["kind"] == "chat_continue" for a in r["actions"])

    def test_confirm_is_high_impact_requires_confirmation(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": "delete_saved_jobs_confirm"})
        yes = next(a for a in r["actions"] if a["id"] == "confirm-delete-jobs")
        assert yes["impact"] == "high"
        assert yes["requires_confirmation"] is True

    def test_cancel_sends_no_type_prompt(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": "delete_saved_jobs_confirm"})
        no = next(a for a in r["actions"] if a["id"] == "cancel-delete-jobs")
        assert "no" in no["payload"]["prompt"].lower()


# ── PR-C: delete_saved_jobs_done ──────────────────────────────────────────────

class TestDeleteDoneActions:

    def test_offers_new_search(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": "delete_saved_jobs_done"})
        assert "new-search" in _action_ids(r)

    def test_new_search_is_chat_continue(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": "delete_saved_jobs_done"})
        act = next(a for a in r["actions"] if a["id"] == "new-search")
        assert act["kind"] == "chat_continue"


# ── PR-C: profile responses ───────────────────────────────────────────────────

class TestProfileActions:

    @pytest.mark.parametrize("rtype", [
        "profile_update", "profile_summary", "cv_first_profile",
    ])
    def test_profile_type_has_view_profile(self, rtype):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": rtype})
        assert "view-profile" in _action_ids(r)

    def test_view_profile_navigates(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": "profile_update"})
        act = next(a for a in r["actions"] if a["id"] == "view-profile")
        assert act["kind"] == "navigate"
        assert act["href"] == "/profile"


# ── PR-C: application_status_update ──────────────────────────────────────────

class TestApplicationActions:

    def test_track_applications_action(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": "application_status_update"})
        assert "view-applications" in _action_ids(r)
        act = next(a for a in r["actions"] if a["id"] == "view-applications")
        assert act["kind"] == "navigate"
        assert act["href"] == "/applications"


# ── PR-C: save_job ────────────────────────────────────────────────────────────

class TestSaveJobActions:

    def test_view_saved_jobs_navigate_to_flow(self):
        from src.services.agentic_ui_composer import compose
        r = compose(None, {"type": "save_job"})
        assert "view-saved-jobs" in _action_ids(r)
        act = next(a for a in r["actions"] if a["id"] == "view-saved-jobs")
        assert act["href"] == "/flow"


# ── PR-C: unknown / no-op types ───────────────────────────────────────────────

class TestUnknownType:

    def test_clarification_returns_none(self):
        from src.services.agentic_ui_composer import compose
        assert compose(None, {"type": "clarification"}) is None

    def test_error_type_returns_none(self):
        from src.services.agentic_ui_composer import compose
        assert compose(None, {"type": "error"}) is None

    def test_no_response_dict_returns_none(self):
        from src.services.agentic_ui_composer import compose
        assert compose(None, None) is None


# ── PR-C: runtime result priority ────────────────────────────────────────────

class TestRuntimePriority:

    def test_runtime_actions_override_type_based_actions(self):
        from src.services.agentic_ui_composer import compose
        rt = _make_result(actions=[
            {"id": "custom-action", "label": "Custom", "kind": "navigate", "href": "/x"}
        ])
        r = compose(rt, {"type": "job_matches", "matches": [{}]})
        ids = _action_ids(r)
        assert "custom-action" in ids
        assert "view-jobs" not in ids  # type-based overridden by runtime

    def test_runtime_proposed_changes_merged_with_type_based_actions(self):
        from src.services.agentic_ui_composer import compose
        rt = _make_result(proposed_changes=[
            {"field": "target_role", "proposed_value": "HSE Manager", "source": "chat"}
        ])
        r = compose(rt, {"type": "job_matches", "matches": [{}]})
        # Actions come from type-based (runtime has no actions)
        assert "view-jobs" in _action_ids(r)
        # proposed_changes come from runtime
        assert "proposed_changes" in r
        assert r["proposed_changes"][0]["field"] == "target_role"

    def test_runtime_without_data_falls_through_to_type_based(self):
        from src.services.agentic_ui_composer import compose
        rt = _make_result()  # data = {} — no actions
        r = compose(rt, {"type": "profile_update"})
        assert "view-profile" in _action_ids(r)

    def test_runtime_none_data_falls_through_to_type_based(self):
        from src.services.agentic_ui_composer import compose

        class _NoneData:
            data = None

        r = compose(_NoneData(), {"type": "profile_update"})
        assert "view-profile" in _action_ids(r)
