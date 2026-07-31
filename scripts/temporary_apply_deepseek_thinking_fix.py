from __future__ import annotations

from pathlib import Path

RUNTIME = Path("src/rico_openai_runtime.py")
TESTS = Path("tests/test_reasoning_provider_hardening.py")
HANDOFF = Path("AI_WORKSPACE/HANDOFFS/2026-07-31-deepseek-thinking-contract-hardening.md")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


runtime = RUNTIME.read_text(encoding="utf-8")

runtime = replace_once(
    runtime,
    "    return OpenAI(**kwargs)\n\n\ndef _call_openai_responses(\n",
    "    return OpenAI(**kwargs)\n\n\ndef _deepseek_chat_request_options(*, stream: bool = False) -> Dict[str, Any]:\n"
    "    \"\"\"Explicit DeepSeek request contract for Rico's final-answer-only chat.\n\n"
    "    DeepSeek V4 thinking defaults are provider-controlled. Rico does not expose\n"
    "    chain-of-thought and requires a final `content` answer, so ordinary chat\n"
    "    calls disable thinking explicitly rather than inheriting an upstream default.\n"
    "    \"\"\"\n"
    "    options: Dict[str, Any] = {\n"
    "        \"extra_body\": {\"thinking\": {\"type\": \"disabled\"}},\n"
    "    }\n"
    "    if stream:\n"
    "        options[\"stream\"] = True\n"
    "    return options\n\n\n"
    "def _call_openai_responses(\n",
    "insert DeepSeek request helper",
)

runtime = replace_once(
    runtime,
    "    response = client.chat.completions.create(\n"
    "        model=model,\n"
    "        messages=messages,\n"
    "        max_tokens=(\n"
    "            _SMOKE_MAX_OUTPUT_TOKENS if smoke else _DEFAULT_MAX_OUTPUT_TOKENS\n"
    "        ),\n"
    "    )\n",
    "    response = client.chat.completions.create(\n"
    "        model=model,\n"
    "        messages=messages,\n"
    "        max_tokens=(\n"
    "            _SMOKE_MAX_OUTPUT_TOKENS if smoke else _DEFAULT_MAX_OUTPUT_TOKENS\n"
    "        ),\n"
    "        **_deepseek_chat_request_options(),\n"
    "    )\n",
    "wire non-streaming DeepSeek request",
)

runtime = replace_once(
    runtime,
    "                stream = client.chat.completions.create(\n"
    "                    model=model, messages=messages,\n"
    "                    max_tokens=_DEFAULT_MAX_OUTPUT_TOKENS, stream=True,\n"
    "                )\n",
    "                stream = client.chat.completions.create(\n"
    "                    model=model, messages=messages,\n"
    "                    max_tokens=_DEFAULT_MAX_OUTPUT_TOKENS,\n"
    "                    **_deepseek_chat_request_options(stream=True),\n"
    "                )\n",
    "wire streaming DeepSeek request",
)

RUNTIME.write_text(runtime, encoding="utf-8")

marker = "# ── DeepSeek explicit thinking contract ──────────────────────────────────────"
tests = TESTS.read_text(encoding="utf-8")
if marker in tests:
    raise RuntimeError("DeepSeek thinking-contract tests already present")

tests += r'''

# ── DeepSeek explicit thinking contract ──────────────────────────────────────

def _reasoning_chunk(*, content=None, reasoning_content=None):
    delta = MagicMock()
    delta.content = content
    delta.reasoning_content = reasoning_content
    choice = MagicMock()
    choice.delta = delta
    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def test_deepseek_non_stream_explicitly_disables_thinking(monkeypatch):
    _deepseek_env(monkeypatch)
    client = MagicMock()
    client.chat.completions.create.return_value = _chat_response("Final answer")

    with (
        patch.object(rt, "_build_client", return_value=client),
        patch.object(rt, "_deepseek_model_chain", return_value=["deepseek-v4-flash"]),
        patch.object(rt, "_advisory_chain", side_effect=lambda models, provider=None: models),
    ):
        result = rt.call_openai_minimal("hello", provider="deepseek")

    kwargs = client.chat.completions.create.call_args.kwargs
    assert result["success"] is True
    assert result["text"] == "Final answer"
    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "stream" not in kwargs


def test_deepseek_stream_explicitly_disables_thinking_and_never_yields_reasoning(monkeypatch):
    _deepseek_env(monkeypatch)
    client = MagicMock()
    client.chat.completions.create.return_value = iter([
        _reasoning_chunk(reasoning_content="private reasoning"),
        _reasoning_chunk(content="Final answer"),
    ])

    with (
        patch.object(rt, "_build_client", return_value=client),
        patch.object(rt, "_deepseek_model_chain", return_value=["deepseek-v4-flash"]),
        patch.object(rt, "_advisory_chain", side_effect=lambda models, provider=None: models),
    ):
        output = list(rt.call_openai_stream("hello", provider="deepseek"))

    kwargs = client.chat.completions.create.call_args.kwargs
    assert output == ["Final answer"]
    assert "private reasoning" not in "".join(output)
    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    assert kwargs["stream"] is True


def test_reasoning_only_stream_stays_fail_closed_and_falls_back_once(monkeypatch):
    _deepseek_env(monkeypatch)
    client = MagicMock()

    def create(*, model, **kwargs):
        assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
        if model == "deepseek-v4-flash":
            return iter([_reasoning_chunk(reasoning_content="private reasoning")])
        return iter([_reasoning_chunk(content="Fallback answer")])

    client.chat.completions.create.side_effect = create

    with (
        patch.object(rt, "_build_client", return_value=client),
        patch.object(
            rt,
            "_deepseek_model_chain",
            return_value=["deepseek-v4-flash", "deepseek-v4-pro"],
        ),
        patch.object(rt, "_advisory_chain", side_effect=lambda models, provider=None: models),
    ):
        output = list(rt.call_openai_stream("hello", provider="deepseek"))

    attempts = rt.get_reasoning_health()["attempts"]
    assert output == ["Fallback answer"]
    assert client.chat.completions.create.call_count == 2
    assert attempts[0]["model"] == "deepseek-v4-flash"
    assert attempts[0]["category"] == "response_contract"
    assert attempts[0]["ok"] is False
    assert attempts[1]["model"] == "deepseek-v4-pro"
    assert attempts[1]["ok"] is True


def test_openai_responses_request_contract_is_unchanged(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-openai-key-for-tests")
    client = MagicMock()
    response = MagicMock()
    response.output_text = "OpenAI answer"
    client.responses.create.return_value = response

    with patch.object(rt, "_build_client", return_value=client):
        result = rt.call_openai_minimal("hello", provider="openai")

    kwargs = client.responses.create.call_args.kwargs
    assert result["success"] is True
    assert result["text"] == "OpenAI answer"
    assert "extra_body" not in kwargs
    assert "thinking" not in kwargs
'''

TESTS.write_text(tests, encoding="utf-8")

HANDOFF.write_text(
    """# DeepSeek Thinking Contract Hardening — 2026-07-31

## Why this exists

Rico's ordinary chat runtime consumes only the provider's final `content` answer and intentionally does not expose `reasoning_content`. DeepSeek V4 thinking behavior is provider-controlled unless the request chooses it explicitly. Hermetic investigation proved that a reasoning-only completion is classified as `response_contract` and invokes fallback; the exact termination reason of the 2026-07-31 production event remains unverified.

This change removes an unsafe implicit provider default. It does not claim the production incident root cause was conclusively proven.

## Governance mapping

- **Vision:** Rico as an AI Career Operating System
- **Epic:** AI Response Reliability & Performance
- **Milestone:** Provider-contract reliability
- **Phase:** P1 bounded runtime hardening
- **Task:** `TASK-20260731-004`
- **Branch:** `fix/deepseek-thinking-contract`
- **Base:** `f5f5fd14aadfb63f3870a73169ee7b3da83b9c02`
- **Owner:** Rico Engineering
- **Source of truth:** `src/rico_openai_runtime.py` for runtime behavior; this handoff records the PR scope and verification boundary.
- **Update when:** the branch head, validation state, merge state, or post-merge smoke evidence changes.

## Objective

Make Rico's final-answer-only DeepSeek contract explicit by disabling thinking for ordinary streaming and non-streaming chat requests through one shared request-options helper.

## Scope

- Add one DeepSeek-specific request-options helper in `src/rico_openai_runtime.py`.
- Use it for ordinary DeepSeek streaming and non-streaming chat calls.
- Extend the already-enrolled reasoning-provider hardening suite.
- Preserve final-content validation and fail-closed fallback behavior.

## Explicit exclusions

- No model-order, timeout, retry, token-budget, prompt, grounding, frontend, environment, migration, Neon, or production configuration changes.
- No `reasoning_content` exposure, logging, persistence, or user-visible rendering.
- No claim of measured production latency improvement.
- No deployment or production smoke in this PR.

## Acceptance criteria

1. Both DeepSeek request paths send `extra_body={\"thinking\": {\"type\": \"disabled\"}}`.
2. OpenAI Responses API arguments remain unchanged.
3. Final `content` remains the only user-visible model output.
4. Reasoning-only or truly empty responses remain `response_contract` failures.
5. A genuine primary failure invokes the existing fallback exactly once.
6. Existing reasoning-provider hardening tests and test enumeration remain green.

## Risks

- DeepSeek may change or reject the provider-specific request field in a future API revision. Existing fail-closed categorization and fallback remain the mitigation.
- Disabling thinking may alter answer quality for some complex prompts. This PR intentionally favors predictable final-answer delivery for the current ordinary-chat contract. A separately governed reasoning mode would require a distinct product and architecture decision.

## Rollback

Revert the eventual squash merge commit. No database, environment, migration, or user-data rollback is required.

## Production verification still required after merge

1. Verify `/version` serves the exact merge SHA.
2. Run a secret-safe ordinary-chat smoke in Arabic and English.
3. Confirm Flash succeeds without fallback where previously reproducible.
4. Record attempt count, first-frame latency, total elapsed time, and provider health.
5. Confirm no `reasoning_content` appears in output, logs, or telemetry.

## Current state

Draft implementation only. Merge, deployment, and production smoke are not authorized by this record.
""",
    encoding="utf-8",
)

print("Applied bounded DeepSeek thinking-contract hardening.")
