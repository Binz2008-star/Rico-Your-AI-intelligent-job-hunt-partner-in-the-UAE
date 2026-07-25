"""
tests/test_reasoning_provider_hardening.py

Deterministic proof for the remaining reasoning-provider-observability items and
the nine merge-gate conditions. No live provider, no real DB, no credentials, no
network — every provider/stream/models call is mocked.

Coverage map (items → tests):
  1. fixed error-category vocabulary + categoriser        → TestErrorCategoriser
  2. /models pre-check (advisory, fail-soft, short cache) → TestModelsPrecheck
  3. /ready endpoint (503 when no reachable valid model)  → TestReadyEndpoint
  4. no-silent-None guard on the HuggingFace cascade      → TestHuggingFaceCascadeGuard
  5. complete health fields + per-attempt elapsed         → TestHealthFieldsComplete
  6. deterministic tests for all of the above             → (this whole file)

Merge-gate map (each proven, never asserted in prose):
  G1 model identifier attempted        → test_gate1_model_identifier_attempted
  G2 duration of each attempt          → test_gate2_duration_of_each_attempt
  G3 failure classified (timeout/400/  → test_gate3_* (categoriser matrix)
     429/5xx/connection)
  G4 fallback engaged on primary       → test_gate4_fallback_engaged_when_primary_timed_out
     timeout
  G5 which model served the success    → test_gate5_which_model_served
  G6 heavy prompt not "unavailable"    → test_gate6_heavy_prompt_tries_fallback_before_unavailable
     before fallback tried
  G7 /health degraded not ok on loss   → test_gate7_health_degraded_not_ok
  G8 no secret/PII in log or health    → test_gate8_no_secret_in_log_or_health
  G9 stream emits MULTIPLE incremental → TestStreamIsIncrementalNotBlob
     frames, first before last
"""
from __future__ import annotations

import logging
import os
import time
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "x" * 32)

import src.rico_openai_runtime as rt


# ── isolation ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_module_state():
    saved_outcome = dict(rt._LAST_REASONING_OUTCOME)
    saved_models = dict(rt._MODELS_STATUS)
    for k in rt._LAST_REASONING_OUTCOME:
        rt._LAST_REASONING_OUTCOME[k] = None
    rt._MODELS_STATUS.update({
        "provider": None, "reachable": None, "available_models": None,
        "error_category": None, "checked_at": None, "_checked_monotonic": None,
    })
    yield
    rt._LAST_REASONING_OUTCOME.update(saved_outcome)
    rt._MODELS_STATUS.update(saved_models)


class _FakeErr(Exception):
    def __init__(self, msg, status_code=None, code=None):
        super().__init__(msg)
        self.status_code = status_code
        self.code = code


def _deepseek_env(monkeypatch, *, hf=False):
    monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-fake-deepseek-key-for-tests")
    if hf:
        monkeypatch.setenv("HF_TOKEN", "hf-fake-token-for-tests")
    else:
        for k in ("HF_TOKEN", "HF_API_TOKEN", "HF_API_KEY", "HUGGINGFACE_API_KEY"):
            monkeypatch.delenv(k, raising=False)


# ── Item 1: fixed error-category vocabulary + categoriser ─────────────────────

class TestErrorCategoriser:
    def test_vocabulary_is_the_exact_fixed_set(self):
        assert rt.ERROR_CATEGORIES == (
            "not_configured", "invalid_configuration", "unsupported_model",
            "authentication", "insufficient_balance", "rate_limited", "timeout",
            "connection", "provider_4xx", "provider_5xx", "response_contract", "unknown",
        )

    def test_every_result_is_in_the_vocabulary(self):
        samples = [
            dict(status_code=429), dict(status_code=401), dict(status_code=403),
            dict(status_code=402), dict(status_code=400), dict(status_code=404),
            dict(status_code=418), dict(status_code=500), dict(status_code=503),
            dict(error_type="ReadTimeout"), dict(error_type="APIConnectionError"),
            dict(error_type="EmptyStream"), dict(key_present=False), dict(),
        ]
        for s in samples:
            assert rt.categorize_error(**s) in rt.ERROR_CATEGORIES

    # G3: the failure is classified into distinct, correct buckets.
    def test_gate3_timeout(self):
        assert rt.categorize_error(error_type="ReadTimeout", message="read timed out") == "timeout"
        assert rt.categorize_error(error_type="TimeoutError") == "timeout"

    def test_gate3_connection(self):
        assert rt.categorize_error(error_type="APIConnectionError") == "connection"
        assert rt.categorize_error(message="Connection refused") == "connection"

    def test_gate3_400_unsupported_vs_invalid(self):
        # 400 that names a retired/unknown model → unsupported_model (deterministic-ish)
        assert rt.categorize_error(status_code=400, provider_error_code="model_not_found") == "unsupported_model"
        assert rt.categorize_error(status_code=400, message="Model deepseek-chat does not exist") == "unsupported_model"
        # 400 that is a plain malformed request → invalid_configuration
        assert rt.categorize_error(status_code=400, message="invalid parameter foo") == "invalid_configuration"

    def test_gate3_429_rate_limited(self):
        assert rt.categorize_error(status_code=429) == "rate_limited"

    def test_gate3_5xx(self):
        assert rt.categorize_error(status_code=500) == "provider_5xx"
        assert rt.categorize_error(status_code=503) == "provider_5xx"

    def test_authentication_and_balance_and_notconfigured(self):
        assert rt.categorize_error(status_code=401) == "authentication"
        assert rt.categorize_error(status_code=403) == "authentication"
        assert rt.categorize_error(status_code=402) == "insufficient_balance"
        assert rt.categorize_error(message="Insufficient Balance") == "insufficient_balance"
        assert rt.categorize_error(key_present=False) == "not_configured"

    def test_response_contract_and_other_4xx_and_unknown(self):
        assert rt.categorize_error(error_type="EmptyStream") == "response_contract"
        assert rt.categorize_error(message="returned empty text") == "response_contract"
        assert rt.categorize_error(status_code=418) == "provider_4xx"
        assert rt.categorize_error() == "unknown"

    def test_canonical_category_is_wired_into_failure_payload_not_raw_class(self, monkeypatch):
        _deepseek_env(monkeypatch)
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = _FakeErr(
            "Model not found", status_code=400, code="model_not_found")
        with patch.object(rt, "_build_client", return_value=fake_client):
            result = rt.call_openai_minimal("hi", provider="deepseek")
        # canonical vocabulary value, not the exception class name
        assert result["error_category"] == "unsupported_model"
        assert result["error_category"] in rt.ERROR_CATEGORIES
        # health surfaces the canonical category too
        assert rt.get_reasoning_health()["error_category"] == "unsupported_model"


# ── Item 2: /models pre-check (advisory, fail-soft, short cache) ───────────────

def _fake_models_client(ids):
    client = MagicMock()
    listing = MagicMock()
    listing.data = [MagicMock(id=i) for i in ids]
    client.models.list.return_value = listing
    return client


class TestModelsPrecheck:
    def test_probe_populates_available_set(self, monkeypatch):
        _deepseek_env(monkeypatch)
        with patch.object(rt, "_build_client", return_value=_fake_models_client(
                ["deepseek-v4-flash", "deepseek-v4-pro"])):
            rt.refresh_model_availability("deepseek", force=True)
        assert rt.is_model_supported("deepseek-v4-flash") is True
        assert rt.is_model_supported("some-retired-id") is False
        assert rt.get_models_status()["reachable"] is True
        assert rt.get_models_status()["available_count"] == 2

    def test_advisory_skip_drops_absent_but_never_empties(self, monkeypatch):
        _deepseek_env(monkeypatch)
        with patch.object(rt, "_build_client", return_value=_fake_models_client(["deepseek-v4-pro"])):
            rt.refresh_model_availability("deepseek", force=True)
        # v4-flash absent → dropped; v4-pro kept
        assert rt._advisory_chain(["deepseek-v4-flash", "deepseek-v4-pro"]) == ["deepseek-v4-pro"]
        # if ALL are absent, the chain is returned untouched (never refuse to serve)
        assert rt._advisory_chain(["x-only", "y-only"]) == ["x-only", "y-only"]

    def test_failsoft_on_probe_error_serves_chain_untouched(self, monkeypatch):
        _deepseek_env(monkeypatch)
        client = MagicMock()
        client.models.list.side_effect = _FakeErr("boom", status_code=None)
        with patch.object(rt, "_build_client", return_value=client):
            rt.refresh_model_availability("deepseek", force=True)
        assert rt._MODELS_STATUS["reachable"] is False
        assert rt._MODELS_STATUS["available_models"] is None
        assert rt.is_model_supported("deepseek-v4-flash") is None  # unknown, not False
        assert rt._advisory_chain(["deepseek-v4-flash"]) == ["deepseek-v4-flash"]

    def test_empty_data_array_carries_on_untouched(self, monkeypatch):
        _deepseek_env(monkeypatch)
        with patch.object(rt, "_build_client", return_value=_fake_models_client([])):
            rt.refresh_model_availability("deepseek", force=True)
        # empty list must NOT be read as "every model unsupported"
        assert rt._MODELS_STATUS["available_models"] is None
        assert rt.is_model_supported("deepseek-v4-flash") is None
        assert rt._advisory_chain(["deepseek-v4-flash", "deepseek-v4-pro"]) == \
            ["deepseek-v4-flash", "deepseek-v4-pro"]

    def test_not_configured_when_key_absent(self, monkeypatch):
        monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        rt.refresh_model_availability("deepseek", force=True)
        assert rt._MODELS_STATUS["reachable"] is False
        assert rt._MODELS_STATUS["error_category"] == "not_configured"

    def test_advisory_verdict_expires_after_short_window(self, monkeypatch):
        _deepseek_env(monkeypatch)
        with patch.object(rt, "_build_client", return_value=_fake_models_client(["deepseek-v4-pro"])):
            rt.refresh_model_availability("deepseek", force=True)
        assert rt.is_model_supported("deepseek-v4-flash") is False  # fresh → advisory active
        # age the probe past the advisory window → verdict expires to "unknown"
        rt._MODELS_STATUS["_checked_monotonic"] = time.monotonic() - (rt._MODELS_ADVISORY_WINDOW_SECONDS + 1)
        assert rt.is_model_supported("deepseek-v4-flash") is None
        assert rt._advisory_chain(["deepseek-v4-flash", "deepseek-v4-pro"]) == \
            ["deepseek-v4-flash", "deepseek-v4-pro"]

    def test_chat_path_never_probes_models(self, monkeypatch):
        # A user chat turn must NEVER trigger the /models discovery round-trip.
        _deepseek_env(monkeypatch)
        client = _fake_models_client(["deepseek-v4-flash"])
        client.chat.completions.create.return_value = _chat_response("hello")
        with patch.object(rt, "_build_client", return_value=client):
            rt.call_openai_minimal("hi", provider="deepseek")
        client.models.list.assert_not_called()


def _chat_response(text):
    resp = MagicMock()
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp.choices = [choice]
    return resp


# ── Item 3: /ready endpoint ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.api.app import app
    return TestClient(app, raise_server_exceptions=False)


class TestReadyEndpoint:
    def test_ready_200_when_configured_and_models_unknown(self, client, monkeypatch):
        _deepseek_env(monkeypatch)
        r = client.get("/ready")
        assert r.status_code == 200
        assert r.json()["ready"] is True

    def test_ready_503_when_not_configured(self, client, monkeypatch):
        monkeypatch.setenv("RICO_AI_PROVIDER", "deepseek")
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        r = client.get("/ready")
        assert r.status_code == 503
        body = r.json()
        assert body["ready"] is False
        assert "not_configured" in body["reasons"]

    def test_ready_503_when_no_chain_model_is_valid(self, client, monkeypatch):
        _deepseek_env(monkeypatch)
        # a FRESH successful probe that lists none of the resolved chain
        rt._MODELS_STATUS.update({
            "provider": "deepseek", "reachable": True,
            "available_models": frozenset({"totally-different-model"}),
            "error_category": None, "checked_at": rt._now_iso(),
            "_checked_monotonic": time.monotonic(),
        })
        r = client.get("/ready")
        assert r.status_code == 503
        assert "no_supported_model" in r.json()["reasons"]

    def test_ready_is_cache_only_no_upstream_probe(self, client, monkeypatch):
        # An inbound /ready must never trigger an outbound (billable) provider call.
        _deepseek_env(monkeypatch)
        with patch.object(rt, "refresh_model_availability") as probe:
            client.get("/ready")
        probe.assert_not_called()

    def test_health_stays_200_even_when_degraded(self, client, monkeypatch):
        _deepseek_env(monkeypatch)
        rt._record_reasoning_outcome(
            "deepseek", reachable=False, error_category="unsupported_model",
            status_code=400, model_attempted="deepseek-v4-flash",
        )
        r = client.get("/health")
        assert r.status_code == 200  # never restart-loops Render's liveness probe
        assert r.json()["status"] == "degraded"


# ── Item 4: no-silent-None guard on the HuggingFace cascade ───────────────────

class TestHuggingFaceCascadeGuard:
    def _agent(self):
        from src.rico_openai_agent import RicoOpenAIAgent
        return RicoOpenAIAgent()

    def test_hf_returns_none_records_engaged_but_failed_and_logs(self, monkeypatch, caplog):
        _deepseek_env(monkeypatch, hf=True)
        agent = self._agent()
        # premium (deepseek) fails; HF backup returns None (silent failure)
        fail = {"success": False, "text": rt._FALLBACK_TEXT, "error": "x",
                "error_code": "reasoning_provider_unavailable"}
        with (
            patch("src.rico_openai_agent.call_openai_minimal", return_value=fail),
            patch.object(agent, "_call_hf_free", return_value=None),
            caplog.at_level(logging.ERROR),
        ):
            agent.respond("give me one CV tip")
        h = rt.get_reasoning_health()
        assert h["fallback_engaged"] is True
        assert h["fallback_succeeded"] is False
        assert any("reasoning_fallback_empty" in rec.message for rec in caplog.records)

    def test_hf_success_records_engaged_and_succeeded(self, monkeypatch):
        _deepseek_env(monkeypatch, hf=True)
        agent = self._agent()
        fail = {"success": False, "text": rt._FALLBACK_TEXT}
        good = {"type": "hf_response", "message": "Use metric numbers.", "provider": "huggingface",
                "model": "HuggingFaceH4/zephyr-7b-beta"}
        with (
            patch("src.rico_openai_agent.call_openai_minimal", return_value=fail),
            patch.object(agent, "_call_hf_free", return_value=good),
        ):
            out = agent.respond("give me one CV tip")
        assert out["provider"] == "huggingface"
        h = rt.get_reasoning_health()
        assert h["fallback_engaged"] is True
        assert h["fallback_succeeded"] is True

    def test_guard_does_not_run_inside_call_openai_minimal(self, monkeypatch):
        # call_openai_minimal must NOT touch the HF fallback bookkeeping.
        _deepseek_env(monkeypatch, hf=True)
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = _FakeErr("boom", status_code=500)
        with patch.object(rt, "_build_client", return_value=fake_client):
            rt.call_openai_minimal("hi", provider="deepseek")
        assert rt._LAST_REASONING_OUTCOME["fallback_engaged"] is None


# ── Item 5: complete health fields + per-attempt elapsed ──────────────────────

class TestHealthFieldsComplete:
    def test_health_has_all_required_fields(self, monkeypatch):
        _deepseek_env(monkeypatch, hf=True)
        h = rt.get_reasoning_health()
        for key in ("provider", "configured", "model_chain", "fallback_exists",
                    "reachable", "last_checked_at", "last_success_at", "last_status",
                    "error_category", "attempts", "last_elapsed_ms", "models_precheck",
                    "last_stream_frames"):
            assert key in h, f"missing health field: {key}"
        assert h["model_chain"] == ["deepseek-v4-flash", "deepseek-v4-pro"]
        assert h["fallback_exists"] is True

    def test_no_secret_in_health_output(self, monkeypatch):
        import json
        _deepseek_env(monkeypatch)
        rt._record_reasoning_outcome(
            "deepseek", reachable=False, error_category="authentication",
            status_code=401, message="Bad key sk-fake-deepseek-key-for-tests in body",
            model_attempted="deepseek-v4-flash",
        )
        blob = json.dumps(rt.get_reasoning_health())
        assert "sk-fake-deepseek-key-for-tests" not in blob
        assert "sk-***REDACTED***" in blob or "REDACTED" in blob

    # G1 + G2 + G5: model attempted, per-attempt duration, model that served.
    def test_gate1_model_identifier_attempted(self, monkeypatch):
        _deepseek_env(monkeypatch)
        client = MagicMock()
        client.chat.completions.create.return_value = _chat_response("ok")
        with patch.object(rt, "_build_client", return_value=client):
            result = rt.call_openai_minimal("hi", provider="deepseek")
        assert result["attempts"][0]["model"] == "deepseek-v4-flash"
        assert rt.get_reasoning_health()["last_model_attempted"] == "deepseek-v4-flash"

    def test_gate2_duration_of_each_attempt(self, monkeypatch):
        _deepseek_env(monkeypatch)
        calls = []

        def create(model, **kw):
            calls.append(model)
            if model == "deepseek-v4-flash":
                raise _FakeErr("Model not found", status_code=400, code="model_not_found")
            return _chat_response("served")

        client = MagicMock()
        client.chat.completions.create.side_effect = create
        with patch.object(rt, "_build_client", return_value=client):
            result = rt.call_openai_minimal("hi", provider="deepseek")
        attempts = result["attempts"]
        assert len(attempts) == 2
        for a in attempts:
            assert isinstance(a["elapsed_ms"], int) and a["elapsed_ms"] >= 0
        # failed attempt carries a canonical category, success carries None
        assert attempts[0]["category"] == "unsupported_model"
        assert attempts[0]["ok"] is False
        assert attempts[1]["ok"] is True

    def test_gate5_which_model_served(self, monkeypatch):
        _deepseek_env(monkeypatch)

        def create(model, **kw):
            if model == "deepseek-v4-flash":
                raise _FakeErr("nope", status_code=400, code="model_not_found")
            return _chat_response("from pro")

        client = MagicMock()
        client.chat.completions.create.side_effect = create
        with patch.object(rt, "_build_client", return_value=client):
            result = rt.call_openai_minimal("hi", provider="deepseek")
        assert result["success"] is True
        assert result["model"] == "deepseek-v4-pro"  # the model that actually served
        assert result["text"] == "from pro"


# ── Merge gates 4, 6, 7, 8 ────────────────────────────────────────────────────

class TestMergeGates:
    def test_gate4_fallback_engaged_when_primary_timed_out(self, monkeypatch):
        # Non-stream: a primary TIMEOUT must trigger the hop to the fallback model.
        _deepseek_env(monkeypatch)
        seen = []

        def create(model, **kw):
            seen.append(model)
            if model == "deepseek-v4-flash":
                raise TimeoutError("read timed out")
            return _chat_response("recovered")

        client = MagicMock()
        client.chat.completions.create.side_effect = create
        with patch.object(rt, "_build_client", return_value=client):
            result = rt.call_openai_minimal("heavy", provider="deepseek")
        assert result["success"] is True
        assert seen == ["deepseek-v4-flash", "deepseek-v4-pro"]
        assert result["attempts"][0]["category"] == "timeout"

    def test_gate6_heavy_prompt_tries_fallback_before_unavailable(self, monkeypatch):
        # A heavy prompt whose primary fails must NOT return the unavailable text
        # until the fallback has actually been attempted.
        _deepseek_env(monkeypatch)

        def create(model, **kw):
            if model == "deepseek-v4-flash":
                raise _FakeErr("overloaded", status_code=503)
            return _chat_response("A thorough three-part answer.")

        client = MagicMock()
        client.chat.completions.create.side_effect = create
        with patch.object(rt, "_build_client", return_value=client):
            result = rt.call_openai_minimal("write me three cover letters", provider="deepseek")
        assert result["success"] is True
        assert result["text"] != rt._FALLBACK_TEXT
        assert [a["model"] for a in result["attempts"]] == ["deepseek-v4-flash", "deepseek-v4-pro"]

    def test_gate7_health_degraded_not_ok(self, monkeypatch):
        _deepseek_env(monkeypatch)  # no HF fallback
        rt._record_reasoning_outcome(
            "deepseek", reachable=False, error_category="unsupported_model",
            status_code=400, model_attempted="deepseek-v4-flash",
        )
        assert rt.get_reasoning_health()["degraded"] is True

    def test_gate7_failed_fallback_still_degraded_even_with_hf_configured(self, monkeypatch):
        # A backup that fails invisibly must still ring the alarm.
        _deepseek_env(monkeypatch, hf=True)
        rt._record_reasoning_outcome(
            "deepseek", reachable=False, error_category="unsupported_model",
            model_attempted="deepseek-v4-flash",
        )
        rt.record_fallback_outcome(engaged=True, succeeded=False,
                                   error_category="response_contract")
        assert rt.get_reasoning_health()["degraded"] is True

    def test_gate8_no_secret_in_log_or_health(self, monkeypatch, caplog):
        # Two distinct guarantees:
        #  (a) an API key that leaks into an upstream error string is REDACTED in
        #      both the log and the health output;
        #  (b) the user's own prompt text and profile content are NEVER echoed
        #      into a log or the health output (Rico never routes user content
        #      into either).
        _deepseek_env(monkeypatch)
        secret = "sk-live-DEEPSEEKKEY0123456789abcdef"
        prompt_pii = "Roben Edwan wants a compliance officer role and earns 45000 AED"
        profile_pii = "PASSPORT A1234567 : private banking client list"
        fake_client = MagicMock()
        # Provider echoes the key in its error body (the exact leak we redact).
        fake_client.chat.completions.create.side_effect = _FakeErr(
            f"401 Unauthorized: bad key {secret}", status_code=401)
        with caplog.at_level(logging.DEBUG):
            with patch.object(rt, "_build_client", return_value=fake_client):
                rt.call_openai_minimal(prompt_pii, profile_context=profile_pii, provider="deepseek")

        import json
        health_blob = json.dumps(rt.get_reasoning_health())
        log_blob = "\n".join(r.getMessage() for r in caplog.records)

        # (a) the key (and any partial key) never appears un-redacted.
        assert secret not in health_blob
        assert secret not in log_blob
        assert "DEEPSEEKKEY" not in health_blob
        assert "DEEPSEEKKEY" not in log_blob
        # (b) neither the user's prompt nor profile content is ever logged or surfaced.
        for pii in (prompt_pii, profile_pii, "Roben Edwan", "PASSPORT A1234567", "45000 AED"):
            assert pii not in health_blob, f"user content leaked into health: {pii!r}"
            assert pii not in log_blob, f"user content leaked into log: {pii!r}"


# ── Gate 9: the stream is incremental, NOT a single buffered blob ─────────────

class _Delta:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.delta = _Delta(content)


class _Chunk:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _LazyStream:
    """A provider stream that RECORDS the order in which chunks are pulled, so a
    test can prove the runtime yields each token as it arrives rather than
    buffering the whole answer into a single blob."""

    def __init__(self, texts, produced_log):
        self._texts = texts
        self._log = produced_log

    def __iter__(self):
        for t in self._texts:
            self._log.append(t)
            yield _Chunk(t)


class TestStreamIsIncrementalNotBlob:
    def test_gate9_runtime_streams_incrementally_multiple_frames(self, monkeypatch):
        _deepseek_env(monkeypatch)
        produced: list = []

        def create(model, **kw):
            assert kw.get("stream") is True
            return _LazyStream(["The ", "first ", "part ", "then more."], produced)

        client = MagicMock()
        client.chat.completions.create.side_effect = create
        with patch.object(rt, "_build_client", return_value=client):
            gen = rt.call_openai_stream("write me a long answer", provider="deepseek")
            first = next(gen)                 # pull ONLY the first output frame
            # Lazy incremental: only the FIRST source chunk has been produced so far —
            # a buffered-blob implementation would have pulled all four before yielding.
            assert produced == ["The "]
            assert first == "The "
            rest = list(gen)                  # drain the remainder

        frames = [first] + rest
        # MULTIPLE incremental frames (a single-frame 200 is the defect, not a pass).
        assert len(frames) == 4
        assert "".join(frames) == "The first part then more."
        # first frame strictly precedes the last in production order
        assert produced.index("The ") < produced.index("then more.")
        # frame-count + first-frame latency recorded in observability
        h = rt.get_reasoning_health()
        assert h["last_stream_frames"] == 4
        assert isinstance(h["last_first_frame_ms"], int)

    def test_gate9_wire_emits_multiple_token_frames_not_one_blob(self, client, monkeypatch):
        # End-to-end through the real SSE endpoint + real call_openai_stream: the
        # wire must carry MULTIPLE `data: {"type":"token"}` frames, not one blob.
        _deepseek_env(monkeypatch)
        produced: list = []

        def create(model, **kw):
            return _LazyStream(["Point one. ", "Point two. ", "Point three."], produced)

        stream_client = MagicMock()
        stream_client.chat.completions.create.side_effect = create

        from src.services.chat_service import ChatPreflight
        from src.services.subscription_gating import GateCheck
        gate = GateCheck(allowed=True, feature="monthly_ai_message_limit", usage=0,
                         limit=300, remaining=100, plan="free", message="ok")
        with (
            patch("src.api.routers.rico_chat.get_current_user", return_value={"email": "u@example.com"}),
            patch("src.services.chat_service.run_chat_preflight",
                  return_value=ChatPreflight(terminal=None, gate=gate)),
            patch("src.services.chat_service.should_stream_ai", return_value=True),
            patch("src.repositories.profile_repo.get_profile", return_value=None),
            patch("src.rico_chat_api.RicoChatAPI._build_openai_context", return_value={}),
            patch("src.rico_chat_api.RicoChatAPI._append_chat"),
            patch.object(rt, "_build_client", return_value=stream_client),
        ):
            res = client.post("/api/v1/rico/chat/stream", json={"message": "give me three points"})
        assert res.status_code == 200  # 200, but that is NOT the proof — the frames are
        token_frames = res.text.count('"type": "token"') + res.text.count('"type":"token"')
        assert token_frames >= 3, f"expected multiple incremental token frames, got {token_frames}"
        assert res.text.count(rt._FALLBACK_TEXT) == 0  # never the buffered fallback blob
