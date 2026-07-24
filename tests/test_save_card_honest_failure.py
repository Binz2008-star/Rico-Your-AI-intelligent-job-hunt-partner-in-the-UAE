"""Regression: the save-job card handler never claims success on a failed save.

The card handler must not tell the user a job was saved unless the CANONICAL
board write (applications_repo, read-back verified) actually succeeded — the
#764 mutation-confirmation contract. Success is gated on
``application_board.persist_job_action`` (the store /applications reads), not on
the best-effort runtime side-effects; a failed board write yields an honest
retry message, mirroring the Skip handler (#1220).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.rico_chat_api import RicoChatAPI


def _save_intent(title: str, company: str):
    return SimpleNamespace(
        intent="save_job",
        extracted_title=title,
        extracted_company=company,
        extracted_role=None,
        entities={},
        confidence=0.95,
        source="test",
        action="",
    )


def _drive_save(board_ok: bool):
    from src.services.application_board import BoardResult

    api = RicoChatAPI(persist=False)
    job = {
        "title": "Data Engineer",
        "company": "Acme",
        "apply_url": "https://example.com/job",
        "source_url": "https://example.com/job",
        "verification_status": "lead_needs_verification",
    }
    # Success now depends on the CANONICAL board write, not the runtime tool.
    board = BoardResult(ok=board_ok, status="saved" if board_ok else "",
                        error="" if board_ok else "persist_failed")
    # Runtime is best-effort side-effects only; report ok either way to prove the
    # message is gated on the board result, not on the runtime.
    fake_result = SimpleNamespace(ok=True, error=None, message="ignored")
    with patch("src.rico_chat_api.classify_intent", return_value=_save_intent("Data Engineer", "Acme")), \
         patch.object(api, "_resolve_card_job", return_value=job), \
         patch("src.services.application_board.persist_job_action", return_value=board), \
         patch("src.rico_chat_api.agent_runtime.handle_action", return_value=fake_result), \
         patch.object(api, "_append_chat"), \
         patch.object(api, "_finalize", side_effect=lambda response, *a, **k: response):
        return api._handle_active_user_inner("smoke-user@example.com", "save Data Engineer at Acme")


def test_failed_save_is_honest_not_a_hollow_promise():
    resp = _drive_save(board_ok=False)
    msg = (resp.get("message") or "").lower()
    assert "couldn't save" in msg or "could not save" in msg
    # The exact hollow-promise phrasing must be gone.
    assert "in your tracker" not in msg
    assert "keep it with your saved jobs" not in msg


def test_successful_save_still_confirms():
    resp = _drive_save(board_ok=True)
    msg = (resp.get("message") or "").lower()
    assert "saved" in msg
    assert "tracked jobs" in msg
