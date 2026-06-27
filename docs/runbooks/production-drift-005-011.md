# Production Migration Drift Runbook: 005 + 011

**Issue:** [#712](https://github.com/Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE/issues/712) / [#711](https://github.com/Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE/issues/711)
**Status:** Documentation / pre-execution planning — no SQL has been applied to production.
**Last updated:** 2026-06-26
**Production baseline at time of writing:** `504c75573fa760471666fed8447a26448ddffd20`

---

## Overview

Two numbered migrations were never applied to the production Neon database:

| Migration | File | Objects created | Runtime impact if missing |
|---|---|---|---|
| **005** | `migrations/005_mvp_settings_pipeline_runs.sql` | `pipeline_status` ENUM, `pipeline_runs` table + indexes + view, `update_updated_at_column()` function, `settings` trigger, `user_include_keywords` / `user_exclude_keywords` tables | `GET /api/v1/pipeline/status` and `POST /api/v1/pipeline/trigger` fail at the DB layer silently (pipeline_repo returns `None`); no data loss but pipeline monitoring is blind |
| **011** | `migrations/011_rico_recommendation_uniqueness.sql` | Uniqueness dedup DELETE, `idx_rico_recommendations_user_job_unique` UNIQUE INDEX, `idx_rico_recommendations_user_job_key` index, `idx_rico_recommendations_user_status_updated` index | The `ON CONFLICT (user_id, job_key)` UPSERT in `rico_db.py` requires this unique index to be idempotent; without it, UPSERT degrades to INSERT and the pipeline save/count correctness (#749) relies on the index being present |

> **Danger level — 011 > 005.** Migration 011 includes a destructive `DELETE` to deduplicate existing rows before adding the unique constraint. It must not be applied blind. See §4.

---

## 1. Current Known Drift

### 1.1 Migration 005 — `pipeline_runs`, ENUM, view, keyword tables

**Objects declared in `migrations/005_mvp_settings_pipeline_runs.sql`:**

```sql
-- ENUM type
CREATE TYPE pipeline_status AS ENUM ('running', 'done', 'failed');

-- Table
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id           SERIAL          PRIMARY KEY,
    started_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    finished_at  TIMESTAMPTZ,
    status       pipeline_status NOT NULL DEFAULT 'running',
    jobs_found   INTEGER         NOT NULL DEFAULT 0,
    jobs_scored  INTEGER         NOT NULL DEFAULT 0,
    jobs_applied INTEGER         NOT NULL DEFAULT 0,
    error        TEXT,
    UNIQUE (started_at, id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status     ON pipeline_runs (status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_finished_at ON pipeline_runs (finished_at);

-- View
CREATE VIEW latest_pipeline_run AS
SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1;

-- Trigger function + trigger on settings
CREATE OR REPLACE FUNCTION update_updated_at_column() ...
CREATE TRIGGER trg_settings_updated_at BEFORE UPDATE ON settings ...

-- Normalized keyword tables (optional in this schema; production uses TEXT[] columns instead)
CREATE TABLE IF NOT EXISTS user_include_keywords (...);
CREATE TABLE IF NOT EXISTS user_exclude_keywords (...);
```

**Collision risk:**
- The `settings` table is **already created** by `src/db.py:init_db()` with a different schema (`include_keywords TEXT[]`, `telegram_chat_id`, `score_threshold_apply`, etc.). The `CREATE TABLE IF NOT EXISTS settings` in 005 will be a no-op — safe.
- The `CREATE TRIGGER trg_settings_updated_at` in 005 is **not idempotent** (no `CREATE OR REPLACE`). If the trigger already exists on the `settings` table, it will raise `ERROR: trigger "trg_settings_updated_at" for table "settings" already exists`. The migration must be split — apply only the objects that are missing.
- `CREATE TYPE pipeline_status AS ENUM` — PostgreSQL 15 (Neon default) does **not** support `IF NOT EXISTS` for ENUM types natively in the SQL syntax used here. If the type already exists, this will raise `ERROR: type "pipeline_status" already exists`. Must check before applying.

### 1.2 Migration 011 — `rico_job_recommendations` unique index

**Objects declared in `migrations/011_rico_recommendation_uniqueness.sql`:**

```sql
-- Step 1: Destructive dedup (keeps highest id per user_id+job_key pair)
DELETE FROM rico_job_recommendations a
USING rico_job_recommendations b
WHERE a.user_id = b.user_id
  AND a.job_key = b.job_key
  AND a.id < b.id
  AND a.job_key IS NOT NULL;

-- Step 2: Unique index (partial — only where job_key IS NOT NULL)
CREATE UNIQUE INDEX IF NOT EXISTS idx_rico_recommendations_user_job_unique
ON rico_job_recommendations (user_id, job_key)
WHERE job_key IS NOT NULL;

-- Step 3: Lookup index
CREATE INDEX IF NOT EXISTS idx_rico_recommendations_user_job_key
ON rico_job_recommendations (user_id, job_key);

-- Step 4: Status + date filter index
CREATE INDEX IF NOT EXISTS idx_rico_recommendations_user_status_updated
ON rico_job_recommendations (user_id, status, updated_at DESC);
```

**Current state of `rico_job_recommendations`:**
`src/rico_db.py` creates the table with only one index:
```sql
CREATE INDEX IF NOT EXISTS idx_rico_recommendations_user_status
ON rico_job_recommendations(user_id, status);
```
The three indexes from 011 (`_user_job_unique`, `_user_job_key`, `_user_status_updated`) are **not** created by the runtime DDL and are assumed to be missing from production.

### 1.3 Summary

| Object | Expected location | Status |
|---|---|---|
| `pipeline_status` ENUM | `pipeline_runs` column type | Assumed **missing** — check first |
| `pipeline_runs` table | `src/repositories/pipeline_repo.py` queries it | Assumed **missing** — check first |
| `idx_pipeline_runs_started_at` | index on `pipeline_runs` | Assumed **missing** |
| `idx_pipeline_runs_status` | index on `pipeline_runs` | Assumed **missing** |
| `idx_pipeline_runs_finished_at` | index on `pipeline_runs` | Assumed **missing** |
| `latest_pipeline_run` VIEW | convenience alias | Assumed **missing** |
| `update_updated_at_column()` function | settings trigger | Unknown — check |
| `trg_settings_updated_at` trigger | `settings` table | Unknown — check |
| `user_include_keywords` table | keyword normalization | Assumed **missing** (legacy; low impact) |
| `user_exclude_keywords` table | keyword normalization | Assumed **missing** (legacy; low impact) |
| `idx_rico_recommendations_user_job_unique` | `rico_job_recommendations` | Assumed **missing** — HIGH IMPACT |
| `idx_rico_recommendations_user_job_key` | `rico_job_recommendations` | Assumed **missing** |
| `idx_rico_recommendations_user_status_updated` | `rico_job_recommendations` | Assumed **missing** |

---

## 2. Read-Only Prechecks

Run all queries below **read-only** against the production Neon database before touching anything. None of these modify data.

### 2.1 Check ENUM type existence

```sql
SELECT typname, typcategory
FROM pg_type
WHERE typname = 'pipeline_status';
-- Expect: 1 row if ENUM exists, 0 rows if missing
```

### 2.2 Check tables existence

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'pipeline_runs',
    'user_include_keywords',
    'user_exclude_keywords',
    'settings',
    'rico_job_recommendations'
  )
ORDER BY table_name;
-- Expected present: settings, rico_job_recommendations
-- Expected missing: pipeline_runs (and possibly the keyword tables)
```

### 2.3 Check view existence

```sql
SELECT table_name
FROM information_schema.views
WHERE table_schema = 'public'
  AND table_name = 'latest_pipeline_run';
-- Expect: 0 rows if missing
```

### 2.4 Check trigger existence

```sql
SELECT trigger_name, event_object_table, action_timing, event_manipulation
FROM information_schema.triggers
WHERE trigger_name = 'trg_settings_updated_at'
  AND event_object_schema = 'public';
-- Expect: 0 rows if missing (safe to create)
--         1+ rows if already present (skip the CREATE TRIGGER statement)
```

### 2.5 Check function existence

```sql
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name = 'update_updated_at_column';
-- Expect: 0 rows if missing
```

### 2.6 Check all indexes on `rico_job_recommendations`

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'rico_job_recommendations'
ORDER BY indexname;
-- Must see idx_rico_recommendations_user_job_unique before applying any UPSERT logic
-- idx_rico_recommendations_user_status is created by runtime DDL — likely present
-- _user_job_unique, _user_job_key, _user_status_updated from 011 — likely absent
```

### 2.7 Check indexes on `pipeline_runs` (if table exists)

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'pipeline_runs'
ORDER BY indexname;
-- Skip if pipeline_runs does not exist per §2.2
```

### 2.8 Duplicate scan on `rico_job_recommendations` (MUST run before 011)

```sql
-- Count duplicates that the DELETE in 011 would remove
SELECT user_id, job_key, COUNT(*) AS dup_count
FROM rico_job_recommendations
WHERE job_key IS NOT NULL
GROUP BY user_id, job_key
HAVING COUNT(*) > 1
ORDER BY dup_count DESC
LIMIT 50;
-- If this returns 0 rows: safe to proceed to unique index creation
-- If this returns rows: review duplicates with the owner before DELETE
```

### 2.9 Inspect duplicate rows (run only if §2.8 returns duplicates)

```sql
SELECT id, user_id, job_key, status, created_at, updated_at
FROM rico_job_recommendations
WHERE job_key IS NOT NULL
  AND (user_id, job_key) IN (
    SELECT user_id, job_key
    FROM rico_job_recommendations
    WHERE job_key IS NOT NULL
    GROUP BY user_id, job_key
    HAVING COUNT(*) > 1
  )
ORDER BY user_id, job_key, id DESC
LIMIT 100;
-- Review which rows would be deleted (the older ones, lower id values)
-- The DELETE in 011 keeps the highest id per pair
```

### 2.10 Confirm production database connection

```sql
SELECT current_database(), current_user, version();
-- Must confirm this is the PRODUCTION Neon database, not a preview branch
-- Cross-check database name against the DATABASE_URL on Render
```

---

## 3. Safe Execution Plan

**Guiding principles:**
- Apply 011 (indexes) and 005 (`pipeline_runs`) as two separate, independent steps.
- Never replay a migration file verbatim without first running the prechecks in §2.
- Each statement is labelled with the precheck that must pass before running it.
- Stop on any unexpected error and escalate before continuing.

### 3.1 Step A — Apply 011 indexes to `rico_job_recommendations`

**Priority: HIGH** (required for #749 save/count idempotency)

**Prerequisite prechecks:** §2.2 (table exists), §2.6 (index state), §2.8 (zero duplicates), §2.10 (correct DB)

**If §2.8 returns 0 duplicate rows**, proceed:

```sql
-- A1: Idempotent dedup guard (safe even if no duplicates exist)
-- Run in a transaction so it can be rolled back if unexpected rows are affected
BEGIN;

DELETE FROM rico_job_recommendations a
USING rico_job_recommendations b
WHERE a.user_id = b.user_id
  AND a.job_key = b.job_key
  AND a.id < b.id
  AND a.job_key IS NOT NULL;

-- Review the DELETE count before committing:
-- If 0 rows deleted: COMMIT (expected)
-- If N rows deleted: review with owner before COMMIT
COMMIT;

-- A2: Unique index (partial — NULL job_key rows are excluded)
CREATE UNIQUE INDEX IF NOT EXISTS idx_rico_recommendations_user_job_unique
ON rico_job_recommendations (user_id, job_key)
WHERE job_key IS NOT NULL;

-- A3: Lookup index
CREATE INDEX IF NOT EXISTS idx_rico_recommendations_user_job_key
ON rico_job_recommendations (user_id, job_key);

-- A4: Status + date filter index
CREATE INDEX IF NOT EXISTS idx_rico_recommendations_user_status_updated
ON rico_job_recommendations (user_id, status, updated_at DESC);
```

**If §2.8 returns duplicates:** STOP. Do not proceed. See §4.3 (duplicate conflict recovery).

### 3.2 Step B — Apply 005 `pipeline_runs` objects

**Priority: MEDIUM** (pipeline monitoring; no data loss if missing, just blind)

**Prerequisite prechecks:** §2.1 (ENUM state), §2.2 (`pipeline_runs` absent), §2.4 (trigger state), §2.5 (function state), §2.10 (correct DB)

**B1 — ENUM type** (only if §2.1 returned 0 rows):

```sql
CREATE TYPE pipeline_status AS ENUM ('running', 'done', 'failed');
```

Skip if ENUM already exists. Do not run if §2.1 returned 1 row.

**B2 — `pipeline_runs` table** (only if §2.2 showed it missing):

```sql
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id           SERIAL          PRIMARY KEY,
    started_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    finished_at  TIMESTAMPTZ,
    status       pipeline_status NOT NULL DEFAULT 'running',
    jobs_found   INTEGER         NOT NULL DEFAULT 0,
    jobs_scored  INTEGER         NOT NULL DEFAULT 0,
    jobs_applied INTEGER         NOT NULL DEFAULT 0,
    error        TEXT,
    UNIQUE (started_at, id)
);
```

**B3 — Indexes on `pipeline_runs`** (only after B2 succeeds):

```sql
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at  ON pipeline_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status       ON pipeline_runs (status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_finished_at  ON pipeline_runs (finished_at);
```

**B4 — View** (only if §2.3 returned 0 rows):

```sql
CREATE VIEW latest_pipeline_run AS
SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1;
```

**B5 — Trigger function** (only if §2.5 returned 0 rows):

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

`CREATE OR REPLACE FUNCTION` is idempotent — safe to run even if the function already exists.

**B6 — Trigger on `settings`** (only if §2.4 returned 0 rows):

```sql
CREATE TRIGGER trg_settings_updated_at
    BEFORE UPDATE ON settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

Skip entirely if §2.4 returned 1 or more rows.

**B7 — Normalized keyword tables** (low priority — only if confirmed needed):

```sql
CREATE TABLE IF NOT EXISTS user_include_keywords (
    user_id    TEXT        NOT NULL,
    keyword    TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, keyword)
);
CREATE INDEX IF NOT EXISTS idx_include_keywords_user ON user_include_keywords (user_id);

CREATE TABLE IF NOT EXISTS user_exclude_keywords (
    user_id    TEXT        NOT NULL,
    keyword    TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, keyword)
);
CREATE INDEX IF NOT EXISTS idx_exclude_keywords_user ON user_exclude_keywords (user_id);
```

These tables are from the legacy single-user architecture. Production uses `TEXT[]` arrays in the `settings` table (via `src/db.py:init_db()`). These tables are safe to create (no conflicts) but may not be actively used. Defer unless a specific feature needs them.

---

## 4. Rollback / Recovery Notes

### 4.1 What can be safely dropped

These objects have no row data and can be re-created freely:

| Object | Drop statement | Notes |
|---|---|---|
| `idx_pipeline_runs_started_at` | `DROP INDEX IF EXISTS idx_pipeline_runs_started_at;` | Index only — no data |
| `idx_pipeline_runs_status` | `DROP INDEX IF EXISTS idx_pipeline_runs_status;` | Index only |
| `idx_pipeline_runs_finished_at` | `DROP INDEX IF EXISTS idx_pipeline_runs_finished_at;` | Index only |
| `idx_rico_recommendations_user_job_unique` | `DROP INDEX IF EXISTS idx_rico_recommendations_user_job_unique;` | Index only — rows are NOT dropped |
| `idx_rico_recommendations_user_job_key` | `DROP INDEX IF EXISTS idx_rico_recommendations_user_job_key;` | Index only |
| `idx_rico_recommendations_user_status_updated` | `DROP INDEX IF EXISTS idx_rico_recommendations_user_status_updated;` | Index only |
| `latest_pipeline_run` VIEW | `DROP VIEW IF EXISTS latest_pipeline_run;` | View only — no data |
| `trg_settings_updated_at` | `DROP TRIGGER IF EXISTS trg_settings_updated_at ON settings;` | Trigger only — no data |
| `update_updated_at_column()` | `DROP FUNCTION IF EXISTS update_updated_at_column();` | Only if no other triggers depend on it |
| `user_include_keywords` | `DROP TABLE IF EXISTS user_include_keywords;` | Only if empty; confirm first |
| `user_exclude_keywords` | `DROP TABLE IF EXISTS user_exclude_keywords;` | Only if empty; confirm first |

### 4.2 What must NOT be dropped without explicit owner approval

| Object | Reason |
|---|---|
| `pipeline_runs` table | May contain audit history of daily pipeline runs after creation |
| `rico_job_recommendations` table | Core user-facing data; `pipeline_repo.py` and `rico_db.py` depend on it |
| `settings` table | Active — `src/db.py` and `src/api/routers/settings.py` read/write it |
| `pipeline_status` ENUM | Dropping an ENUM requires `CASCADE` and would drop `pipeline_runs` column |

### 4.3 Duplicate conflict during 011

If the `DELETE` in Step A returns an unexpectedly large number of rows, or if `CREATE UNIQUE INDEX` fails with `ERROR: could not create unique index` (meaning duplicates remain after the DELETE):

1. **ROLLBACK immediately** if inside a transaction.
2. Run §2.9 to inspect surviving duplicates.
3. Present the duplicate list to the owner for manual review.
4. Do not retry the unique index creation until duplicates are resolved.
5. The application continues to function without the index — it will INSERT instead of UPSERT, creating new rows rather than updating existing ones. This is degraded behavior but not data corruption.

### 4.4 ENUM creation failure

If `CREATE TYPE pipeline_status` fails with `type "pipeline_status" already exists`:

- The ENUM is already present — skip that statement.
- Check if `pipeline_runs` table exists (§2.2). It may have been created by a prior partial migration.
- Do not attempt `DROP TYPE pipeline_status CASCADE` — it would cascade to `pipeline_runs.status`.

### 4.5 Trigger creation failure

If `CREATE TRIGGER trg_settings_updated_at` fails with `trigger already exists`:

- Run §2.4 to confirm the trigger is present.
- No action needed — the trigger is already protecting `updated_at`.
- Do not attempt to replace it without owner approval.

---

## 5. Verification Queries

Run after each step to confirm the objects were created correctly.

### 5.1 After Step A (011 indexes)

```sql
-- Confirm all three 011 indexes exist
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'rico_job_recommendations'
  AND indexname IN (
    'idx_rico_recommendations_user_job_unique',
    'idx_rico_recommendations_user_job_key',
    'idx_rico_recommendations_user_status_updated'
  )
ORDER BY indexname;
-- Expect: 3 rows

-- Confirm unique index is partial (WHERE job_key IS NOT NULL)
SELECT indexname, indexdef
FROM pg_indexes
WHERE indexname = 'idx_rico_recommendations_user_job_unique';
-- indexdef must contain: WHERE (job_key IS NOT NULL)

-- Confirm no duplicates remain
SELECT COUNT(*) AS remaining_duplicates
FROM (
  SELECT user_id, job_key
  FROM rico_job_recommendations
  WHERE job_key IS NOT NULL
  GROUP BY user_id, job_key
  HAVING COUNT(*) > 1
) dupes;
-- Expect: 0
```

### 5.2 After Step B (005 pipeline_runs)

```sql
-- Confirm ENUM
SELECT typname FROM pg_type WHERE typname = 'pipeline_status';
-- Expect: 1 row

-- Confirm table
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name = 'pipeline_runs';
-- Expect: 1 row

-- Confirm indexes
SELECT indexname FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'pipeline_runs'
ORDER BY indexname;
-- Expect: idx_pipeline_runs_finished_at, idx_pipeline_runs_started_at, idx_pipeline_runs_status

-- Confirm view
SELECT table_name FROM information_schema.views
WHERE table_schema = 'public' AND table_name = 'latest_pipeline_run';
-- Expect: 1 row

-- Confirm trigger
SELECT trigger_name FROM information_schema.triggers
WHERE trigger_name = 'trg_settings_updated_at'
  AND event_object_schema = 'public';
-- Expect: 1 row (or already existed from precheck)
```

### 5.3 App health after deploy

```bash
# Backend liveness
curl -s https://rico-job-automation-api.onrender.com/health | python3 -m json.tool

# Confirm version matches expected commit
curl -s https://rico-job-automation-api.onrender.com/version | python3 -m json.tool

# Pipeline status (requires auth — run from a session with valid JWT cookie)
# GET /api/v1/pipeline/status
# Expect: HTTP 200, not an unhandled exception about "relation pipeline_runs does not exist"
```

### 5.4 Functional smoke — save idempotency (requires auth)

After Step A, verify that saving the same job twice does not double-count in the pipeline:

1. Search for a role via the `/command` UI.
2. Say "save the second job to my pipeline" — note the pipeline count.
3. Repeat the same save command.
4. Confirm the pipeline count did not increment a second time.

This is the owner-side authenticated smoke test that cannot be run from the sandbox.

---

## 6. Required Approvals

The following gates must be confirmed **before any write operation** is issued against production:

| Gate | Who | What to confirm |
|---|---|---|
| **G1 — Correct database** | Owner | Run §2.10 and confirm `current_database()` matches the Neon database name shown in the Render `DATABASE_URL` env var |
| **G2 — Backup / snapshot** | Owner | Confirm a Neon branch or manual snapshot of the production database exists and was taken within 24 hours of applying the migration |
| **G3 — Duplicate review** | Owner | Run §2.8 and confirm the result is 0 rows, OR review the duplicate list from §2.9 and explicitly approve the DELETE |
| **G4 — Step A approval** | Owner | Explicitly approve Step A (011 indexes) before any SQL is issued |
| **G5 — Step B approval** | Owner | Explicitly approve Step B (005 pipeline_runs) before any SQL is issued; this is independent of G4 |
| **G6 — Render deploy** | Owner | After applying the migration, confirm a Render deploy is triggered and `/health` returns `status: ok` before declaring success |

No production SQL should be issued by any automation (GitHub Actions, Render cron, Claude session) without G1–G3 at minimum. G4 and G5 gate their respective steps independently.

---

## 7. Production Execution Checklist

Copy this checklist into the approval comment before starting:

```
[ ] G1: Confirmed correct Neon production database (current_database() matches Render DATABASE_URL)
[ ] G2: Neon snapshot / branch taken within 24h
[ ] G3: §2.8 duplicate scan returned 0 rows (or duplicates reviewed and approved)

-- Step A (011 indexes) --
[ ] G4: Owner approval for Step A
[ ] A1: Dedup DELETE run in transaction, row count reviewed, COMMITTED
[ ] A2: idx_rico_recommendations_user_job_unique created
[ ] A3: idx_rico_recommendations_user_job_key created
[ ] A4: idx_rico_recommendations_user_status_updated created
[ ] Verify §5.1: all 3 indexes present, 0 duplicates remaining

-- Step B (005 pipeline_runs) --
[ ] G5: Owner approval for Step B
[ ] B1: pipeline_status ENUM created (or confirmed already present, skipped)
[ ] B2: pipeline_runs table created
[ ] B3: pipeline_runs indexes created
[ ] B4: latest_pipeline_run view created
[ ] B5: update_updated_at_column() function created (CREATE OR REPLACE — idempotent)
[ ] B6: trg_settings_updated_at trigger created (or confirmed already present, skipped)
[ ] B7: Keyword tables — deferred or confirmed not needed
[ ] Verify §5.2: all 005 objects present

-- Post-apply --
[ ] G6: Render deploy triggered and /health returns status: ok
[ ] §5.3: /version matches expected commit
[ ] §5.4: Owner confirms save-idempotency smoke (save same job twice → count unchanged)
```

---

## 8. What This Runbook Does NOT Cover

- `#746` — separate issue; do not start until explicitly approved.
- Any migration between 006–010 or 012–032 — these are assumed applied; if drift is suspected, a separate audit is required.
- Structural changes to `rico_job_recommendations` or `settings` schema — out of scope here.
- Branch deletion — not part of this runbook.
