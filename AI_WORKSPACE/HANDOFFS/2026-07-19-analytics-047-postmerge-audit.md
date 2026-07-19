# Handoff — Post-merge audit of PR #1176 (`analytics_events`, migration 047)

Date: 2026-07-19 · Author: Claude (read-only audit session, owner-directed)
Audit target: squash merge `c09a929a5ea4baa01b5729387d22b8697e2d4f3b`
(PR #1176, merged 2026-07-19 06:44:41 UTC onto `d5f96f1e`).
Verdict: **B — safe with follow-up** (no corrective PR, no rollback).

Constraints honored: no runtime code touched, migration 047 not edited, no
SQL applied, no Render env changed, no emitters wired, no purge scheduled,
PR #1177 untouched. All database access was read-only metadata/COUNT.

## 1. Verified production state

- Neon project `robenjob` (`old-frog-88141983`), branch **`production`**
  (`br-restless-cherry-amq6wj7o` — the project default branch).
- `analytics_events` **present**; PK + all 3 migration indexes present
  (`uq_analytics_events_dedupe`, `idx_analytics_events_name_occurred`,
  `idx_analytics_events_occurred`).
- All 4 applied CHECK constraints match `migrations/047_analytics_events.sql`
  exactly (event allowlist 8/8, audience, properties-object, schema_version).
- Row count **0** at ≈09:55 UTC (default-branch query) and again **0** at
  10:10:13 UTC (explicit `branchId` + `neondb` re-check).
- The apply actor/timestamp is not recorded in the workspace; the apply
  happened between #1178's "production pending" record (06:52 UTC) and the
  audit query (≈09:55 UTC). Owner may backfill the apply event if desired.
- `RICO_ANALYTICS_HMAC_KEY` on Render: **unverifiable from the audit
  environment** (key absent from the session env; Render domain blocked by
  the environment network policy; nothing printed). TASK-20260719-003
  separately records the owner-side gate "Analytics HMAC gate: PASS" —
  the owner record is authoritative.
- Emitters: **zero callers** of `record_event`/`purge_expired` existed at
  the audit target `c09a929a` (verified via `git grep`). Emitters v1
  (#1179) and inert purge scheduling (#1180) merged AFTER the audit target.

## 2. Test evidence at the merge commit

- `tests/unit/test_analytics_events_repo.py` at `c09a929a`: **31/31 passed**
  (28 test functions; parametrization brings collected cases to 31),
  executed in a disposable detached worktree. The "22 tests" figure in the
  frozen PR body is superseded (consistent with #1178's record correction).

## 3. Findings (none at P0/P1)

### P2-1 — `record_event` "never raises" contract breached for malformed types (CONFIRMED empirically)
Row construction runs outside the `try` (`_clean_properties` at
`src/repositories/analytics_events_repo.py:246`, `_dedupe_key` at `:255`;
`try` begins `:260`). Reproduced at the merge commit:
`properties=['x']` → AttributeError; `client_event_id=123` → AttributeError;
`occurred_at="2026-07-19"` → TypeError. Not reachable in production at the
audit target (zero callers). **Post-audit status:** #1179's emitter layer
(`src/services/analytics_emitters.py`) validates all inputs and wraps every
call fail-soft, mitigating product-flow risk for v1; the repo-level
contract hole itself remains unfixed (#1179/#1180 did not touch the row
construction path).

### P2-2 — Governance exception: merged with zero completed reviews
The PR's GitHub review list is empty. Timeline: marked Ready ≤06:41 UTC;
Codex review attempt failed on usage quota 06:41:04 UTC; merged
06:44:41 UTC. The owner's stated pre-merge gate (full diff / CI /
migration / rollback / privacy / TASKS / overlap review) was not completed
by any reviewer before merge. **Compensating control: this post-merge
audit (owner-directed), recorded here as the governance exception record.**

### P3 (summary; full detail in the audit report delivered in chat)
- P3-1 Allowlist-growth trap: the lockstep test
  (`tests/unit/test_analytics_events_repo.py:361-375` at the merge commit)
  pins code to 047's **file**; with 047 now applied, event #9 requires a
  NEW ALTER migration + test redesign — never an in-place 047 edit. The
  drift checker verifies table/index existence only, not CHECK contents;
  an applied-vs-code CHECK divergence drops events silently (23514
  swallowed as transient).
- P3-2 Unknown event names logged verbatim (`:211-213`) and the warn-set
  unbounded (`:127`) — sanitize/cap in the emitter era.
- P3-3 Auto-dedupe minute bucket undercounts legitimate identical repeats
  (`:175-177`) — accepted bias; emitters whose events can repeat
  sub-minute should pass `client_event_id`.
- P3-4 `purge_expired(True)` accepted as 1-day retention (bool passes
  `int()` bounds; still true after #1180's `_validated_retention_days`).
- P3-5 No real-Postgres integration test for 047 (unit suite mocks the
  cursor); mitigated by the live applied-DDL verification above.
- P3-6 Migration nits (harmless): `actor_hash CHAR(64) DEFAULT ''`
  blank-pads if defaulted; `properties IS NOT NULL` redundant in CHECK.
  HMAC key rotation unlinks all prior actor hashes (privacy-positive;
  measurement discontinuity — runbook-worthy).

## 4. Required future gates (owner-directed)

1. **Fix the malformed-input exceptions** in `record_event` before or
   within the next PR that adds ANY caller outside
   `src/services/analytics_emitters.py`. Until fixed, all emission goes
   through the emitter layer only.
2. **Add adversarial tests**: non-dict `properties`, non-str
   `client_event_id`, non-datetime `occurred_at`, boolean
   `retention_days`.
3. **Define the additive allowlist-growth migration policy before
   event #9** (new ALTER migration + lockstep-test redesign; 047 is
   immutable once applied).
4. **Record owner confirmation of `RICO_ANALYTICS_HMAC_KEY` on Render**
   in the workspace before relying on measurement (emitters no-op
   fail-closed without it; production row count was still 0 at
   10:10 UTC).

## 5. Records reconciled by this handoff's PR

- `AI_WORKSPACE/TASKS.md` TASK-20260719-002: status → done; audit
  sub-block added (this document is the detail).
- `AI_WORKSPACE/RUNBOOKS/047-analytics-events-migration.md`: header and
  safety-section claims ("production NOT performed", "key NOT set",
  "no emitters wired") superseded with dated corrections; production
  verification addendum added.
- Observed but NOT changed (outside this PR's single objective):
  TASK-20260719-003 and -004 still read `Status: review` although #1179
  and #1180 are merged; `AI_WORKSPACE/CURRENT_STATE.md:20` still lists
  behavioral analytics as "deferred". Owner may fold these into the next
  reconciliation.
