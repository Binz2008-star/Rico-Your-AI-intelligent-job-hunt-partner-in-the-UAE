# DeepSeek Thinking Contract Hardening — 2026-07-31

## Why this exists

Rico's ordinary chat runtime consumes only the provider's final `content` answer and intentionally does not expose `reasoning_content`. DeepSeek V4 thinking behavior is provider-controlled unless the request chooses it explicitly. Hermetic investigation proved that a reasoning-only completion is classified as `response_contract` and invokes fallback; the exact termination reason of the 2026-07-31 production event remains unverified.

This change removes an unsafe implicit provider default. It does not claim the production incident root cause was conclusively proven.

## Governance mapping

- **Vision:** Rico as an AI Career Operating System
- **Epic:** AI Response Reliability & Performance
- **Milestone:** Provider-contract reliability
- **Phase:** P1 bounded runtime hardening
- **Task:** `TASK-20260731-004`
- **PR:** `#1478` (Draft)
- **Branch:** `fix/deepseek-thinking-contract`
- **Base:** `f5f5fd14aadfb63f3870a73169ee7b3da83b9c02`
- **Implementation commit:** `8ab58a1f6297c4b59f54ab520d61c9bc4feebb01`
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

1. Both DeepSeek request paths send `extra_body={"thinking": {"type": "disabled"}}`.
2. OpenAI Responses API arguments remain unchanged.
3. Final `content` remains the only user-visible model output.
4. Reasoning-only or truly empty responses remain `response_contract` failures.
5. A genuine primary failure invokes the existing fallback exactly once.
6. Existing reasoning-provider hardening tests and test enumeration remain green.

## Verified branch evidence

The bounded implementation was applied and verified in GitHub Actions before the temporary patch workflow and patch script deleted themselves from the branch.

- Python compile checks: **PASS**.
- `tests/test_reasoning_provider_hardening.py`: **41 passed**, 2 pre-existing warnings.
- Test enumeration guard: **PASS**; unexplained files `0` and frozen debt unchanged at `204`.
- `git diff --check`: **PASS**.
- Final PR file set after cleanup: runtime, focused existing test suite, and this handoff only.
- No live provider call, production credential, deployment, migration, Neon mutation, or production smoke was performed.

This targeted validation does not replace exact-head repository CI. The documentation update recording this evidence intentionally triggers a fresh PR synchronization so required checks can evaluate the final three-file diff.

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

Draft PR implementation is complete and targeted checks are green. Exact-head CI and independent review remain required. Merge, deployment, and production smoke are not authorized by this record.
