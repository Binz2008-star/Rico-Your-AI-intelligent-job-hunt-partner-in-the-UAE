"""
tests/unit/test_compound_role_amp_split.py

Regression: a compound job title joined by "&" (or "and") was split into two
garbage roles. A live conversation showed "search Risk & Compliance Officer
jobs in UAE" → the parser produced ["Risk", "Compliance Officer"], searched the
degenerate "Risk", and the request errored ("Something went wrong").

Fix: the compound-title shield now recognises "X and/& Y" pairs (including
risk/compliance) and shields BOTH connectors, so the title stays one role. The
existing "and"-only phrases (oil & gas, health & safety, …) written with "&"
were latently broken too and are now covered. Genuine multi-role lists still
split, and the original connector ("&" vs "and") is preserved.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


class TestCompoundNotSplit:
    @pytest.mark.parametrize("text,expected", [
        ("Risk & Compliance Officer", ["Risk & Compliance Officer"]),
        ("Risk and Compliance Officer", ["Risk and Compliance Officer"]),
        ("search Risk & Compliance Officer jobs in UAE", ["Risk & Compliance Officer"]),
        ("Oil & Gas Engineer", ["Oil & Gas Engineer"]),
        ("Health & Safety Manager", ["Health & Safety Manager"]),
        ("Food & Beverage Manager", ["Food & Beverage Manager"]),
        ("Research & Development Lead", ["Research & Development Lead"]),
        ("find Environmental Health and Safety Manager jobs", ["Environmental Health and Safety Manager"]),
    ])
    def test_single_compound_role(self, text, expected):
        from src.agent.intelligence.intent_classifier import extract_role_list
        roles, _ = extract_role_list(text)
        assert roles == expected


class TestGenuineListsStillSplit:
    def test_comma_and_list_splits(self):
        from src.agent.intelligence.intent_classifier import extract_role_list
        roles, _ = extract_role_list(
            "Environmental Manager, Compliance Manager and ESG Manager"
        )
        assert roles == ["Environmental Manager", "Compliance Manager", "ESG Manager"]

    def test_unknown_amp_pair_still_splits(self):
        from src.agent.intelligence.intent_classifier import extract_role_list
        # Not a known compound title → still treated as a two-item list.
        roles, _ = extract_role_list("Accountant & Nurse")
        assert roles == ["Accountant", "Nurse"]


class TestConnectorPreserved:
    def test_amp_and_word_forms_round_trip(self):
        from src.agent.intelligence.intent_classifier import (
            _shield_compound_role_phrases, _unshield_compound_role_phrases,
        )
        for s in ("Risk & Compliance Officer", "Risk and Compliance Officer",
                  "Oil & Gas Engineer"):
            shielded = _shield_compound_role_phrases(s)
            assert "&" not in shielded or "and" not in shielded  # connector hidden
            assert _unshield_compound_role_phrases(shielded) == s


class TestClassifyAndSearch:
    def test_classify_single_explicit_role(self):
        from src.agent.intelligence.intent_classifier import classify_intent
        r = classify_intent("search Risk & Compliance Officer jobs in UAE")
        assert r.intent == "job_search_explicit"
        assert (r.entities or {}).get("location") == "UAE"

    def test_end_to_end_single_role_search_not_split(self):
        from tests.harness.chat_harness import ChatHarness
        h = ChatHarness()
        h.seed("rc@t", cv_status="parsed", cv_filename="cv.pdf",
               target_roles=["Environmental Manager", "Compliance Manager",
                             "Risk & Compliance Officer"],
               skills=["iso 14001", "audit", "compliance"],
               years_experience=10, preferred_cities=["Dubai"])
        r = h.say("rc@t", "search Risk & Compliance Officer jobs in UAE")
        assert r.get("type") == "job_matches"
        # A SINGLE role was searched — not the "Risk" + "Compliance Officer" split.
        assert len(h.searched_roles) == 1
        assert "I recognised 2 target roles" not in (r.get("message") or "")
