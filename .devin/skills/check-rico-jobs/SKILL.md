---
name: check-rico-jobs
description: Read-only verification of Rico Hunt job fetching and scoring. Inspect JSearch adapter, provider fallback, and scoring pipeline without calling live APIs.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
---

# check-rico-jobs

Read-only verification of Rico Hunt job fetching and scoring. This skill **never calls live JSearch, RapidAPI, or job boards**. It only inspects code and configuration.

## What it verifies

1. JSearch adapter (`src/job_source_adapters/jsearch_adapter.py`) normalizes job data correctly.
2. Provider fallback and error handling exist when JSearch is unavailable.
3. Scoring pipeline uses the configured scorer without hardcoded thresholds for a single role.
4. Job actions (apply/save/skip/block/draft/why) go through `agent_runtime.handle_action()`.
5. No live job board credentials are logged or printed.

## Quick checks

```bash
# JSearch adapter structure
grep -n "class.*Adapter\|def search\|def normalize" src/job_source_adapters/jsearch_adapter.py

# Provider fallback
grep -n "jsearch\|RAPIDAPI_KEY\|JSEARCH_API_KEY" src/job_sources.py src/job_source_adapters/*.py

# Scoring pipeline
grep -n "score\|eligibility\|filter" src/llm_scorer.py src/eligibility_filter.py src/filter.py

# Actions go through agent_runtime
grep -n "handle_action" src/api/routers/actions.py src/agent/runtime.py
```

## Files to read

- `src/job_source_adapters/jsearch_adapter.py` — JSearch normalization
- `src/job_sources.py` — provider selection
- `src/llm_scorer.py` / `src/eligibility_filter.py` — scoring logic
- `src/api/routers/actions.py` — job action routes
- `src/agent/runtime.py` — action dispatcher

## Safety constraints

- Do not call live JSearch or RapidAPI endpoints.
- Do not run the full daily pipeline without approval (use `/rico-pipeline` for that).
- Do not special-case one target role or one user profile in scoring logic.
