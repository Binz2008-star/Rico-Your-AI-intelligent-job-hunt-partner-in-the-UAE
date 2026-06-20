"""tests/test_career_os_01_agentic_contracts.py

CAREER-OS-01 backward-compatibility tests for the AgenticUIContract schema
additions to RicoChatResponse (src/schemas/chat.py) and the corresponding
TypeScript schema additions (apps/web/lib/schemas/index.ts).

No DB, no live APIs, no imports of psycopg2 or FastAPI app required.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.schemas.chat import (
    AgenticUIActionContract,
    AgenticUIComponentContract,
    AgenticUIContract,
    RicoChatResponse,
)


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
            {"message": "ok", "unknown_field_from_future_version": "ignored_but_kept"}
        )
        assert resp.message == "ok"
        assert resp.agentic_ui is None
        # extra="allow" means unknown fields are stored
        assert resp.model_extra is not None
        assert "unknown_field_from_future_version" in resp.model_extra

    def test_none_agentic_ui_is_absent_in_serialized_output(self) -> None:
        resp = RicoChatResponse.model_validate({"message": "Hi"})
        d = resp.model_dump(exclude_none=True)
        assert "agentic_ui" not in d


# ── AgenticUIContract parsing ──────────────────────────────────────────────────


class TestAgenticUIContractParsing:
    """The new contract models must parse correctly from dicts."""

    def test_empty_contract_uses_defaults(self) -> None:
        contract = AgenticUIContract.model_validate({})
        assert contract.version == "1"
        assert contract.components == []
        assert contract.primary_action is None

    def test_contract_with_components(self) -> None:
        contract = AgenticUIContract.model_validate(
            {
                "version": "1",
                "components": [
                    {
                        "component": "job_card",
                        "title": "Top match",
                        "data": {"title": "ML Engineer", "company": "Noon"},
                        "actions": [
                            {
                                "action_id": "abc123",
                                "type": "apply",
                                "label": "Apply",
                                "style": "primary",
                                "job_id": "job_42",
                            }
                        ],
                    }
                ],
            }
        )
        assert contract.version == "1"
        assert len(contract.components) == 1
        comp = contract.components[0]
        assert comp.component == "job_card"
        assert comp.title == "Top match"
        assert len(comp.actions) == 1
        action = comp.actions[0]
        assert action.type == "apply"
        assert action.style == "primary"
        assert action.job_id == "job_42"

    def test_contract_with_primary_action(self) -> None:
        contract = AgenticUIContract.model_validate(
            {
                "primary_action": {
                    "type": "navigate",
                    "label": "View Dashboard",
                    "href": "/dashboard",
                }
            }
        )
        assert contract.primary_action is not None
        assert contract.primary_action.type == "navigate"
        assert contract.primary_action.href == "/dashboard"

    def test_contract_unknown_fields_pass_through(self) -> None:
        contract = AgenticUIContract.model_validate(
            {"version": "2", "future_field": "some_value", "components": []}
        )
        assert contract.version == "2"
        assert contract.model_extra is not None
        assert "future_field" in contract.model_extra


# ── RicoChatResponse with agentic_ui set ──────────────────────────────────────


class TestRicoChatResponseWithAgenticUI:
    """Responses carrying agentic_ui must round-trip correctly."""

    def test_response_with_agentic_ui_dict(self) -> None:
        payload = {
            "message": "I found 3 matches.",
            "agentic_ui": {
                "version": "1",
                "components": [
                    {
                        "component": "job_list",
                        "title": "Your matches",
                        "data": {"jobs": []},
                        "actions": [],
                    }
                ],
            },
        }
        resp = RicoChatResponse.model_validate(payload)
        assert resp.message == "I found 3 matches."
        assert resp.agentic_ui is not None
        assert resp.agentic_ui.version == "1"
        assert len(resp.agentic_ui.components) == 1
        assert resp.agentic_ui.components[0].component == "job_list"

    def test_response_with_agentic_ui_none_explicit(self) -> None:
        resp = RicoChatResponse.model_validate({"message": "ok", "agentic_ui": None})
        assert resp.agentic_ui is None

    def test_response_roundtrip(self) -> None:
        payload = {
            "message": "Done.",
            "agentic_ui": {
                "version": "1",
                "primary_action": {
                    "type": "send_message",
                    "label": "Tell me more",
                    "action_id": "x1",
                },
                "components": [],
            },
        }
        resp = RicoChatResponse.model_validate(payload)
        out = resp.model_dump(exclude_none=True)
        assert out["message"] == "Done."
        assert out["agentic_ui"]["version"] == "1"
        assert out["agentic_ui"]["primary_action"]["label"] == "Tell me more"


# ── AgenticUIActionContract style validation ───────────────────────────────────


class TestAgenticUIActionContract:
    """Action model validation."""

    def test_default_style_is_secondary(self) -> None:
        action = AgenticUIActionContract.model_validate({"type": "skip", "label": "Skip"})
        assert action.style == "secondary"

    def test_danger_style_accepted(self) -> None:
        action = AgenticUIActionContract.model_validate(
            {"type": "cancel", "label": "Cancel", "style": "danger"}
        )
        assert action.style == "danger"

    def test_invalid_style_raises(self) -> None:
        with pytest.raises(Exception):
            AgenticUIActionContract.model_validate(
                {"type": "apply", "label": "Apply", "style": "invalid_style"}
            )

    def test_payload_defaults_to_empty_dict(self) -> None:
        action = AgenticUIActionContract.model_validate({"type": "apply", "label": "Apply"})
        assert action.payload == {}


# ── TypeScript schema file structural checks ───────────────────────────────────


class TestTypeScriptSchemaFile:
    """Verify the TypeScript schema file contains the expected CAREER-OS-01 symbols.

    These are string-presence checks — they don't compile TypeScript but confirm
    that the symbols were actually added and not accidentally removed.
    """

    SCHEMA_FILE = (
        Path(__file__).resolve().parent.parent
        / "apps" / "web" / "lib" / "schemas" / "index.ts"
    )

    def _source(self) -> str:
        return self.SCHEMA_FILE.read_text(encoding="utf-8")

    def test_agentic_ui_action_contract_schema_exported(self) -> None:
        assert "AgenticUIActionContractSchema" in self._source()

    def test_agentic_ui_component_contract_schema_exported(self) -> None:
        assert "AgenticUIComponentContractSchema" in self._source()

    def test_agentic_ui_contract_schema_exported(self) -> None:
        assert "AgenticUIContractSchema" in self._source()

    def test_agentic_ui_field_on_rico_chat_response_schema(self) -> None:
        src = self._source()
        rico_chat_idx = src.index("RicoChatResponseSchema")
        agentic_ui_idx = src.index("agentic_ui:", rico_chat_idx)
        assert agentic_ui_idx > rico_chat_idx, (
            "agentic_ui field must appear inside RicoChatResponseSchema"
        )

    def test_type_exports_present(self) -> None:
        src = self._source()
        assert "export type AgenticUIActionContract" in src
        assert "export type AgenticUIComponentContract" in src
        assert "export type AgenticUIContract" in src

    def test_passthrough_on_contract_schemas(self) -> None:
        src = self._source()
        # All three contract schemas must have .passthrough()
        for schema_name in (
            "AgenticUIActionContractSchema",
            "AgenticUIComponentContractSchema",
            "AgenticUIContractSchema",
        ):
            idx = src.index(schema_name + " = z.object(")
            passthrough_idx = src.index(".passthrough()", idx)
            assert passthrough_idx > idx, (
                f"{schema_name} must use .passthrough() for forward compatibility"
            )


# ── Python schema file structural checks ──────────────────────────────────────


class TestPythonSchemaFile:
    """Verify the Python schema file contains the expected CAREER-OS-01 additions."""

    SCHEMA_FILE = (
        Path(__file__).resolve().parent.parent
        / "src" / "schemas" / "chat.py"
    )

    def _source(self) -> str:
        return self.SCHEMA_FILE.read_text(encoding="utf-8")

    def test_agentic_ui_action_contract_class_present(self) -> None:
        assert "class AgenticUIActionContract" in self._source()

    def test_agentic_ui_component_contract_class_present(self) -> None:
        assert "class AgenticUIComponentContract" in self._source()

    def test_agentic_ui_contract_class_present(self) -> None:
        assert "class AgenticUIContract" in self._source()

    def test_agentic_ui_field_on_rico_chat_response(self) -> None:
        src = self._source()
        rico_idx = src.index("class RicoChatResponse")
        field_idx = src.index("agentic_ui:", rico_idx)
        assert field_idx > rico_idx

    def test_all_contract_classes_have_extra_allow(self) -> None:
        src = self._source()
        for cls in (
            "AgenticUIActionContract",
            "AgenticUIComponentContract",
            "AgenticUIContract",
        ):
            cls_idx = src.index(f"class {cls}")
            # extra="allow" must appear before the next class definition
            next_class = src.find("\nclass ", cls_idx + 1)
            segment = src[cls_idx:next_class if next_class != -1 else cls_idx + 500]
            assert 'extra="allow"' in segment, (
                f"{cls} must have ConfigDict(extra='allow') for forward compatibility"
            )
