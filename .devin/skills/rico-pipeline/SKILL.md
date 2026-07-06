---
name: rico-pipeline
description: Run the Rico Hunt daily job bot / intelligence pipeline safely. Default to dry-run/read-only checks; require explicit approval before any real job processing or applications.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
---

# run-rico-pipeline

Run the Rico Hunt daily job bot / intelligence pipeline (`src/run_daily.py`). This skill is **safety-first**: it defaults to a dry-run or inspection step and requires explicit approval before any real execution.

## Entry point

```bash
python -m src.run_daily
```

Before running, verify the environment:

```bash
echo "RICO_ENABLE_AUTO_APPLY=$RICO_ENABLE_AUTO_APPLY"
echo "RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=$RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS"
echo "RICO_INTERACTIVE_APPLY=$RICO_INTERACTIVE_APPLY"
```

## Required safety defaults

- `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` must remain true in production.
- `RICO_ENABLE_AUTO_APPLY=false` is the safe production default.
- `RICO_INTERACTIVE_APPLY=false` is the safe production default.

If any of these values are unsafe, **stop and ask for approval** before running.

## Dry-run / inspection first

Before a real run, inspect what the pipeline would do:

```bash
# Syntax check only
python -m py_compile src/run_daily.py

# Read the pipeline entry to understand stages
sed -n '1,80p' src/run_daily.py
```

## When to run for real

Only run `python -m src.run_daily` when:
1. The user explicitly asked for a real pipeline run.
2. The safety env vars above are safe.
3. No production smoke testing is happening against live user accounts.
4. The run is limited to the intended scope (e.g., a specific provider or role).

## Never do this

- Do not set `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=false` to "make it work".
- Do not bypass `agent_runtime.handle_action()` and call repositories directly.
- Do not run the pipeline against production user accounts without explicit approval.
- Do not trigger the cron-only `POST /api/v1/pipeline/reminders` without `X-Cron-Secret`.
