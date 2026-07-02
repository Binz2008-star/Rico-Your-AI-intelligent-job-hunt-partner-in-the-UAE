# Decisions

Use this file for decisions that affect product behavior, architecture, AI workflow, release policy, or contributor workflow.

## Decision template

```md
### DEC-YYYYMMDD-001 — <title>

Status: accepted | superseded | proposed
Date: YYYY-MM-DD
Owner: <name/tool>
Related task: TASK-YYYYMMDD-001

#### Context
<why this decision is needed>

#### Decision
<what was decided>

#### Consequences
- Positive:
- Negative/trade-off:

#### Follow-up
- [ ]
```

## Accepted decisions

### DEC-20260628-001 — No Dead UI Rule

Status: accepted
Date: 2026-06-28
Owner: Roben / Claude
Related task: PR #775 (cleanup); audit surfaced during P2-A production verification

#### Context

During P2-A production verification, a route audit found that `next.config.js` redirected 9 routes
to `/command` or `/flow`, while 7 of those routes still contained substantial `page.tsx` implementations
(48–576 lines each). The most notable case: `/onboarding` redirects to `/command`, but
`apps/web/app/onboarding/page.tsx` is 466 lines of real code including CV upload, classification,
and bilingual error messages — none of which is reachable in production.

This "redirect + live page" pattern creates an invisible class of dead code: it passes `npm run build`,
passes TypeScript, and passes CI, but is never executed by any user. It silently accumulates drift,
bugs, and maintenance debt without any signal.

#### Decision

**No route may redirect away while still keeping meaningful `page.tsx` code behind it.**

A route must be exactly one of:

1. **Active and reachable** — no redirect; the page is the live production UI.
2. **Redirect-only** — `next.config.js` redirect is the correct mechanism AND the `page.tsx` either does
   not exist or contains only a thin passthrough (e.g. `redirect("/command")`) with no meaningful logic.
3. **Removed** — route, redirect, and page file all deleted.

Hybrid state (redirect + real page.tsx) is prohibited. If a page cannot be made live yet, keep it
redirect-only with no implementation, or gate it behind a feature flag that makes the page reachable.

#### Consequences

- Positive: CI failures, type errors, and behavioral bugs in `page.tsx` files are guaranteed to matter —
  there is no silent dead-code escape hatch.
- Positive: redirect inventory in `next.config.js` is the single truthful routing contract.
- Trade-off: routes with meaningful page code that are intentionally hidden (future features, WIP)
  must live on a feature branch until they are either live or formally removed.

#### Follow-up

- [x] Phase A (2026-06-28): delete `/chat` and `/orchestrate` stubs; remove `/pipeline → /flow` redirect
      (no page file exists for `/pipeline`).
- [ ] Phase B: resolve `/dashboard`, `/onboarding`, `/jobs`, `/signals`, `/archive`, `/saved-searches` —
      each requires an explicit product decision: make live, strip to stub, or delete.


### DEC-20260621-003 — Action-audit hardening rolled out; migration drift surfaced and tracked

Status: accepted
Date: 2026-06-21
Owner: Roben / Claude
Related task: PR #708, issues #710, #711

#### Context

DEC-20260621-002 approved #708 as the draft implementation candidate for hardening the existing
`action_audit_log` (migration 030). This decision records the completed rollout and the production
migration drift it surfaced.

#### Decision

- Apply migration 030 to production Neon before deploying, then merge + deploy #708. Done:
  #708 merged at `9078d77`, migration 030 applied + verified in production, backend live on `9078d77`.
- Treat production migration drift as separate, gated cleanups — never bundled with #708:
  - #710 (`021_user_job_context_alt_url.sql`) applied + closed.
  - #711 (`005` `pipeline_runs`, `011` `rico_job_recommendations` unique index) logged, NOT applied
    (verify-first; 011 deletes rows).

#### Consequences

- Positive: audit log is now DB-enforced append-only; request-time DDL removed from `write_audit_log()`.
- Positive: a full `005`–`030` prod drift audit now exists and is repeatable.
- Trade-off: numbered migrations are still applied manually (no deploy-time runner) — the systemic
  root cause behind both 030's manual apply and the 021/005/011 drift.

#### Follow-up
- [ ] #711 — apply 005 (targeted) and 011 (verify-first) under explicit approval.
- [ ] Add a migration runner / CI gate so prod schema can't silently fall behind `main`.


### DEC-20260621-002 — Harden existing `action_audit_log`; do not build parallel audit/approval systems

Status: accepted
Date: 2026-06-21
Owner: Roben / Claude
Related task: PR #708

#### Context

After PR #706 merged, the canonical Agentic Vision foundation is the existing action runtime,
pending-permission system, and `action_audit_log`. PR #685 attempted a parallel audit and approval
foundation (`agent_audit_events`, `agent_approval_tokens`, duplicate `audit_writer.py`, and
parallel `policy_gate.py`), which creates duplicate-risk against the now-merged inventory guidance.

The audit repository also still had request-time schema mutation: `write_audit_log()` checked
`information_schema` and executed `ALTER TABLE action_audit_log ADD COLUMN ...` during normal
request handling.

#### Decision

Proceed with PR #708 as a draft implementation candidate on branch
`feat/action-audit-schema-hardening`.

Allowed direction:

- extend existing `action_audit_log`
- move `event_type` and `data` additions into numbered migration 030
- add database-level append-only protection where safe
- update focused `audit_repo` tests
- keep existing action runtime and pending-permission system

Explicitly not allowed:

- frontend or `/ask`
- permission token format changes
- `agent_approval_tokens`
- duplicate HMAC approval infrastructure
- duplicate `audit_writer.py`
- parallel `policy_gate.py`
- `agent_audit_events`
- browser automation
- CV tailoring
- FitScorer

Stale PR queue decision:

- #685 closed as superseded / duplicate-risk
- #695 closed as superseded by #706 and #707 workspace state
- #699 closed as template/unclear not planned
- #688 kept open only as preview/mock UX; do not merge, wire, or treat its 300-second timer as production truth
- #697 kept as a separate small bugfix candidate; do not mix with audit-schema hardening

#### Consequences

- Positive: keeps audit hardening on Rico's canonical audit path and avoids a second approval/audit stack.
- Positive: removes schema DDL from request-time repository code.
- Trade-off: migration 030 must be reviewed and applied before deploying the repository change, because `write_audit_log()` no longer creates missing columns at runtime.
- Trade-off: the append-only trigger intentionally blocks update/delete/truncate operations on `action_audit_log`; this is correct for audit integrity but requires explicit rollback approval if future maintenance needs mutation.

#### Verification

Implementation report for #708:

- PR: #708 draft, open, unmerged
- Head: `fb63a60a9ba0c35debdff2dfa734caf1c271a183`
- Changed files: 4
  - `migrations/030_action_audit_log_hardening.sql`
  - `src/repositories/audit_repo.py`
  - `tests/unit/test_action_audit_schema_migration.py`
  - `tests/unit/test_write_audit_log.py`
- Focused tests: 27 passed
- Python compilation: passed
- Git diff check: passed
- GitHub pytest, Playwright, Vercel: passed

#### Follow-up

- [ ] Review migration 030 carefully before marking #708 ready.
- [ ] Confirm no current code path updates/deletes/truncates `action_audit_log`.
- [ ] Plan safe Neon/production migration rollout.
- [ ] Apply migration 030 before deploying the repository change.
- [ ] Keep #708 draft until migration rollout is explicitly approved.

### DEC-20260621-001 — Smallest-safe security hardening batch (#700–#705) merged to `main`

Status: accepted
Date: 2026-06-21
Owner: Roben / Claude
Related task: TASK-20260621-001

#### Context
A codebase sweep surfaced a class of high-impact correctness and security gaps in the
agent action / approval path:
- The permission approval engine (CAREER-OS-03) issued `apply` permissions that were not
  bound to a specific job, allowing a valid `permission_id` to be replayed against a
  *different* job.
- Permission denials were not audited.
- Multiple DB writers inserted/upserted without `conn.commit()` in the psycopg2
  non-autocommit environment, so the writes were silently rolled back. Only the in-memory
  dedup/cache survived, which is why the data loss went unnoticed.
- A connection-pool leak in identity merge left connections open on the exception path.
- `/api/v1/actions/run` passed the client-provided `job` dict straight to the runtime
  without stripping the `_approved` sentinel, letting a caller forge approval and bypass
  `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS`.

Per the user directive, the chosen approach was the smallest safe fix first — harden in
place through existing systems rather than building a parallel audit/approval framework.

#### Decision
Ship the hardening as small, focused PRs from current `main`, each independently testable:

- **#700** — Bind `job_key` to issued `apply` permissions; reject replay against a different
  job (mismatch does *not* consume the token, so the legitimate job can still approve). Audit
  permission denials through the existing `audit_repo.log_action()` with
  `result_status="denied"`, `failure_reason="permission_denied"`.
- **#701** — Add the missing `conn.commit()` in `audit_repo._db_write` so `action_audit_log`
  rows actually persist (regression-tested).
- **#702** — Fix `_save_attempt` in `src/auto_apply.py` and `src/naukrigulf_apply.py` to
  `commit()` after upsert and `close()` in `finally`.
- **#703** — Acquire the connection before the `try` and `close()` in `finally` in
  `agent/identity/resolver._attempt_identity_merge` (read-only, no commit) so the connection
  is released on every path.
- **#705** — Sanitize the `job` dict in `/actions/run` by stripping the `_approved` key; only
  `/actions/execute` (which validates a `permission_id`) may inject the sentinel.
- AI_WORKSPACE is standardized as the task-flow control system for all agents (reinforces
  DEC-20260617-001).

#### Consequences
- Positive: closes a permission-replay vector and an approval-bypass vector; restores audit
  and application-attempt persistence; eliminates two connection leaks. All changes are
  backward compatible (unbound permissions still accept any job; empty key normalizes to
  unbound). Render backend redeploy verified live.
- Trade-off: job-key binding is stricter — any caller that previously relied on reusing a
  permission across jobs will now be rejected (intended).

#### Verification (2026-06-21)
- Render: "Your service is live"; Uvicorn up on port 10000; `rico_db_init OK`;
  `settings_migration OK`; `startup_check: critical tables present`;
  `migration_ok label=028_performance_indexes`.
- `/health` → 200; `/version` → 200 during deploy polling.
- Warning (non-blocking): SkillNER not installed; did not block startup.

#### Follow-up
- [x] Confirmed deployed commit: `/version.commit` = `d93bb25` (current `main` HEAD), so the
      merged hardening batch (#700–#704) is live in production. Note: the `/version.deployed_at`
      field reads `2026-05-23` — it is a static build-time constant, not the actual deploy time,
      so trust `commit` over `deployed_at`.
- [x] Merged #705 (pytest + playwright green; squash commit `da452f6` on `main`). #704 closed
      as superseded — the consolidated AI_WORKSPACE decision record already landed via #705.
- [x] #705 Render deploy verified LIVE (2026-06-21): `/version.commit` = `da452f6`
      (matches `main` HEAD); `/health` → 200. Approval-bypass fix is in production.

### DEC-20260618-001 — Close PR #601 as stale/superseded; merge docs PRs #608 and #566

Status: accepted
Date: 2026-06-18
Owner: Roben / Claude
Related task: TASK-20260618-014

#### Context
Three open PRs created backlog noise. #601 was a broad multi-batch feature PR (~1.3k LOC)
touching `src/rico_chat_api.py` on a stale base, still in draft, with an unchecked test plan
and a body/title mismatch. #608 and #566 were small, clean, docs-only additions.

#### Decision
Close #601 without merging and without opening a replacement PR. Merge the two docs-only PRs
(#608 localization pattern, #566 Gmail read-only connector design) after confirming they are
clean, docs-only, and Vercel-green. Re-cut #601's deterministic fast paths later as small,
focused PRs from current `main` only if still needed.

#### Consequences
- Positive: open PR backlog is clean (0 open PRs); design docs for localization and the
  Gmail connector (#356) are now on `main`; future fast-path work starts from a current base.
- Trade-off: the fast-path content in #601 must be re-authored against current `main` if still
  wanted — its existing diff is not reused.

#### Follow-up
- [ ] Re-cut #601 fast paths as small PRs from `main` if/when prioritised.
- [ ] Consider disabling the third-party "Continuous AI" bot checks (they error on every PR).

### DEC-20260617-001 — Use `AI_WORKSPACE/` as the shared AI source of truth

Status: accepted
Date: 2026-06-17
Owner: Roben / ChatGPT
Related task: TASK-20260617-001

#### Context
Multiple AI tools can plan, implement, review, and verify Rico work. Without a shared repo-native context, each tool can drift based on stale chat history.

#### Decision
All multi-model work must use `AI_WORKSPACE/` as the shared source of truth for project context, active tasks, handoff briefs, decisions, and verification evidence.

#### Consequences
- Positive: less context drift, clearer PR boundaries, easier review.
- Trade-off: every contributor must update the workspace files when task state changes.

#### Follow-up
- [ ] Use the handoff template for the next implementation task.
- [ ] Keep decisions short and tied to tasks.
