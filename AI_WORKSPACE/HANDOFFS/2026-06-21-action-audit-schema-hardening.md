# Handoff — Action Audit Schema Hardening

Date: 2026-06-21
Owner: Roben / Claude
Branch: `feat/action-audit-schema-hardening`
PR: #708 — `feat(audit): harden existing action_audit_log schema`
Status: Draft, open, unmerged
Head: `fb63a60a9ba0c35debdff2dfa734caf1c271a183`

## Current state

The stale PR queue was cleaned before implementation:

- Closed as superseded / not planned: #685, #695, #699
- Kept open and untouched: #688, #697

PR #708 is the current implementation candidate for audit schema hardening. It remains draft and must not be merged automatically.

## Goal

Harden the existing `action_audit_log` audit foundation without introducing a parallel audit, approval, or policy system.

## Scope implemented in #708

Changed files:

- `migrations/030_action_audit_log_hardening.sql`
- `src/repositories/audit_repo.py`
- `tests/unit/test_action_audit_schema_migration.py`
- `tests/unit/test_write_audit_log.py`

Main changes:

- Adds numbered migration `030_action_audit_log_hardening.sql`.
- Adds existing general-event fields `event_type` and `data` to `action_audit_log` through migration, not request-time code.
- Adds an event-type/time index.
- Adds a database-level trigger that rejects `UPDATE`, `DELETE`, and `TRUNCATE` on `action_audit_log`.
- Removes request-time `information_schema` checks and `ALTER TABLE` from `write_audit_log()`.
- Keeps existing action runtime and pending-permission system.
- Keeps `audit_repo` as the canonical audit repository.

## Explicit exclusions

PR #708 does not add or change:

- frontend
- `/ask`
- permission token format
- pending-permission behavior
- `agent_approval_tokens`
- duplicate HMAC approval infrastructure
- duplicate `audit_writer.py`
- parallel `policy_gate.py`
- `agent_audit_events`
- browser automation
- CV tailoring
- FitScorer

## Validation reported

Local validation reported by implementation agent:

```text
Focused tests: 27 passed
Python compilation: passed
Git diff check: passed
GitHub pytest, Playwright, Vercel: passed
```

PR body validation commands:

```text
python -m pytest tests/unit/test_write_audit_log.py tests/unit/test_action_audit_schema_migration.py tests/unit/test_607_correctness_fixes.py -q
27 passed in 0.90s

python -m py_compile src/repositories/audit_repo.py

git diff --check
```

## Review notes

Before marking #708 ready or merging:

1. Review `migrations/030_action_audit_log_hardening.sql` carefully.
2. Confirm migration ordering and rollback language.
3. Confirm no current code path updates/deletes/truncates `action_audit_log`.
4. Confirm production migration rollout plan.
5. Apply migration 030 before deploying the repository change.

## Risk notes

- `write_audit_log()` no longer creates `event_type` / `data` columns at request time.
- Migration 030 must be applied before the repository change is deployed to production.
- The append-only trigger intentionally blocks update/delete/truncate on `action_audit_log`.
- The migration was not run against production in #708.
- Local `psql` was unavailable; migration behavior is covered by static contract tests rather than local PostgreSQL execution.

## Current recommendation

Keep #708 draft for review.

Do not merge until migration 030 is reviewed and a safe Neon/production migration rollout is explicitly approved.
