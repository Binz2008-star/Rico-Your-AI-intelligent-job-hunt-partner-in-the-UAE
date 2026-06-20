"""
tests/test_agentic_ui_composer.py
Unit tests for src/services/agentic_ui_composer.compose().

Pure Pydantic/domain tests — no HTTP, no database, no external services.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "x" * 32)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_result(**data_kwargs):
    """Build a minimal stub that looks like RuntimeResult."""
    class _Stub:
        data = data_kwargs
    return _Stub()


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


# ── Tests ─────────────────────────────────────────────────────────────────────

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
        from src.schemas.chat import RicoAgenticUi
        result = _make_result(permission_request=_sample_permission_request())
        ui = compose(result)
        assert ui is not None
        assert isinstance(ui, RicoAgenticUi)
        assert ui.permission_request is not None
        assert ui.permission_request.id == "perm-test-abc123"
        assert ui.permission_request.risk_level == "high"

    def test_permission_request_approve_action_preserved(self):
        from src.services.agentic_ui_composer import compose
        result = _make_result(permission_request=_sample_permission_request())
        ui = compose(result)
        assert ui.permission_request.approve_action.kind.value == "approve"
        assert ui.permission_request.approve_action.endpoint == "/api/v1/rico/actions/execute"

    def test_empty_actions_list_returns_none(self):
        """An empty actions list carries no UI artifacts — skip it."""
        from src.services.agentic_ui_composer import compose
        assert compose(_make_result(actions=[])) is None

    def test_actions_list_maps_to_agentic_ui(self):
        from src.services.agentic_ui_composer import compose
        from src.schemas.chat import RicoAgenticUi
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
        assert isinstance(ui, RicoAgenticUi)
        assert len(ui.actions) == 1
        assert ui.actions[0].label == "Save"

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
        assert ui.permission_request is not None
        assert len(ui.actions) == 1

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
        """Calling compose() twice with the same result produces equal outputs."""
        from src.services.agentic_ui_composer import compose
        result = _make_result(permission_request=_sample_permission_request())
        ui1 = compose(result)
        ui2 = compose(result)
        assert ui1.model_dump() == ui2.model_dump()

    def test_malformed_permission_request_returns_none(self):
        """If the permission_request dict doesn't match the schema, compose() returns None."""
        from src.services.agentic_ui_composer import compose
        result = _make_result(permission_request={"bad": "data", "no_id": True})
        ui = compose(result)
        assert ui is None
