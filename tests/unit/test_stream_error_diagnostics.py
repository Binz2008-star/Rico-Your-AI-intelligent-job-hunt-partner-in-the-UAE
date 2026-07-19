"""chat_stream_error sanitized diagnostics — owner-scoped (2026-07-19).

A production TypeError in the SSE done-only branch was untraceable: safe_exc
logs the exception TYPE only, so the throw site (envelope build vs
json.dumps vs yield) could not be located. The diagnostic adds:

  * sanitized traceback frames — basename:function:lineno ONLY (no
    exception message, no source lines, no locals, no payloads), and
  * a last-completed-stage marker (finalize_complete → done_envelope_ready
    → done_json_serialized → done_yielded) logged with a correlation ref.

Acceptance (owner's four points): logs carry no message text / email /
response data; frames are locations only; the client-visible error event is
byte-identical to before; SSE happy-path behavior is unchanged.
"""
from __future__ import annotations

import logging
import os
import re
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET", "x" * 32)

_USER = "stream-diag@test.com"
_SECRET_TEXT = "SECRET-CHAT-MESSAGE probe@example.com response-body-value"
_LOGGER = "src.api.routers.rico_chat"

_FRAME_RE = re.compile(r"^[\w.\-]+\.py:[\w<>.]+:\d+$")


def _client() -> TestClient:
    from src.api.app import app
    from src.api.auth import create_access_token
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("access_token", create_access_token({"sub": _USER, "role": "user"}))
    return tc


def _stream(tc: TestClient, message: str) -> str:
    res = tc.post("/api/v1/rico/chat/stream", json={"message": message})
    assert res.status_code == 200
    return res.text


def _error_records(caplog):
    return [r for r in caplog.records if r.name == _LOGGER and r.levelno >= logging.ERROR]


# ── 1+2: sanitized log — no user data; frames are locations only ─────────────

def test_diagnostic_log_is_sanitized_and_frames_are_locations_only(caplog):
    with caplog.at_level(logging.ERROR, logger=_LOGGER), \
         patch("src.repositories.profile_repo.get_profile", return_value=None), \
         patch("src.services.chat_service.should_stream_ai", return_value=False), \
         patch("src.services.chat_service.send_message",
               side_effect=ValueError(_SECRET_TEXT)):
        body = _stream(_client(), "typed user chat text that must never reach logs")

    records = _error_records(caplog)
    assert records, "chat_stream_error was not logged"
    logged = records[0].getMessage()

    # No exception message, chat text, email, or response data — ever.
    assert "SECRET-CHAT-MESSAGE" not in logged
    assert "@" not in logged
    assert "typed user chat text" not in logged
    assert "response-body-value" not in logged

    assert "err=ValueError" in logged            # type name only (safe_exc)
    assert "stage=stream_begin" in logged        # raised before finalize
    assert "ref=ERR-" in logged                  # correlation ref present

    frames = logged.split("frames=", 1)[1]
    assert frames and frames != "unavailable"
    for segment in frames.split(" > "):
        assert _FRAME_RE.match(segment), f"non-location frame segment: {segment!r}"

    # 3: the client-visible error event is byte-identical to the legacy one.
    assert '"type": "error"' in body
    assert "Stream error. Please try again." in body


# ── Stage marker distinguishes the json.dumps throw (THE production case) ────

def test_unserializable_envelope_logs_done_envelope_ready_stage(caplog):
    bad_response = {"type": "text", "message": "ok", "poison": object()}
    with caplog.at_level(logging.ERROR, logger=_LOGGER), \
         patch("src.repositories.profile_repo.get_profile", return_value=None), \
         patch("src.services.chat_service.should_stream_ai", return_value=False), \
         patch("src.services.chat_service.send_message", return_value=bad_response):
        body = _stream(_client(), "probe")

    records = _error_records(caplog)
    assert records
    logged = records[0].getMessage()
    assert "err=TypeError" in logged
    assert "stage=done_envelope_ready" in logged  # dumps threw, envelope built
    assert "object at 0x" not in logged           # repr of the value never leaks
    assert "Stream error. Please try again." in body


# ── 4: SSE happy path unchanged ──────────────────────────────────────────────

def test_done_only_happy_path_is_unchanged(caplog):
    ok_response = {"type": "text", "message": "hello reply", "success": True}
    with caplog.at_level(logging.ERROR, logger=_LOGGER), \
         patch("src.repositories.profile_repo.get_profile", return_value=None), \
         patch("src.services.chat_service.should_stream_ai", return_value=False), \
         patch("src.services.chat_service.send_message", return_value=ok_response):
        body = _stream(_client(), "probe")

    assert '"type": "done"' in body
    assert "hello reply" in body
    assert "Stream error" not in body
    assert not _error_records(caplog)             # no diagnostic on success
