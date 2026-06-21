#!/usr/bin/env python3
"""
scripts/apply_migration_drift.py

One-time, gated remediation for the #712 production migration drift
(005 pipeline objects + 011 recommendation indexes). Designed to run from a
GitHub Actions runner (which can reach Neon) using the DATABASE_URL secret,
because the drift-detector confirmed exactly these two migrations are missing.

Safety properties:
- Refuses to run unless APPLY_CONFIRM == "APPLY-712" (workflow gate).
- Only applies the specific, idempotent objects below — never arbitrary SQL.
- 011 indexes are created CONCURRENTLY (autocommit, no transaction) and the
  unique index is only attempted when a fresh duplicate check returns zero, so
  no dedupe DELETE is ever performed.
- 005 objects are additive (IF NOT EXISTS / OR REPLACE).
- Re-running is a no-op.

Usage (CI):
    APPLY_CONFIRM=APPLY-712 DATABASE_URL=... python scripts/apply_migration_drift.py
"""
from __future__ import annotations

import os
import sys

# 011 — index-only (no dedupe DELETE). CONCURRENTLY => must run outside a txn.
_O11_INDEXES = [
    """CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_rico_recommendations_user_job_unique
       ON rico_job_recommendations (user_id, job_key) WHERE job_key IS NOT NULL""",
    """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rico_recommendations_user_job_key
       ON rico_job_recommendations (user_id, job_key)""",
    """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rico_recommendations_user_status_updated
       ON rico_job_recommendations (user_id, status, updated_at DESC)""",
]

# 005 — focused pipeline objects (additive, idempotent). The settings table and
# update_updated_at_column() already exist in prod, so we touch neither here.
_O05_SQL = """
DO $$ BEGIN
  CREATE TYPE pipeline_status AS ENUM ('running','done','failed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS pipeline_runs (
  id SERIAL PRIMARY KEY,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  status pipeline_status NOT NULL DEFAULT 'running',
  jobs_found INTEGER NOT NULL DEFAULT 0,
  jobs_scored INTEGER NOT NULL DEFAULT 0,
  jobs_applied INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  UNIQUE (started_at, id)
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at  ON pipeline_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status      ON pipeline_runs (status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_finished_at ON pipeline_runs (finished_at);
CREATE OR REPLACE VIEW latest_pipeline_run AS
  SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1;
"""

_DUP_CHECK = """
SELECT COALESCE(SUM(c - 1), 0)
FROM (
  SELECT COUNT(*) AS c FROM rico_job_recommendations
  WHERE job_key IS NOT NULL
  GROUP BY user_id, job_key
  HAVING COUNT(*) > 1
) t
"""


def main() -> int:
    if os.environ.get("APPLY_CONFIRM") != "APPLY-712":
        print("ERROR: refusing to run — set APPLY_CONFIRM=APPLY-712 to apply.", file=sys.stderr)
        return 2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        return 2

    import psycopg2

    conn = psycopg2.connect(db_url)
    conn.autocommit = True  # required for CREATE INDEX CONCURRENTLY
    try:
        with conn.cursor() as cur:
            # --- 011: guard then index-only ---
            cur.execute(_DUP_CHECK)
            dup_rows = cur.fetchone()[0] or 0
            if dup_rows > 0:
                print(f"ABORT 011: {dup_rows} duplicate (user_id, job_key) row(s) exist; "
                      "the unique index needs a reviewed dedupe first (see #712). Not applying 011.",
                      file=sys.stderr)
                return 1
            print("011: 0 duplicate rows — applying indexes concurrently")
            for stmt in _O11_INDEXES:
                cur.execute(stmt)
                print(f"  applied: {stmt.split(chr(10))[0].strip()} …")

            # --- 005: additive pipeline objects ---
            print("005: applying pipeline objects (enum/table/indexes/view)")
            cur.execute(_O05_SQL)

        # --- verify with the drift detector's own checks ---
        from scripts.check_migration_drift import CHECKS, _present
        missing = []
        with conn.cursor() as cur:
            for migration, kind, ident in CHECKS:
                if not _present(cur, kind, ident):
                    missing.append((migration, kind, ident))
    finally:
        conn.close()

    print()
    if missing:
        nums = sorted({m for m, _, _ in missing})
        print(f"POST-APPLY: still missing across {', '.join(nums)} — investigate.", file=sys.stderr)
        return 1
    print("POST-APPLY: all migration signature objects present — drift cleared.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
