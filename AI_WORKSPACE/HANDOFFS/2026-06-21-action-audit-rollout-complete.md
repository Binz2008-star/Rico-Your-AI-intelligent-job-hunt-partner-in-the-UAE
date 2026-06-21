# Handoff — Action Audit Hardening Rollout COMPLETE (+ migration drift)

Date: 2026-06-21
Owner: Roben / Claude
Status: rollout complete + verified; follow-up drift logged

Supersedes the candidate handoff `2026-06-21-action-audit-schema-hardening.md` (which described
#708 while it was still a draft). This records the completed production rollout and the
migration-drift work that came out of it.

## #708 — action_audit_log hardening (migration 030): DONE

- PR #708 squash-merged to `main` at `9078d77`.
- Migration `030_action_audit_log_hardening.sql` applied to **production Neon** and verified.
- Backend deployed and live on `9078d77` (Render auto-deploy via `deploy-render.yml`; green run
  polled `/version` to the merged commit + health 200).

### Production verification evidence
- `/version` → `9078d77`; `/health` → ok.
- `pg_stat_statements`: `INSERT INTO action_audit_log (… event_type, data …)` executes with
  `rows > 0` → migrated append-only schema accepts writes.
- `pg_stat_statements`: new `get_recent()` SELECT (returns `event_type`/`data`) executes against
  prod.
- Trigger `trg_action_audit_log_append_only`: `tgenabled='O'`, `tgtype=58`
  (= BEFORE, STATEMENT-level, UPDATE+DELETE+TRUNCATE; INSERT allowed) — exactly as designed.
- No `audit_log_write_failed`; no append-only / SQLSTATE `55000` errors in logs.

### Behavior verified earlier on real PostgreSQL (throwaway PG 16)
- 006 → 030 applied; columns nullable; index + trigger present; INSERT allowed;
  UPDATE/DELETE/TRUNCATE rejected; migration idempotent on re-run; rollback steps inspected only.

## #710 — user_job_context.alt_url (migration 021): DONE / closed

- Production was missing `migrations/021_user_job_context_alt_url.sql` → runtime
  `UndefinedColumn: column "alt_url"` at `user_job_context_repo.py:73` (errors were swallowed,
  so chat was unaffected but job-context upserts silently failed).
- Applied bare idempotent DDL: `ALTER TABLE user_job_context ADD COLUMN IF NOT EXISTS alt_url TEXT NOT NULL DEFAULT '';`
- Verified `alt_url` present (`text`, `NOT NULL`, default `''`) via `information_schema` + real
  row reads. Issue **#710 closed (completed)**.

## #711 — additional migration drift: OPEN, NOT applied

A full `005`–`030` presence audit against prod Neon found two more missing migrations:

- **005** — table `pipeline_runs` missing (`settings` exists via the app's runtime
  `settings_migration`). Low/monitoring impact. Apply only the missing pieces — do NOT re-run the
  whole `005` file (its `CREATE TRIGGER` / `CREATE VIEW` are unguarded against existing `settings`).
- **011** — `idx_rico_recommendations_user_job_unique` missing. Higher care: 011 includes a dedup
  `DELETE`, and a missing unique index can break `ON CONFLICT (user_id, job_key)` upserts (`42P10`).
  Verify-first (check for an equivalent unique index under another name; count dup rows) before applying.

Tracked in issue **#711**. Verify-first SQL + targeted remediation are in the issue body.

## Systemic root cause (recommended follow-up)

Numbered SQL migrations (`005`–`030`) are **not auto-applied on deploy** — they are run manually
via `psql`. This is why 021 drifted and why 030 had to be hand-applied. Recommend adding a
migration runner / CI gate so prod schema can't silently fall behind `main`. A reusable read-only
`005`–`030` drift-audit query exists and can be re-run after any remediation.

## Security

- Neon production password **rotated** (a connection string was shared in-session during the
  rollout). Treat any in-session DB endpoint/token as exposed.

## Constraints honored

- #688 (preview/mock-only) and #697 (separate bugfix candidate) untouched.
- Migration 030 / audit hardening not modified post-merge.
