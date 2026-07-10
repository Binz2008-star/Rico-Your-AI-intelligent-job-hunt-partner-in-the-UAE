# 2026-07-10 — Full System Audit (production readiness gate before Atelier rollout)

Read-only audit run before starting the `DEC-20260710-001` Atelier rollout. Owner accepted
the verdict in-session. Audited commit: `main` = `db3d7226c1ed87990db2abbb964e6e4196526213`.

## Verdict

**YELLOW — acceptable. Zero P0/P1 blockers. UI migration may start after the Phase 0
docs PR merges** (owner instruction). Phase gates below.

## Confirmed production facts

- Render backend serves `main` exactly (`/version.commit` match); `/health` OK;
  jooble/adzuna/jsearch configured, none degraded.
- Vercel proxy chain (`ricohunt.com/proxy/*`) healthy — identical payloads to direct backend.
- No localhost DB fallback (`db.py`/`rico_db.py` hard-require `DATABASE_URL`).
- 15/15 public routes 200 (< 0.8s): `/`, `/login`, `/signup`, `/forgot-password`,
  `/upload`, `/subscription`, `/privacy`, `/refund-policy`, `/terms`, `/design-preview`,
  `/rico-preview`, `/design-gallery`, `/reset-password`, `/verify-email`
  (+ `/onboarding` 307→`/command` by config — see P2 hybrid finding).
- `/design-preview` is `noindex,nofollow`; no production-nav links to preview routes.
- Public chat: hello EN ✓, Arabic ✓ (no crash, fluent reply), guest job search returns
  `onboarding_cta` with zero fabricated listings ✓, empty message → clean 422 ✓,
  no provider names in user-visible text ✓.
- Billing: `NEXT_PUBLIC_BILLING_MODE` defaults manual → WhatsApp-assisted; live page has
  zero Stripe/sandbox/test strings; code guard never calls Stripe checkout in manual mode.
- `/flow` = pipeline source of truth (all 5 nav components); `/applications` is a clean
  5-line `redirect("/flow")`.
- Security: admin data API 401 unauth; `/admin/leads` client-gated; unauth `/me` returns
  data-free guest identity; no secrets in tracked files; no `.env` tracked.
- Frontend: `npm run build` exit 0; vitest 19 failed / 302 passed — exactly the known
  pre-existing baseline (9 files, `next/navigation` mocks), zero new failures.
- Backend: focused pytest 225 passed / 3 failed (known-stale, below); `py_compile` clean
  on `run_daily.py`, `api/app.py`, `rico_chat_api.py`, `chat_service.py`, `agent/runtime.py`.
- Guest render smoke, local production build of the same commit, mobile 390×844 +
  desktop 1440×900: `/`, `/login`, `/subscription`, `/design-preview`, `/rico-preview`,
  `/command`, `/flow`, `/dashboard` all render with 0 application console errors.

## Real production bugs found

None at P0/P1. No broken user flow, no data exposure, no crash, no fake-success path.

## Tooling-only failures (NOT Rico bugs)

- Playwright against `ricohunt.com`: container's TLS-intercepting proxy vs Chromium
  (TLS verification was not disabled). Covered by local-build smoke + CI Playwright + curl.
- Render log inspection: Render MCP `unauthorized` for this session.
- Vercel deployment-object inspection: Vercel MCP unauthenticated (owner can authorize
  via claude.ai connector settings).
- Two transient invocation errors (script module resolution; stale cwd) — retried, passed.

## Inconclusive (honest gaps)

- Authenticated smokes (login → `/me` → profile/settings → authenticated `/command`,
  auth-flash, "I applied" persistence honesty): no smoke credentials available to agent
  sessions → TASK-20260710-007.
- Render runtime error logs: MCP unauthorized (indirect signals healthy).

## Findings table

| # | Finding | Sev | Blocks rollout? | Task |
|---|---|---|---|---|
| 1 | 3 stale `test_agent.py` apply-link tests (pre-trust-gate contract); file absent from CI pytest selection | P2 | No | TASK-20260710-004 |
| 2 | `/onboarding` hybrid dead-UI (config redirect + real 466-line page; violates DEC-20260628-001) | P2 | **Phase 4 gate** | TASK-20260710-005 |
| 3 | vitest `next/navigation` mock baseline (19 failures in the exact surfaces Phase 3 touches) | P2 | **Phase 3 gate** | TASK-20260710-006 |
| 4 | No agent-runnable authenticated smoke path | P2 | **Phase 3 gate** | TASK-20260710-007 |
| 5 | Public chat API exposes internal metadata (`active_provider`, `deepseek_available`, `hf_available`, `model`, `jotform_form_id`) | P3 | No | backlog |
| 6 | `/version.deployed_at` stale (2026-05-23 hardcoded; `started_at` correct) | P3 | No | backlog |
| 7 | `/queue` is a live, functional 177-line approval-queue page, unlinked + undocumented | P3 | No | backlog |
| 8 | CLAUDE.md route drift (`GET /api/v1/user/profile` nonexistent; actions route is `POST /api/v1/actions/run`) | P3 | No | fixed in this Phase 0 PR (docs-only) |
| 9 | PR board staleness: #872/#873 (design-gallery only; #873 has an unresolved lint-blocking review thread), #899 held under #871 freeze | P3 | No | owner decision |

## Stop/rollback conditions for the rollout

Stop if: any new P0/P1 mid-phase; a post-merge production smoke fails (revert PR →
Vercel auto-redeploy → re-smoke); a phase PR touches backend/auth/billing/Neon/schema;
a phase gate cannot be satisfied. Every phase stays single-PR revertible.

## Session provenance

Audit performed read-only by Claude (session of 2026-07-10): no code changed, no PRs
opened during the audit, no accounts created, no credentials used or printed. Phase 0
docs PR (this handoff, `DEC-20260710-001`, TASKS -003..-007, CURRENT_STATE header,
CLAUDE.md route corrections) is the only write that followed, owner-approved.
