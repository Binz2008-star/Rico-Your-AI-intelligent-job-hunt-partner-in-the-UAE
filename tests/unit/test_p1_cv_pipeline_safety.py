"""Focused regression tests for PR A1 (fix/p1-cv-pipeline-safety).

Covers three fixes:
  1. CV upload parses off the event loop (run_in_executor).
  2. pipeline_repo insert_run/update_run commit (and roll back on error).
  3. auto_apply._RateLimiter.can_apply fails CLOSED on lock timeout.
"""
from __future__ import annotations

import asyncio
import io
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


# ── Fix 1: CV parse runs in an executor (does not block the event loop) ────────

def test_cv_upload_runs_parser_in_executor(monkeypatch):
    """The async upload route must offload the synchronous CV parser to a thread.

    Inside an executor thread there is no running event loop, so
    asyncio.get_running_loop() raises — we use that as the offload signal.
    """
    from src.api.app import app
    import src.services.chat_service as chat_service

    captured: dict = {}

    def _fake_parse(data, filename="cv.pdf"):
        try:
            asyncio.get_running_loop()
            captured["offloaded"] = False  # ran ON the event-loop thread (not offloaded)
        except RuntimeError:
            captured["offloaded"] = True   # ran in an executor thread (offloaded)
        captured["head"] = bytes(data[:4])
        captured["filename"] = filename
        return {
            "document_type": "resume",
            # Readable text is required by the #1118 parse-quality gate before a
            # preview_ready result; the mock must supply it, not just a count.
            "text": (
                "Jane Roe — Software Engineer with Python, FastAPI and cloud "
                "experience. Skills: python, testing, CI. Based in Dubai, UAE."
            ),
            "extraction_quality": "high",
            "extracted_chars": 100,
            "skills": ["python"],
        }

    monkeypatch.setattr(chat_service, "parse_cv", _fake_parse)
    # Keep the post-parse path DB-free so we assert the parse offloading + the
    # preserved response shape, not the profile store.
    monkeypatch.setattr("src.api.routers.rico_chat.get_profile", lambda uid: None)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/rico/upload-cv?user_id=public:web-upload12345",
        files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4 fake cv"), "application/pdf")},
    )

    # Response shape/contract preserved.
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "preview_ready"
    # Core of the fix: the synchronous parser ran OFF the event loop.
    assert captured.get("offloaded") is True
    assert captured.get("head") == b"%PDF"
    assert captured.get("filename") == "cv.pdf"


# ── Fix 2: pipeline_repo commits writes (and rolls back on error) ──────────────

def test_pipeline_insert_run_commits(monkeypatch):
    import src.repositories.pipeline_repo as pipeline_repo

    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (42,)
    monkeypatch.setattr(pipeline_repo, "get_db_connection", lambda: conn)

    run_id = pipeline_repo.insert_run()

    assert run_id == 42
    conn.commit.assert_called_once()
    conn.close.assert_called_once()


def test_pipeline_update_run_commits(monkeypatch):
    import src.repositories.pipeline_repo as pipeline_repo

    conn = MagicMock()
    monkeypatch.setattr(pipeline_repo, "get_db_connection", lambda: conn)

    pipeline_repo.update_run(7, "done")

    conn.commit.assert_called_once()
    conn.close.assert_called_once()


def test_pipeline_insert_run_rolls_back_on_error(monkeypatch):
    import src.repositories.pipeline_repo as pipeline_repo

    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.execute.side_effect = RuntimeError("boom")
    monkeypatch.setattr(pipeline_repo, "get_db_connection", lambda: conn)

    run_id = pipeline_repo.insert_run()

    assert run_id is None
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()


# ── Fix 3: auto_apply rate limiter fails CLOSED on lock timeout ────────────────

def test_auto_apply_can_apply_fails_closed_on_lock_timeout(monkeypatch, tmp_path):
    import src.auto_apply as auto_apply

    class _BoomLock:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            raise auto_apply.FileLockTimeout("lock held")

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(auto_apply, "FileLock", _BoomLock)

    limiter = auto_apply._RateLimiter(path=tmp_path / "rate.json")
    ok, reason = limiter.can_apply()

    assert ok is False  # safe default: deny when the lock cannot be acquired
    assert reason == "lock_timeout"
