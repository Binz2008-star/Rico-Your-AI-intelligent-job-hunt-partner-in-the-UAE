"""tests/test_career_os_01_agentic_contracts.py

CAREER-OS-01 backward-compatibility tests for the optional agentic_ui field
added to RicoChatResponse (src/schemas/chat.py) and RicoChatResponseSchema
(apps/web/lib/schemas/index.ts).

agentic_ui reuses AgentUIResponse / AgentUIResponseSchema — no new model classes.
No DB, no live APIs, no FastAPI app import required.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.schemas.chat import RicoChatResponse
from src.schemas.agent import AgentAction, AgentUIComponent, AgentUIResponse, AgentUIType


# ── RicoChatResponse backward compatibility ────────────────────────────────────


class TestRicoChatResponseBackwardCompat:
    """Existing callers that never set agentic_ui must continue to work."""

    def test_empty_dict_parses(self) -> None:
        resp = RicoChatResponse.model_validate({})
        assert resp.message == ""
        assert resp.agentic_ui is None

    def test_minimal_message_parses(self) -> None:
        resp = RicoChatResponse.model_validate({"message": "Hello from Rico"})
        assert resp.message == "Hello from Rico"
        assert resp.agentic_ui is None

    def test_full_legacy_response_parses(self) -> None:
        payload = {
            "message": "Here are your top matches.",
            "type": "response",
            "matches": [{"title": "SRE", "company": "Acme", "score": 0.9}],
            "options": [{"action": "apply", "label": "Apply now"}],
            "next_action": "choose_option",
            "next_actions": [{"action": "skip", "label": "Skip"}],
            "intent": "job_search",
            "response_source": "deepseek",
            "provider": "deepseek",
            "reasons": ["Skill match: Python", "Location: Dubai"],
            "success": True,
        }
        resp = RicoChatResponse.model_validate(payload)
        assert resp.message == "Here are your top matches."
        assert len(resp.matches) == 1
        assert resp.agentic_ui is None

    def test_extra_unknown_fields_pass_through(self) -> None:
        resp = RicoChatResponse.model_validate(
            {"message": "ok", "unknown_field_from_future_version": "kept"}
        )
        assert resp.message == "ok"
        assert resp.model_extra is not None
        assert "unknown_field_from_future_version" in resp.model_extra

    def test_none_agentic_ui_absent_in_serialized_output(self) -> None:
        resp = RicoChatResponse.model_validate({"message": "Hi"})
        d = resp.model_dump(exclude_none=True)
        assert "agentic_ui" not in d


# ── RicoChatResponse with agentic_ui set ──────────────────────────────────────


class TestRicoChatResponseWithAgenticUI:
    """Responses carrying agentic_ui must round-trip correctly."""

    def test_agentic_ui_from_dict(self) -> None:
        payload = {
            "message": "I found 3 matches.",
            "agentic_ui": {
                "message": "Top job matches",
                "ui": {"type": "job_list", "data": {"jobs": []}},
                "actions": [],
                "success": True,
            },
        }
        resp = RicoChatResponse.model_validate(payload)
        assert resp.message == "I found 3 matches."
        assert resp.agentic_ui is not None
        assert isinstance(resp.agentic_ui, AgentUIResponse)
        assert resp.agentic_ui.ui is not None
        assert resp.agentic_ui.ui.type == AgentUIType.JOB_LIST

    def test_agentic_ui_none_explicit(self) -> None:
        resp = RicoChatResponse.model_validate({"message": "ok", "agentic_ui": None})
        assert resp.agentic_ui is None

    def test_agentic_ui_with_actions(self) -> None:
        payload = {
            "message": "Apply?",
            "agentic_ui": {
                "message": "Ready to apply",
                "ui": {"type": "confirm", "data": {"title": "Apply to Noon"}},
                "actions": [
                    {"action_id": "a1", "type": "apply", "label": "Apply", "style": "primary", "job_id": "job_42"},
                    {"action_id": "a2", "type": "skip", "label": "Skip", "style": "secondary"},
                ],
                "success": True,
            },
        }
        resp = RicoChatResponse.model_validate(payload)
        assert resp.agentic_ui is not None
        assert len(resp.agentic_ui.actions) == 2
        assert resp.agentic_ui.actions[0].type == "apply"
        assert resp.agentic_ui.actions[0].style.value == "primary"
        assert resp.agentic_ui.actions[0].job_id == "job_42"

    def test_agentic_ui_roundtrip(self) -> None:
        resp = RicoChatResponse.model_validate({
            "message": "Done.",
            "agentic_ui": {
                "message": "Action complete",
                "actions": [{"type": "send_message", "label": "Tell me more"}],
                "success": True,
            },
        })
        out = resp.model_dump(exclude_none=True)
        assert out["message"] == "Done."
        assert out["agentic_ui"]["message"] == "Action complete"
        assert out["agentic_ui"]["actions"][0]["label"] == "Tell me more"

    def test_agentic_ui_from_model_instance(self) -> None:
        ui_resp = AgentUIResponse(
            message="3 jobs found",
            ui=AgentUIComponent(type=AgentUIType.JOB_LIST, data={"jobs": []}),
            actions=[AgentAction(type="apply", label="Apply", job_id="j1")],
        )
        resp = RicoChatResponse(message="Here you go", agentic_ui=ui_resp)
        assert resp.agentic_ui is ui_resp
        assert resp.agentic_ui.ui.type == AgentUIType.JOB_LIST


# ── No new model classes introduced ───────────────────────────────────────────


class TestNoNewModelClasses:
    """CAREER-OS-01 must reuse AgentUIResponse, not create parallel classes."""

    CHAT_SCHEMA_FILE = (
        Path(__file__).resolve().parent.parent / "src" / "schemas" / "chat.py"
    )

    def _source(self) -> str:
        return self.CHAT_SCHEMA_FILE.read_text(encoding="utf-8")

    def test_no_agentic_ui_action_contract_class(self) -> None:
        assert "class AgenticUIActionContract" not in self._source()

    def test_no_agentic_ui_component_contract_class(self) -> None:
        assert "class AgenticUIComponentContract" not in self._source()

    def test_no_agentic_ui_contract_class(self) -> None:
        assert "class AgenticUIContract" not in self._source()

    def test_agentic_ui_field_uses_agent_ui_response(self) -> None:
        src = self._source()
        rico_idx = src.index("class RicoChatResponse")
        field_idx = src.index("agentic_ui", rico_idx)
        segment = src[field_idx: field_idx + 80]
        assert "AgentUIResponse" in segment, (
            "agentic_ui field must reference AgentUIResponse, not a new class"
        )

    def test_agent_ui_response_imported(self) -> None:
        assert "from src.schemas.agent import AgentUIResponse" in self._source()


# ── TypeScript schema structural checks ───────────────────────────────────────


class TestTypeScriptSchemaFile:
    """Verify the TypeScript file references AgentUIResponseSchema (existing),
    not newly introduced AgenticUI* schemas."""

    SCHEMA_FILE = (
        Path(__file__).resolve().parent.parent
        / "apps" / "web" / "lib" / "schemas" / "index.ts"
    )

    def _source(self) -> str:
        return self.SCHEMA_FILE.read_text(encoding="utf-8")

    def test_no_agentic_ui_action_contract_schema(self) -> None:
        assert "AgenticUIActionContractSchema" not in self._source()

    def test_no_agentic_ui_component_contract_schema(self) -> None:
        assert "AgenticUIComponentContractSchema" not in self._source()

    def test_no_agentic_ui_contract_schema(self) -> None:
        assert "AgenticUIContractSchema" not in self._source()

    def test_agentic_ui_field_uses_agent_ui_response_schema(self) -> None:
        src = self._source()
        rico_idx = src.index("RicoChatResponseSchema")
        field_idx = src.index("agentic_ui:", rico_idx)
        segment = src[field_idx: field_idx + 60]
        assert "AgentUIResponseSchema" in segment, (
            "agentic_ui field must reference AgentUIResponseSchema, not a new schema"
        )

    def test_agent_ui_response_schema_defined_before_rico_chat_response_schema(self) -> None:
        src = self._source()
        agent_idx = src.index("AgentUIResponseSchema = z.object(")
        rico_idx = src.index("RicoChatResponseSchema = z.object(")
        assert agent_idx < rico_idx, (
            "AgentUIResponseSchema must be defined before RicoChatResponseSchema"
        )
