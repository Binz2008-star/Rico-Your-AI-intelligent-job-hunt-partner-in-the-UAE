# Runbook — Migration 047 (`analytics_events`)

Canonical apply / verify / rollback procedure. This exact procedure was
executed on the Neon **preview** branch on 2026-07-19. The **production**
application has SINCE been performed and verified — see the addendum
"Production application — verified (2026-07-19)" at the end of this
runbook. (The original "NOT been performed" statement here was accurate
when written at 06:52 UTC and was superseded the same day.)

## Identity of the migration

- File: `migrations/047_analytics_events.sql` at `main` commit
  `c09a929a5ea4baa01b5729387d22b8697e2d4f3b` (squash of PR #1176, merged
  head `25975b63a5e4c16cf24a6dbaf6aa1becb01687b3`).
- sha256 (identical at merged head and on main — byte-for-byte):
  `a04f110605785f18236e4feafc755781d7594fdc73a5aa2094356a280cacd97d`
- Exactly ONE migration numbered 047 exists on `main`. PR #1177 (Draft)
  carries a CONFLICTING `047_reasoning_traces.sql` — owner ruling: #1177
  stays Draft; any future reopen restarts from `main` ≥ `c09a929a` with a
  NEW migration number and a new task.

## Environment facts

- Neon project: `robenjob` (`old-frog-88141983`).
- Production branch: `production` (`br-restless-cherry-amq6wj7o`), db `neondb`.
- Preview branch used for validation: `br-tiny-truth-am61levn`
  (`preview/pr-1176-claude/analytics-events-foundation`) — GitHub-created
  TEMPORARY branch: `default=false`, `protected=false`, parent =
  production, TTL 14 days, expires `2026-08-01T23:47:02Z`. It is NOT
  production.

## Apply (statements verbatim from the migration file — run in order)

```sql
CREATE TABLE IF NOT EXISTS analytics_events ( ... );          -- full body in migrations/047_analytics_events.sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_analytics_events_dedupe
    ON analytics_events (dedupe_key);
CREATE INDEX IF NOT EXISTS idx_analytics_events_name_occurred
    ON analytics_events (event_name, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_occurred
    ON analytics_events (occurred_at);
```

All statements are `IF NOT EXISTS` — idempotent; re-running is safe.

## Verify (read-only, all must pass)

```sql
-- 10 columns, 4 indexes (PK + 3 explicit), 4 CHECK constraints
SELECT count(*) FROM information_schema.columns WHERE table_name = 'analytics_events';   -- = 10
SELECT count(*) FROM pg_indexes WHERE tablename = 'analytics_events';                    -- = 4
SELECT count(*) FROM pg_constraint
 WHERE conrelid = 'analytics_events'::regclass AND contype = 'c';                        -- = 4
SELECT count(*) FROM analytics_events;                                                   -- = 0 on production
```

Functional CHECK probes (each INSERT must FAIL with the named constraint):

```sql
-- analytics_events_event_name_check
INSERT INTO analytics_events (event_name, actor_hash, audience, dedupe_key, properties)
VALUES ('not_in_allowlist', 'x', 'user', 'p1', '{}');
-- analytics_events_audience_check
INSERT INTO analytics_events (event_name, actor_hash, audience, dedupe_key, properties)
VALUES ('session_start', 'x', 'admin', 'p2', '{}');
-- analytics_events_properties_check
INSERT INTO analytics_events (event_name, actor_hash, audience, dedupe_key, properties)
VALUES ('session_start', 'x', 'user', 'p3', '[1,2,3]');
-- analytics_events_schema_version_check
INSERT INTO analytics_events (event_name, actor_hash, audience, dedupe_key, properties, schema_version)
VALUES ('session_start', 'x', 'user', 'p4', '{}', 0);
```

Preview run additionally proved (with real `record_event`-built rows and a
throwaway key, never a production secret): duplicate dedupe_key collapses
via `ON CONFLICT DO NOTHING` (4 inserts → 3 rows); distinct guest
identities → distinct actors/rows; zero raw-identity leaks.

## Safety of production application (why it triggers no writes)

- ZERO call sites of `analytics_events_repo.record_event` exist outside
  the module and its tests — no emitters are wired.
- `RICO_ANALYTICS_HMAC_KEY` is NOT set on Render — even a future caller
  is fail-closed (writes skipped) until the owner sets the key.
- Nothing reads the table. The applied table sits inert.

> Superseded 2026-07-19 (same day, post-#1179/#1180): the three bullets
> above describe the state AT APPLY TIME and remain accurate for that
> moment. Since then: emitters v1 call `record_event` from
> `src/agent/runtime.py` and `src/rico_chat_api.py` via
> `src/services/analytics_emitters.py` (#1179), and TASK-20260719-003
> records the owner-side "Analytics HMAC gate: PASS". The purge endpoint
> exists but is inert (#1180: flag OFF, schedule commented out).

## Rollback

- Ownership: the OWNER holds the apply/rollback decision gate. The agent
  executes only on explicit owner instruction; Windsurf is not involved
  in DB operations.
- Procedure (single object, nothing references it):

```sql
DROP TABLE IF EXISTS analytics_events;
```

- Code needs no rollback to tolerate this: the repository latches itself
  off on `42P01` (table absent) per process.
- Drift note: while 047 is unapplied on production (or after a rollback),
  the scheduled migration-drift check alerts — that alert is the
  intended reminder, not an incident.

## Addendum — retention purge scheduling (DEC-20260719-001)

The "scheduled job wired in a LATER change" promised by the migration header
now exists. Architecture (no new infrastructure — the proven cron-secret
pattern only):

```text
emitters (src/services/analytics_emitters.py)
  ↓
analytics_events (migration 047)
  ↓
POST /api/v1/pipeline/analytics-purge
  (X-Cron-Secret + RICO_ENABLE_ANALYTICS_PURGE, default off)
  ↓
.github/workflows/analytics-purge.yml (scheduled GitHub Actions caller)
```

Governance invariants:

- The retention window is the fixed `RETENTION_DAYS` (180) constant in
  `src/repositories/analytics_events_repo.py` — NEVER an API input, never an
  env var. Changing it is a reviewed code change plus a DECISIONS.md update.
- The dry-run count (`count_expired`) and the DELETE (`purge_expired`) are
  built from the same `_EXPIRED_PREDICATE_SQL` string, so the reported count
  is exactly what a real run would remove (pinned by unit test).
- Deletion uses `idx_analytics_events_occurred`; no batching in v1 — at
  daily cadence each run removes roughly one day of events. Revisit batching
  only if a large backlog scenario ever materialises.

Rollout gates (owner-sequenced; either gate alone keeps the purge off):

1. `RICO_ENABLE_ANALYTICS_PURGE` on Render — default off; disabled runs
   return `{"status": "disabled"}` (HTTP 200) and never touch the repository.
2. The workflow schedule ships COMMENTED OUT (job-alert-emails.yml pattern).
   Uncomment only after, in order: 047 applied to production → emitters
   live → baseline collection established → owner approval.

Verification before enabling: with the flag on, dispatch the workflow with
`dry_run=true` and confirm `would_remove` matches expectations. A
table-absent database yields 0 (fail-soft, never an error).

Emergency disable (fastest first): disable the workflow in the GitHub UI →
set the flag off on Render (no deploy) → revert the PR. Do NOT clear
`RICO_CRON_SECRET` — that would 503 every pipeline sweep, not just this one.

Deleted rows are unrecoverable by design; disaster recovery is Neon PITR /
branch restore only.

## Addendum — production application verified (2026-07-19)

Verified by the owner-directed post-merge audit
(`AI_WORKSPACE/HANDOFFS/2026-07-19-analytics-047-postmerge-audit.md`),
read-only queries against Neon branch **`production`**
(`br-restless-cherry-amq6wj7o` — the project default), db `neondb`:

- `to_regclass('public.analytics_events')` → present.
- Indexes: `analytics_events_pkey`, `uq_analytics_events_dedupe`,
  `idx_analytics_events_name_occurred`, `idx_analytics_events_occurred`
  (4/4 expected).
- All 4 applied CHECK constraints match the migration file exactly
  (event-name allowlist 8/8, audience, properties-object, schema_version).
- `SELECT count(*) FROM analytics_events` → **0** at ≈09:55 UTC and again
  **0** at 10:10:13 UTC (post-#1179 merge; deployed backend SHA was not
  verifiable from the audit environment, so a 0 count says nothing about
  emitter/key status).

The apply actor and exact timestamp are not recorded in the workspace; the
apply occurred between the 06:52 UTC "production pending" record (#1178)
and the ≈09:55 UTC audit query. Owner may backfill the apply event.
Audit verdict for the merged foundation: **B — safe with follow-up**; the
four required future gates live in the handoff and in TASK-20260719-002.
