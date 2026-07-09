# Handoff — 2026-07-09 Security/data-risk deep dive (#127, #198)

## Task

Read-only, code-level verification of the security/data-risk claims in #127 and #198, flagged
"needs full deep dive" by the same-day board-health scan (`HANDOFFS/2026-07-09-board-health-scan.md`),
before touching #758/#812/#446.

## Context

- Repository: Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE
- Branch: none during the deep dive (read-only); persisted via `docs/security-data-risk-deep-dive`
- Issue or PR: #127, #198 (read-only inspection); #263 deferred, not checked
- Relevant files: `src/rico_db.py`, `src/repositories/subscription_repo.py`,
  `src/repositories/profile_repo.py`, `src/repositories/applications_repo.py`,
  `src/indeed_apply.py`, `src/run_daily.py`, `src/db.py`, `src/services/chat_service.py`,
  `.github/workflows/daily.yml`, `.env.example`, `requirements.txt`,
  `apps/web/components/auth/LoginForm.tsx`, `apps/web/app/subscription/page.tsx`
- Relevant architecture notes: `AI_WORKSPACE/HANDOFFS/2026-07-09-board-health-scan.md`

## Constraints

- Out of scope: any code change, test change, label change, issue close, Neon/Vercel/Render
  touch, running SQL against Neon, starting #758/#812/#446
- Compatibility requirements: n/a (read-only)
- Style and typing requirements: n/a (read-only)
- **This deep dive was performed by direct manual code inspection (Read/Grep against current
  `main`). No Codex or other automated review tool was run on it — do not represent this result
  as Codex-reviewed.**

## Acceptance Criteria

- [x] Every named claim in #127 checked against current `main` code
- [x] Every named claim in #198 checked against current `main` code (except lower-severity C3,
      C4, H1, H2, H4, M1–M7, L1–L4 — deferred, not checked)
- [x] Each claim classified: still present / fixed / partially fixed / cannot verify, with
      severity, file/function evidence, and (if still present) a smallest-safe-fix sketch
- [x] No code changed, no issues closed, no labels changed during the deep dive itself

## Continuity Block

Copy verbatim from the `AI_WORKSPACE/TASKS.md` entry this handoff closes (`TASK-20260709-002`):

- Task ID: TASK-20260709-002
- GitHub issue/PR: #127, #198 (read-only; #263 deferred)
- Branch: none during the deep dive; persisted via `docs/security-data-risk-deep-dive`
- Base branch: main
- Last safe commit SHA: d2bd86093a155b91522c4cb02e9cd6db23b498d2
- Current head SHA: d2bd86093a155b91522c4cb02e9cd6db23b498d2 (deep dive made no code commits)
- Status: done
- Files changed: none during the deep dive; this docs-only PR changes `PROJECT_STATUS.md`,
  `CURRENT_STATE.md`, `TASKS.md`, this handoff, `MASTER_INDEX.md`
- Files intentionally not touched: all runtime code (read-only inspection only), tests, Neon,
  Vercel/Render config, issue labels/state
- Known blockers: none
- Validation already run: direct `grep`/`Read` inspection of every file/function named in each
  claim below
- Validation still required: #263 deep dive (if picked up); lower-severity #198 items (C3, C4,
  H1, H2, H4, M1–M7, L1–L4)
- Next exact action: #446 read-only Neon precheck (count/identify affected rows, confirm #445
  root cause still holds, prepare transaction + rollback SQL) — no cleanup execution without
  explicit owner approval
- Stop condition: do not execute #446 cleanup, or start #758/#812, or fix the `profile_repo.py`
  leak, until the owner reviews the precheck and explicitly approves each next step
- Rollback plan: revert this docs-only PR; no schema/env/runtime changes

## #127 verdict — P0/P1 hardening audit (2026-05-14)

| Claim | File/function checked | Status | Severity |
|---|---|---|---|
| SQL injection in `get_recommendations` (user-controlled `status` in clause) | `src/rico_db.py:792` `get_recommendations` | **Fixed** — `status` is never interpolated into SQL; only a fixed clause template (`"status = %s"`) is built, and the actual value goes through `cur.execute(sql, params)` parameterization. | n/a (resolved) |
| Hardcoded PII in `indeed_apply.py` | `src/indeed_apply.py:748-749` | **Fixed** — `name = os.getenv("INDEED_NAME", "")`, `email = os.getenv("INDEED_EMAIL", "")`. Reads from env, not hardcoded. | n/a |
| `.env.example` contains a real-looking Neon string | `.env.example` | **Fixed** — placeholder only: `postgresql://user:password@host/dbname?sslmode=require`. | n/a |
| `daily.yml` dashboard publish uses `if: always()` | `.github/workflows/daily.yml:77-92` | **Fixed** — `if: always()` now only guards a Gmail-OAuth-file cleanup step (correct use). The dashboard artifact upload and `deploy-dashboard` job both already use `if: success()`. | n/a |
| `src/db.py` `autocommit=True` destroys atomicity | `src/db.py` (whole file) | **Fixed / not present** — `autocommit` is never set anywhere; `psycopg2.connect()` defaults to explicit-transaction mode, with paired `_commit()`/`_rollback()` helpers. | n/a |
| Application pagination loads all rows into memory | `src/api/routers/applications.py:127-146` | **Still present** — `list_applications()` slices an already-fully-fetched `all_apps[offset:offset+limit]` in Python, not in SQL. | Low (correctness/scale, not security) |
| `run_daily.py` distributed lock fails open | `src/run_daily.py:283-307` `distributed_lock()` | **Still present** — `if not REDIS_AVAILABLE: yield True` and the `except Exception: ... yield True` fallback both let the pipeline proceed without the lock instead of blocking. | **Medium** — a transient Redis error lets two cron runs execute concurrently |
| Hardcoded Prometheus port 8000 collision | `src/run_daily.py:117,345` `start_http_server(8000)` | **Still present** — hardcoded twice, not env-configurable. Separate process from the FastAPI app (also port 8000 by default); collision risk only if ever co-located. | Low |
| Risky Playwright flags (`ignore_https_errors`, `--no-sandbox`) unconditional | `src/indeed_apply.py:391-401` `IndeedApplyEngine.__enter__` | **Still present**, but **dormant** — only reachable from `apply_service.py:321`, gated by `RICO_ENABLE_AUTO_APPLY` (default `false`). | Low (defense-in-depth gap, not live) |
| Unpinned `requirements.txt` | `requirements.txt` | **Still present** — most packages have no version pin; only a few (`sentry-sdk`, `slowapi`, `limits`) do. | Low (supply-chain hygiene) |

**#127 verdict: no live SQL-injection or credential-leak issue.** Named P0s are fixed. Remaining
items are lower-severity reliability/hygiene debt.

## #198 verdict — Defensive bug-hunt follow-up (2026-05-24)

| Claim | File/function checked | Status | Severity |
|---|---|---|---|
| C1 — connection leaks in `rico_db.py` / `subscription_repo.py` | `src/rico_db.py:268-320` (`connect()`/`_transaction()`), `src/repositories/subscription_repo.py` (`_db_transaction`, `get_subscription`, `get_subscription_by_stripe_customer`) | **Partially fixed** — `rico_db.py`'s own `_transaction()` and `subscription_repo.py`'s functions all explicitly `conn.close()` in a `finally`. But `rico_db.py`'s own code comment (lines 272-288) documents that pooling was disabled *because* callers use `with db.connect() as conn:` (commits/rollbacks but never closes) — and that exact pattern is still live in **`src/repositories/profile_repo.py` at lines 541, 583, 615, 651, 742** (5 call sites). | **Medium** — real leak; pooling is disabled so it leaks raw connections rather than starving a fixed pool, but can still exhaust Neon's connection limit under load |
| C2 — maintenance mode hardcoded `true` | `apps/web/components/auth/LoginForm.tsx:28`, `apps/web/app/subscription/page.tsx:25` | **Fixed** — both read `process.env.NEXT_PUBLIC_MAINTENANCE_MODE === "true"`. | n/a |
| H3 — `get_subscription_by_stripe_customer` returns first row only | `src/repositories/subscription_repo.py:81-120` | **Fixed** — `ORDER BY updated_at DESC LIMIT 1` present. | n/a |
| H5 — public chat accepts email identity without ownership proof | `src/services/chat_service.py:632-676` `_resolve_db_user_id` | **Fixed/mitigated** — auto-provisioning by email is explicitly gated: `if not user_id or user_id.startswith("public:") or "@" not in user_id: return None`. Public/guest session IDs cannot trigger email-based auto-provisioning. Lookup also prefers `id` > `email` > `external_user_id` specifically to avoid the cross-user contamination that caused #446. | n/a (resolved as part of the #445/#446 fix train) |
| H6 — `upsert_recommendation` TOCTOU race | `src/rico_db.py:846-873` | **Fixed** — `ON CONFLICT (user_id, job_key) WHERE job_key IS NOT NULL DO UPDATE`, backed by the migration-011 partial unique index (owner-verified applied in production). | n/a |
| C3, C4, H1, H2, H4, M1–M7, L1–L4 | — | **Not checked** — deferred; lower-severity, out of scope for this pass | — |

**#198 verdict: no live security hole.** The one confirmed still-live issue (`profile_repo.py`
connection leak) is a real reliability risk, not a security/data-integrity breach.

## Updated priority (owner decision, 2026-07-09)

1. **#446 read-only precheck** — count/identify affected rows, confirm #445 root cause still
   holds, prepare transaction + rollback SQL. Read-only Neon queries only; no cleanup execution.
2. **#446 cleanup** — execute only with explicit owner approval.
3. **Fix `profile_repo.py` connection leak** — owner ruling: not higher priority than #446, but
   ahead of #758/#812 product-quality work, given it's a confirmed real reliability issue.
4. **#758** — unify job-key scheme (duplicate DB rows from save-path key mismatch).
5. **#812** — fix compound-title role splitting.

## Deliverables

- Changed files: `AI_WORKSPACE/PROJECT_STATUS.md`, `AI_WORKSPACE/CURRENT_STATE.md`,
  `AI_WORKSPACE/TASKS.md`, this handoff, `AI_WORKSPACE/MASTER_INDEX.md`
- Implementation summary: docs-only persistence of the #127/#198 read-only deep-dive verdict and
  the owner's updated priority order
- Tests run: none (docs-only; no runtime/test files touched)
- Risks: none — pure documentation, no schema/env/runtime changes
- Rollback notes: revert this PR; no schema/env/runtime changes, isolated to the 5 files above

## Required Verification

```bash
grep -n "d2bd860" AI_WORKSPACE/PROJECT_STATUS.md AI_WORKSPACE/CURRENT_STATE.md
grep -n "TASK-20260709-002" AI_WORKSPACE/TASKS.md
grep -n "security-data-risk-deep-dive" AI_WORKSPACE/MASTER_INDEX.md
```

## Expected Response

```md
## Summary
Docs-only persistence of the 2026-07-09 #127/#198 security/data-risk deep-dive verdict: no
live security issue found; profile_repo.py connection leak confirmed as the one real
reliability issue. Updated priority order recorded.

## Changed files
- AI_WORKSPACE/PROJECT_STATUS.md — refreshed dashboard (main SHA, risks, next-ordered list)
- AI_WORKSPACE/CURRENT_STATE.md — new reconciliation header with the deep-dive verdict
- AI_WORKSPACE/TASKS.md — TASK-20260709-002 Continuity Block added
- AI_WORKSPACE/HANDOFFS/2026-07-09-security-data-risk-deep-dive.md — full per-claim detail (new)
- AI_WORKSPACE/MASTER_INDEX.md — handoff indexed as latest pointer

## Verification
- grep checks above — all found

## Risks
None — docs-only, no runtime/schema/env changes.

## Rollback
Revert this PR.

## Open questions
None.
```

## Reviewer Notes

- Scope respected: yes — only the 5 files listed above changed; no runtime code, tests, labels,
  issue state, Neon, or Vercel/Render config touched; no SQL run.
- Evidence complete: yes — every claim in the tables above cites the exact file/function checked;
  no claim of Codex/automated review (this was direct manual inspection only).
- Follow-up tasks: #446 read-only precheck is the required next step, per owner instruction —
  do not execute cleanup, do not start #758/#812, do not fix the `profile_repo.py` leak yet
  without further explicit approval on each.
