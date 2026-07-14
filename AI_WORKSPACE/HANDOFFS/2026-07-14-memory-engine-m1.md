# Handoff — Career Memory Engine M1 (ADR-001, shadow writes)

Date: 2026-07-14 · Branch: `feat/memory-engine-m1` · ADR: `AI_WORKSPACE/ADR/ADR-001-rico-career-memory-engine.md` (ACCEPTED)

## What M1 ships (strict owner scope)

- `migrations/042_career_memory_engine.sql` — additive, idempotent:
  `career_memory_events` (append-only envelope, `UNIQUE (account_key,
  idempotency_key)`) + `career_memory_facts` (history via
  `effective_from`/`effective_to`, partial-unique current row for
  single-valued classes). Auto-applied by the app.py lifespan runner
  (`_apply_career_memory_engine`, same pattern as 028/031/032/038).
- `src/services/memory_writer.py` — the single write path: flag-gated,
  never-raises, idempotent, canonical-ID keyed (`acct:<rico_users.id>` /
  `session:<public:web-…>`), §8 exclusion filter, in-process failure/drift
  counters (`get_write_stats`) + structured `memory_write_failed` log lines.
- One shadow hook in `agent_runtime.handle_action()` (step 8b): fire-and-forget
  `record_action_episode` reusing the runtime's own md5 action identity as the
  idempotency key. **No reader, no chat/context change, no legacy migration,
  no user-visible change.**

## Flag / kill switch

`RICO_MEMORY_ENGINE_ENABLED` — default **OFF** (unset/anything-but-"true").
Read at call time: setting it to anything other than `true` on Render stops
all writes immediately (kill switch). Do NOT set it in production until the
owner starts the M1 shadow-observation window.

## Backfill plan (deliberately NOT part of M1)

M1 records only new action episodes. Historical backfill happens in M5
(legacy-source migration), one source at a time, each behind its own PR:
`career_memory.py` settings-JSON entries → episodes (idempotency key =
hash of the legacy entry), then `user_job_context` interactions. Backfill is
re-runnable because every insert is `ON CONFLICT DO NOTHING` on the same key.

## Rollback plan

1. Instant: set `RICO_MEMORY_ENGINE_ENABLED=false` (or unset) — writes stop;
   the action path is untouched either way (fire-and-forget + try/except).
2. Code: revert the single M1 commit — removes the writer, the runtime hook,
   and the lifespan migration call. No caller depends on any of it.
3. Schema: tables are additive and unread; they may stay empty harmlessly.
   Dropping them (if ever desired) is a separate owner-approved destructive
   migration — NOT part of the standard rollback.

## Verification run

- `pytest tests/test_memory_writer.py` → 13 passed (flag default-off, kill
  switch, canonical keying, public-session separate keying + no lookup,
  idempotent dedup-as-success, per-user isolation, unresolved-identity skip,
  §8 exclusion filter incl. nesting + truncation, DB-exception swallowing,
  invalid-envelope rejection, runtime unaffected when the writer explodes,
  runtime passes its md5 identity through).
- `pytest tests/test_agent_runtime.py tests/test_jwt_user_isolation.py
  tests/test_p0_mutation_trust_guard.py` → 129 passed (zero regression).
- `python -m py_compile` on the three touched modules → OK.

## Shadow-observation metrics (for the M1→M2 gate)

While the flag is on in a controlled window, watch Render logs for
`memory_write_failed` / `memory_write_skipped` lines and (optionally) expose
`get_write_stats()` via an admin-only surface later. Drift check: compare
`career_memory_events` action counts vs `action_audit_log` for the same
window — they should match 1:1 for flag-on periods.

## Next exact action

Owner reviews the M1 Draft PR. Per the owner's instruction, M1 **stops before
merge**. After merge + a shadow window with clean metrics, M2 (decisions &
reasons + commitments capture) starts as its own PR.
