# Handoff — Agentic Foundation Hardening Rollout

Date: 2026-06-21
Owner: Roben / Claude / ChatGPT
Status: production foundation updated

## Summary

Rico's Agentic Vision implementation has moved from docs/prototype into production backend hardening.

The current direction is: extend existing CAREER-OS systems, do not build parallel approval or audit systems.

## Recent production changes

### PR #700 — Job-key permission binding + denial audit

Status: merged and deployed
Merge commit: `1a4806577eb87a9f0c2a6efdd52cfaa1b8ba60f3`
Branch: `feat/agentic-foundation-hardening`

What changed:

- `src/services/pending_permissions.py`
  - `register()` and `validate_and_consume()` now accept optional `job_key`.
  - A permission issued for one job cannot be consumed for another job.
  - Job mismatch fails closed and does not consume the legitimate permission.
  - `None` or empty `job_key` preserves backward-compatible job-agnostic behavior.

- `src/services/permission_factory.py`
  - Apply permissions are bound to the job key at issuance.

- `src/api/routers/rico_chat.py`
  - `/actions/execute` forwards `req.job_key` to permission validation.
  - Denied execution attempts are logged through existing `audit_repo.log_action` with `result_status="denied"`.

Tests added or updated:

- `tests/test_pending_permissions_job_binding.py`
- `tests/test_permission_execute.py`

PR body verification:

- 165 passing tests, 0 regressions.

### PR #701 — Persist action audit rows

Status: merged
Merge commit: `25fb5c7ee2df3cf965abfdae23d0567e8956d8b2`

Problem fixed:

- `audit_repo._db_write()` inserted into `action_audit_log` but did not call `conn.commit()`.
- The missing commit meant action audit rows could be rolled back on connection close.
- This affected the denial audit records added in PR #700.

What changed:

- Added the missing commit after `action_audit_log` insert.
- Added regression coverage for successful writes, denied writes, and insert-error behavior.

PR body verification:

- Full audit + permission suite passed: 116 passed.
- One unrelated container-only dependency pin issue was noted and not caused by this PR.

### PR #702 — Persist application-attempt dedup rows

Status: merged
Merge commit: `8aa627f3229911d5ecfc09aa76289565918132fd`

Problem fixed:

- Two application-attempt writers saved dedup records without a commit and without guaranteed connection close.
- The dedup guard could fail to persist across runs.
- A DB connection could remain open after the write path.

What changed:

- `src/auto_apply.py`
- `src/naukrigulf_apply.py`

Both `_save_attempt()` implementations now commit after the upsert and close in `finally`.

Verification:

- PR body records `python -m py_compile src/auto_apply.py src/naukrigulf_apply.py`.
- Human update after merge: `pytest` green and `playwright` green.

## Current architecture decision

Do not implement a parallel HMAC approval-token table, parallel audit-event table, or duplicate policy gate unless a focused audit proves the existing systems cannot be extended.

Canonical current systems:

- Permission store: `src/services/pending_permissions.py`
- Permission creation: `src/services/permission_factory.py`
- Execution endpoint: `src/api/routers/rico_chat.py` `/actions/execute`
- Audit repository: `src/repositories/audit_repo.py`
- Audit table: `action_audit_log`
- Match explanation foundation: `rico_match_explainer`

## Open follow-ups

### 1. Permission TTL alignment

Known gap:

- Backend permission TTL is currently 900 seconds.
- `/ask` approval UI countdown is 300 seconds.

Recommended next PR:

- Branch: `feat/permission-ttl-alignment`
- Scope: backend TTL/tests only.
- No frontend unless strictly justified.
- No DB migration.
- No new approval/audit system.

### 2. Append-only audit hardening

Potential later PR:

- Decide whether to enforce append-only behavior on `action_audit_log` or add an additive `agent_audit_events` stream.
- Do not start before a small schema/risk review.
- This is larger than TTL alignment.

### 3. Update GitHub Intelligence Report

`docs/rico-agentic-vision-github-intelligence.md` should be updated before merge/use as canonical roadmap.

Needed correction:

- The report should no longer imply Rico is greenfield for approval/audit.
- It must acknowledge the existing permission/audit/match-explanation foundations.
- Roadmap should start from inventory/hardening, not duplicate systems.

## Do not do next

- Do not build `approval_token.py` as a duplicate of `pending_permissions.py`.
- Do not add new audit tables before deciding how they relate to `action_audit_log`.
- Do not wire `/ask` to real execution until TTL and foundation behavior are consistent.
- Do not start CV tailoring, FitScorer, browser automation, or outreach sending before foundation follow-ups are closed.

## Recommended immediate next action

Open a small PR:

```text
feat/permission-ttl-alignment
```

Acceptance criteria:

- Backend permission TTL is 300 seconds.
- Expired permissions fail after 300 seconds.
- One-time consume remains intact.
- Wrong user/action/job-key behavior from PR #700 remains intact.
- No DB migration.
- No frontend changes unless explicitly justified.
- Existing permission/action tests pass.
