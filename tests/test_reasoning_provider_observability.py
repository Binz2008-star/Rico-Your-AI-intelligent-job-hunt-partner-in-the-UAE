"""
tests/test_reasoning_provider_observability.py

Hardening for the DeepSeek-down incident: a dead core AI must be LOUD and
observable — never a silent cosy fallback — and context assembly must survive
document rows with missing/NULL optional fields.

Deterministic only (no live provider, no real DB, no credentials). Covers:
  1. failure payload carries the distinct error_code + degraded state
  5. upstream status code / provider error code / model attempted / redacted
     message are captured and exposed on /health
  2. the fallback text is honest, not a soft reassurance
  4. get_reasoning_health() states + the /health degraded flip, secret-free
  3. smoke: _build_openai_context / _documents_for_llm never throw on NULL/missing
     optional fields
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "x" * 32)

import src.rico_openai_runtime as rt


@pytest.fixture(autouse=True)
def _reset_reasoning_state():
    """Isolate the module-level last-outcome record between tests."""
    saved = dict(rt._LAST_REASONING_OUTCOME)
    for k in rt._LAST_REASONING_OUTCOME:
        rt._LAST_REASONING_OUTCOME[k] = None
    yield
    rt._LAST_REASONING_OUTCOME.update(saved)


class _FakeErr(Exception):
    def __init__(self, msg, status_code=None, code=None):
        super().__init__(msg)
        self.status_code = status_code
        self.code = code


def _fail_call(err):
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = err
    with patch.object(rt, "_build_client", return_value=fake_client):
        return rt.call_openai_minimal("hi", provider="deepseek")


# ── Items 1 & 5: failure payload + upstream capture ───────────────────────────

class TestFailurePayloadObservability:
    def test_distinct_error_code_and_degraded_state(self):
        result = _fail_call(_FakeErr("Model not found", status_code=400, code="model_not_found"))
        assert result["success"] is False
        assert result["error_code"] == "reasoning_provider_unavailable"
        assert result["provider_state"] == "degraded"
        assert result["response_source"] == "fallback"  # unchanged contract

    def test_upstream_details_recorded(self, monkeypatch):
        monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-deepseek-key-for-tests")
        monkeypatch.delenv("HF_TOKEN", raising=False)
        _fail_call(_FakeErr("Model not found", status_code=400, code="model_not_found"))
        h = rt.get_reasoning_health()
        assert h["reachable"] is False
        assert h["last_status_code"] == 400
        assert h["last_provider_error_code"] == "model_not_found"
        assert h["last_model_attempted"] in ("deepseek-v4-flash", "deepseek-v4-pro")
        assert "not found" in (h["last_error_message"] or "").lower()
        assert h["degraded"] is True  # primary unusable + no HF fallback


# ── Item 2: honest fallback text ──────────────────────────────────────────────

class TestHonestFallbackText:
    def test_fallback_is_honest_not_cosy(self):
        text = rt._FALLBACK_TEXT.lower()
        assert "unavailable" in text
        assert "try again" in text
        # Must NOT falsely promise it can still reason for the user.
        assert "cv review" not in text
        assert "i can still assist" not in text


# ── Item 4: reasoning health states + /health flip ────────────────────────────

class TestReasoningHealth:
    def test_unknown_before_any_call(self, monkeypatch):
        monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-deepseek-key-for-tests")
        monkeypatch.setenv("HF_TOKEN", "fake-hf-token-for-tests")
        h = rt.get_reasoning_health()
        assert h["provider"] == "deepseek"
        assert h["configured"] is True
        assert h["reachable"] is None      # no call yet → unknown, never a claim
        assert h["degraded"] is False      # can't assert degraded without evidence
        assert h["fallback_available"] is True

    def test_success_marks_reachable(self):
        rt._record_reasoning_outcome("deepseek", reachable=True, model_attempted="deepseek-chat")
        h = rt.get_reasoning_health()
        assert h["reachable"] is True
        assert h["degraded"] is False
        assert h["last_error_category"] is None

    def test_degraded_only_when_unusable_and_no_fallback(self, monkeypatch):
        monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-deepseek-key-for-tests")
        monkeypatch.delenv("HF_TOKEN", raising=False)
        rt._record_reasoning_outcome(
            "deepseek", reachable=False, error_category="BadRequestError",
            status_code=400, provider_error_code="model_not_found",
            message="Model not found", model_attempted="deepseek-v4-flash",
        )
        h = rt.get_reasoning_health()
        assert h["degraded"] is True
        assert h["last_model_attempted"] == "deepseek-v4-flash"

    def test_not_degraded_when_fallback_available(self, monkeypatch):
        monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
        monkeypatch.setenv("HF_TOKEN", "fake-hf-token-for-tests")
        rt._record_reasoning_outcome("deepseek", reachable=False, error_category="BadRequestError", model_attempted="x")
        assert rt.get_reasoning_health()["degraded"] is False

    def test_health_endpoint_flips_degraded_and_leaks_no_secret(self, monkeypatch):
        monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-deepseek-key-for-tests")
        monkeypatch.delenv("HF_TOKEN", raising=False)
        rt._record_reasoning_outcome(
            "deepseek", reachable=False, error_category="BadRequestError",
            status_code=400, provider_error_code="model_not_found",
            message="Model not found", model_attempted="deepseek-v4-flash",
        )
        from fastapi.testclient import TestClient
        from src.api.app import app

        r = TestClient(app).get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "degraded"
        rp = body["reasoning_provider"]
        assert rp["degraded"] is True
        assert rp["last_status_code"] == 400
        assert rp["last_provider_error_code"] == "model_not_found"
        assert rp["last_model_attempted"] == "deepseek-v4-flash"
        # No key value ever appears in the health payload.
        assert "fake-deepseek-key-for-tests" not in r.text


# ── Item 3: context-assembly smoke against NULL / missing optional fields ──────

class TestContextAssemblySmoke:
    def _build_ctx(self, docs):
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI.__new__(RicoChatAPI)
        api._memory = MagicMock()
        api._memory.load_chat_history.return_value = []
        mock_db = MagicMock()
        mock_db.available = True
        mock_db.list_user_documents.return_value = docs
        with patch("src.rico_db.RicoDB", return_value=mock_db), \
             patch.object(api, "_get_recent_messages", return_value=[]), \
             patch.object(api, "_recent_jobs_summary", return_value=""):
            return api._build_openai_context(None, user_id="u@x.com")

    def test_documents_for_llm_survives_null_and_weird_fields(self):
        from src.rico_chat_api import RicoChatAPI

        rows = [
            {},                                                                    # empty row
            {"id": None, "file_size": None, "doc_type": "cv", "is_primary": True},  # NULL file_size (prod shape)
            {"file_size": 0, "filename": "Nehad_Zoher_Emirates_ID.pdf", "doc_type": "cv", "is_primary": True},  # zero-byte
            {"file_size": "0", "doc_type": "cv", "is_primary": True},               # file_size as str
            {"file_size": 88000, "doc_type": "cv", "is_primary": True, "skills_count": None, "years_experience": None, "filename": "a.pdf"},
        ]
        out = RicoChatAPI._documents_for_llm(rows)  # must not raise
        assert isinstance(out, list)
        assert len(out) == 4  # only the int-zero-byte row is excluded

    def test_build_openai_context_survives_null_fields(self):
        docs = [
            {"id": "d1", "file_size": None, "doc_type": "cv", "is_primary": True,
             "skills_count": None, "years_experience": None, "filename": "x.pdf"},
            {"id": "d2", "file_size": 0, "doc_type": "other", "is_primary": False, "filename": "empty.pdf"},
        ]
        ctx = self._build_ctx(docs)  # must not raise
        up = ctx.get("uploaded_documents", [])
        # the 0-byte row (d2) is excluded from the LLM copy; d1 survives
        assert all(d["document_id"] != "d2" for d in up)
