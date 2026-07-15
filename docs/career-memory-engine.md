# Career Memory Engine — M1 Operations (ADR-001)

Status: **M1 — shadow writes only.** No reader exists; nothing user-visible
depends on these tables. Decision record:
`AI_WORKSPACE/ADR/ADR-001-rico-career-memory-engine.md` (ACCEPTED 2026-07-14).

## What M1 ships

- Migration `042_career_memory_engine.sql` — two additive tables:
  `career_memory_events` (append-only episodes) and `career_memory_facts`
  (current value + full change history via `effective_from`/`effective_to`/
  `superseded_by`).
- `src/services/memory_writer.py` — the single writer (`memory_writer`
  singleton). Enforces the feature flag, kill switch, circuit breaker,
  canonical identity, mandatory provenance, trust hierarchy, and the
  secret/billing/document exclusion filter.
- `src/repositories/career_memory_repo.py` — all SQL, per-account only.
- One integration point: `agent_runtime.handle_action()` step 11b shadow-writes
  successful job actions (`apply/save/skip/block/not_relevant`) alongside the
  legacy `career_memory.py` write. Fire-and-forget; the action result is
  byte-identical whether the engine is on, off, or broken.

## Flags

| Env var | Default | Meaning |
| --- | --- | --- |
| `RICO_MEMORY_ENGINE_ENABLED` | `false` | Master enable. M1 ships dark; nothing is written until this is `true` on Render. |
| `RICO_MEMORY_ENGINE_KILL` | unset | Hard kill switch. `true` disables all memory writes even when the enable flag is on. Use this to stop writes without touching the enable flag's configured value. |

A third, automatic protection: an in-process **circuit breaker** opens after 5
consecutive database failures and suspends writes for 300 s (log line
`memory_engine_breaker_open`). It closes itself; no operator action needed.

## Identity model (ADR §3)

Writes are keyed by the canonical immutable account ID — `rico_users.id`
(UUID) — resolved at the write boundary from whatever external identity the
caller holds (email, telegram id, `public:web-*` session). The writer never
creates identity rows. Public sessions resolve only to their own exact
`external_user_id` row; any fuzzier resolution is refused and logged
(`memory_engine_public_merge_blocked`) — the explicit, audited public→account
merge step is M5 scope.

## Metrics

`memory_writer.metrics_snapshot()` returns in-process counters:

- `written` / `duplicate` / `failed`
- `skipped_disabled`, `skipped_breaker_open`, `skipped_no_account`
- `rejected_excluded` (exclusion filter), `rejected_provenance`,
  `rejected_lower_tier`, `rejected_unverified_tier`
- `breaker_trips`
- `drift_engine_miss` (legacy store wrote, engine didn't) and
  `drift_legacy_miss` (engine wrote, legacy didn't) — measured per shadow
  write while both stores run in parallel; every drift event also logs a
  `memory_drift` warning line visible in Render logs.

Drift reconciliation query (legacy `_cm` entries vs engine episodes for one
account):

```sql
-- engine side
SELECT COUNT(*) FROM career_memory_events
WHERE account_id = '<uuid>' AND event_type LIKE 'job_action.%';

-- legacy side (entries under the "_cm" key of the same account's settings)
SELECT jsonb_array_length(COALESCE(settings->'_cm', '[]'::jsonb))
FROM rico_agent_settings WHERE user_id = '<uuid>';
```

The legacy store caps at 200 entries per user (oldest dropped), so on
long-active accounts the engine count may legitimately exceed the legacy
count; per-write drift metrics are the primary signal, the counts are the
coarse check.

## Rollback

M1 is dark by default, so rollback is layered — use the smallest step that
stops the problem:

1. **Flag off** (`RICO_MEMORY_ENGINE_ENABLED=false` or unset on Render):
   stops all writes. Zero user impact — no reader exists. This is the normal
   rollback and needs no code change or migration.
2. **Kill switch** (`RICO_MEMORY_ENGINE_KILL=true`): same effect, expresses
   "stopped due to an incident" without losing the configured enable value.
3. **Code revert**: revert the M1 PR. The runtime step 11b disappears; legacy
   career memory (step 11) is untouched and remains the behavior of record.
4. **Schema removal** (only with explicit owner approval — data deletion):

   ```sql
   DROP TABLE IF EXISTS career_memory_facts;
   DROP TABLE IF EXISTS career_memory_events;
   ```

   Shadow rows are reconstructible: every M1 episode mirrors a legacy
   `_cm` entry and links its `action_audit_log` record via
   `source_record_id`, so dropping the tables loses nothing that cannot be
   backfilled (below).

## Backfill

When the engine is enabled after having been off (or after a schema
rollback), historical job actions can be backfilled from the legacy store —
each `_cm` entry becomes one episode:

```sql
INSERT INTO career_memory_events (
    account_id, event_type, idempotency_key, occurred_at, actor, source,
    source_record_id, confidence, payload, retention_class
)
SELECT
    s.user_id,
    'job_action.' || (e->>'a'),
    'backfill:_cm:' || s.user_id || ':' || (e->>'ts') || ':' || (e->>'a') || ':' || COALESCE(e->>'jk', ''),
    to_timestamp((e->>'ts')::bigint),
    'user',
    'verified_event',
    'rico_agent_settings:_cm:' || s.user_id,
    1.0,
    jsonb_build_object(
        'action', e->>'a', 'title', e->>'ti',
        'company', e->>'co', 'job_key', e->>'jk',
        'surface', 'backfill'
    ),
    'episode'
FROM rico_agent_settings s,
     jsonb_array_elements(COALESCE(s.settings->'_cm', '[]'::jsonb)) AS e
ON CONFLICT ON CONSTRAINT uq_career_memory_events_idem DO NOTHING;
```

Idempotent (`ON CONFLICT DO NOTHING` against the same unique constraint the
writer uses) — safe to re-run. Do not run against production without explicit
owner approval; the full legacy-store migration is M5 scope.

## What M1 must NOT do (owner-accepted scope)

No MemoryReader rollout, no chat-context change, no summarization jobs, no
legacy-store retirement, no user-visible behavior change, no public-session
implicit merge, no billing/security/document payload copies. Re-check this
list before extending anything in this module tree.
