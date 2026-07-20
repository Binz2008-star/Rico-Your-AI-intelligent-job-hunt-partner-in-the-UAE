"""Regression: SSE 'done' events serialize with a total encoder (default=str).

The terminal 'done' event serializes the full chat response dict. If any field
is not natively JSON-serializable (a datetime, Decimal, or a pydantic model that
slipped through), a bare json.dumps raises TypeError mid-stream; the stream
generator's except then collapses the reply to a generic "Stream error",
dropping the already-persisted assistant turn from the wire. #1210/#1222/#1225
each patched this boundary one field at a time. `_sse_done` uses default=str to
close the whole class.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.api.routers.rico_chat import _sse_done


def _payload_of(sse_line: str) -> dict:
    assert sse_line.startswith("data: ")
    assert sse_line.endswith("\n\n")
    return json.loads(sse_line[len("data: ") :].strip())


def test_done_event_tolerates_datetime_field():
    dt = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    line = _sse_done({"message": "hi", "reset_at": dt})
    body = _payload_of(line)
    assert body["type"] == "done"
    assert body["response"]["message"] == "hi"
    # Rendered as a string rather than crashing the stream.
    assert isinstance(body["response"]["reset_at"], str)


def test_done_event_tolerates_decimal_field():
    line = _sse_done({"message": "hi", "score": Decimal("3.5")})
    body = _payload_of(line)
    assert body["response"]["score"] in ("3.5", "3.5000")  # str(Decimal)


def test_bare_json_dumps_would_raise_on_same_payload():
    # Demonstrates the pre-fix failure mode the encoder prevents.
    with pytest.raises(TypeError):
        json.dumps({"type": "done", "response": {"reset_at": datetime.now(timezone.utc)}})


def test_normal_dict_payload_unchanged():
    line = _sse_done({"message": "ok", "type": "conversational", "response_source": "stream"})
    body = _payload_of(line)
    assert body == {
        "type": "done",
        "response": {"message": "ok", "type": "conversational", "response_source": "stream"},
    }
