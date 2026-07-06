---
name: check-rico-ai
description: Read-only audit of Rico Hunt AI provider routing. Verify RICO_AI_PROVIDER env var, fallback chain, and provider health without calling live AI APIs.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
---

# check-rico-ai

Read-only audit of Rico Hunt AI provider routing. This skill **never calls live OpenAI, DeepSeek, HuggingFace, or JSearch APIs**. It only inspects code and environment variables.

## What it verifies

1. `RICO_AI_PROVIDER` is set to a supported provider (`openai`, `deepseek`, `huggingface`, or keyword fallback).
2. The active provider matches the fallback chain described in `CLAUDE.md`:
   - `deepseek` → HuggingFace → keyword/templated fallback
   - `openai` → fallback
3. `src/rico_openai_agent.py` routing logic reflects the provider chain.
4. `src/rico_env.py` health report fields (`*_key_present`, `ready_for_*`, `hf_available`) are computed at runtime, not static env vars.
5. Required API keys are present as env vars but their values are not exposed.

## Quick checks

```bash
# Show active provider and keys (values hidden)
echo "RICO_AI_PROVIDER=$RICO_AI_PROVIDER"
echo "OPENAI_API_KEY set: $([ -n "$OPENAI_API_KEY" ] && echo yes || echo no)"
echo "DEEPSEEK_API_KEY set: $([ -n "$DEEPSEEK_API_KEY" ] && echo yes || echo no)"
echo "HF_TOKEN set: $([ -n "$HF_TOKEN" ] && echo yes || echo no)"

# Inspect routing and health code
grep -n "RICO_AI_PROVIDER\|provider\|ready_for_\|hf_available" src/rico_openai_agent.py src/rico_env.py
```

## Files to read

- `src/rico_openai_agent.py` — provider routing logic
- `src/rico_env.py` — health report dataclass and runtime checks
- `CLAUDE.md` — AI Provider Routing section (source of truth)

## Safety constraints

- Do not print actual API key values.
- Do not call `openai.chat.completions.create`, DeepSeek, or HuggingFace endpoints.
- Do not set `RICO_AI_PROVIDER` to a different provider without approval.
