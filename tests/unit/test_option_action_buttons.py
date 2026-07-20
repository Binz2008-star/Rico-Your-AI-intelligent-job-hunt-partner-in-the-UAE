"""Tests for audit item 1-A: letter-choice options → agentic_ui chat_continue buttons.

Contract note (2026-07-20): _inject_option_buttons now returns ``agentic_ui``
as a serialized plain dict (``model_dump(exclude_none=True)``), not a raw
RicoAgenticUi model — a raw model reached the SSE done-only json.dumps
un-encoded and raised TypeError. These tests assert the dict-on-the-wire
shape accordingly.
"""
from __future__ import annotations

import pytest
from src.rico_chat_api import RicoChatAPI as RicoChatProcessor
from src.schemas.chat import RicoChatAction, RicoAgenticUi, RicoActionKind


def _opts(*labels_messages):
    """Build a list of option dicts from (label, message) pairs."""
    return [{"label": lbl, "message": msg, "action": "test"} for lbl, msg in labels_messages]


class TestInjectOptionButtons:

    def test_basic_two_options_become_buttons(self):
        opts = _opts(("Software Engineer", "find jobs for software engineer"),
                     ("Data Analyst", "find jobs for data analyst"))
        result = RicoChatProcessor._inject_option_buttons({"message": "pick one"}, opts)
        ui = result["agentic_ui"]
        assert isinstance(ui, dict)
        assert len(ui["actions"]) == 2
        assert ui["actions"][0]["kind"] == "chat_continue"
        assert ui["actions"][1]["kind"] == "chat_continue"

    def test_button_labels_have_letter_prefix(self):
        opts = _opts(("Apply now", "apply"), ("Save for later", "save job"))
        result = RicoChatProcessor._inject_option_buttons({}, opts)
        labels = [a["label"] for a in result["agentic_ui"]["actions"]]
        assert labels[0].startswith("A)")
        assert labels[1].startswith("B)")

    def test_button_payloads_carry_full_message(self):
        opts = _opts(("Find jobs", "find live UAE jobs for data scientist"))
        result = RicoChatProcessor._inject_option_buttons({}, opts)
        assert result["agentic_ui"]["actions"][0]["payload"]["message"] == "find live UAE jobs for data scientist"

    def test_caps_at_four_options(self):
        opts = _opts(*[(f"Option {i}", f"msg {i}") for i in range(6)])
        result = RicoChatProcessor._inject_option_buttons({}, opts)
        assert len(result["agentic_ui"]["actions"]) == 4

    def test_no_options_returns_unchanged_result(self):
        original = {"message": "hello", "type": "chat"}
        result = RicoChatProcessor._inject_option_buttons(original, [])
        assert result is original
        assert "agentic_ui" not in result

    def test_invalid_option_entries_skipped(self):
        # None/string/empty-label entries are skipped; valid entry at index 3 gets letter "D"
        # (letter matches list position, same as _resolve_letter_choice)
        opts = [None, "string", {"label": "", "message": "msg"}, {"label": "Valid", "message": "go"}]
        result = RicoChatProcessor._inject_option_buttons({}, opts)
        assert len(result["agentic_ui"]["actions"]) == 1
        assert result["agentic_ui"]["actions"][0]["label"] == "D) Valid"

    def test_existing_agentic_ui_actions_are_preserved(self):
        existing_action = RicoChatAction(
            id="existing-1",
            label="Existing",
            kind=RicoActionKind.submit,
            payload={},
        )
        existing_ui = RicoAgenticUi(actions=[existing_action])
        opts = _opts(("New opt", "new message"))
        result = RicoChatProcessor._inject_option_buttons({"agentic_ui": existing_ui}, opts)
        actions = result["agentic_ui"]["actions"]
        assert len(actions) == 2
        assert actions[0]["label"] == "Existing"
        assert actions[1]["label"] == "A) New opt"

    def test_label_already_prefixed_not_doubled(self):
        opts = [{"label": "A) Software Engineer", "message": "find SE jobs", "action": ""}]
        result = RicoChatProcessor._inject_option_buttons({}, opts)
        assert result["agentic_ui"]["actions"][0]["label"] == "A) Software Engineer"

    def test_result_dict_is_not_mutated(self):
        original = {"message": "pick"}
        opts = _opts(("Opt A", "msg a"))
        result = RicoChatProcessor._inject_option_buttons(original, opts)
        assert "agentic_ui" not in original
        assert result is not original
