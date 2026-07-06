---
name: test-rico
description: Run focused tests for Rico Hunt — backend pytest, frontend build/lint, and vitest. Use when asked to verify a change, run tests, check correctness, or validate a fix without the full smoke suite.
triggers:
  - user
  - model
---

# test-rico

Run focused tests for Rico Hunt. This skill is the **fast correctness path** — it does not start servers or hit live endpoints. It validates the changed area and stops as soon as there is enough evidence.

## Quick checks (run these first)

### Frontend build (catches TypeScript / import errors fast)

```bash
cd apps/web && npm run build
```

Expected: no errors, route list printed, exit 0.

### Frontend lint

```bash
cd apps/web && npm run lint
```

### Backend focused tests (core auth/webhook/onboarding isolation)

```bash
python -m pytest tests/test_jotform_webhook.py tests/test_jwt_user_isolation.py tests/test_onboarding_state.py -q
```

These ~94 tests run in ~2s and do not call live APIs or Neon.

## Full suites (when explicitly asked)

```bash
# Frontend unit tests
cd apps/web && npm run test

# Full backend test suite
python -m pytest tests/ -q --tb=short
```

## Known pre-existing failures

- `tests/test_agent.py` and `tests/test_agent_runtime.py` contain 6 pre-existing failures (`TestApplyServiceIndeedMethod`, `TestDraftAction`, `TestJobResolution`). They are gating failures only if you are changing the agent runtime. Do not silently fix them as part of an unrelated change.

## Cost rule

Stop after the focused checks if they pass. Only run the full suites when the change is large, risky, or the user explicitly asks for it.
