"""_finalize agentic_ui contract — never null on the wire (2026-07-19).

Production incident: complete profile-report replies rendered as the
generic error bubble because _finalize serialized "agentic_ui": null for
card-less text replies, and the frontend schema (optional, not nullable)
rejected the whole envelope: SSE done payload silently dropped + REST
fallback threw. Contract now: a REAL object when cards exist, an ABSENT
key otherwise — never null, never an empty-object substitute.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.rico_chat_api import RicoChatAPI


class _Agent:
    available = True
    openai_available = True
    deepseek_available = True
    hf_available = False
    provider_available = True
    model = "test-model"


def _finalize(response):
    api = RicoChatAPI.__new__(RicoChatAPI)
    with patch.object(RicoChatAPI, "_get_openai_agent", return_value=_Agent()):
        return api._finalize(response, "openai", profile=None)


def test_cardless_text_reply_omits_agentic_ui_key_entirely():
    envelope = _finalize({"type": "text", "message": "تقرير ملفك الشخصي ..."})
    assert "agentic_ui" not in envelope          # absent — NOT null, NOT {}
    assert envelope["message"]                   # reply itself untouched


def test_job_matches_reply_keeps_real_agentic_ui_object():
    envelope = _finalize({"type": "job_matches", "message": "m", "matches": []})
    assert isinstance(envelope.get("agentic_ui"), dict)
    assert envelope["agentic_ui"].get("actions")  # the auto-generated cards


def test_preexisting_null_in_response_dict_is_also_stripped():
    """Defensive: a null smuggled in via **response never reaches the wire."""
    envelope = _finalize({"type": "text", "message": "m", "agentic_ui": None})
    assert "agentic_ui" not in envelope
