# Full System Audit — 2026-07-20

**Baseline:** `main` HEAD `e44466b2` (PR #1227). Working tree clean.
**Method:** read-only ground-truth pass (git, GitHub PRs/issues, AI_WORKSPACE),
five parallel layer auditors (auth ×2, billing/quota, uploads, chat-runtime,
database), then independent verification of every finding before any fix. Each
fix is an isolated branch off `main` with a regression test proven to fail
pre-fix, opened as a small Draft PR.

Evidence standard: `file:line`, commit SHA, or reproducible test output only.
Agent reports were treated as leads, not proof — every fixed finding was
re-verified by direct code reading in this session.

---

## Fixed — Draft PRs opened (CODE VERIFIED; CI in progress/green)

| # | Finding | Severity | Evidence | PR | Tests | State |
|---|---------|----------|----------|----|-------|-------|
| 1 | DOCX decompression-bomb guard bypassed on the classifier path — `document_classifier._extract_docx` (runs first) had no size guard; the #1058 guard lived only in `cv_parser._parse_docx`. Small `.docx` declaring multi-GB inflated → worker OOM. | **P0** (OOM-DoS) | `src/services/document_classifier.py:416`; `src/cv_parser.py:346`; order `rico_chat.py:1718` vs `:1985` | #1231 | 6 new; 70+201 area pass; pre-fix inflate demonstrated | review |
| 2 | `whatsapp_requests_repo` never closes its DB connection (all 3 fns) — `get_db_connection()` opens a fresh psycopg2 conn (no pool). Latent (flag off) but exhausts Neon on enable. | **P1** | `src/repositories/whatsapp_requests_repo.py:72,122,153`; `main` has 0 `conn.close()` in module | #1232 | 8 new; 31 pass | review |
| 3 | Telegram alert roster decoded RealDictCursor rows with `dict(zip(cols,row))` → `{col: col}`; every `telegram_chat_id` became the string `"telegram_chat_id"` → daily sender delivers to no one. | **P2** | `src/repositories/profile_repo.py:1007`; sibling email roster uses `dict(row)` `:1084` | #1233 | 3 new | review |
| 4 | `/agent/chat` action idempotency keyed on `sha256(action_type:link)` (no user) + global `is_duplicate` SQL → one user's action suppresses another user's identical action for 1h. Runtime path was safe (its key folds user_id). | **P1** (cross-user) | `orchestrator.py:86`; `audit_repo.py:67` (no user in SQL); `response_builder.py:487` | #1234 | 4 new; 116 pass; cross-user fail-pre-fix demonstrated | review |
| 5 | Save-job card claimed success on failure — on `handle_action` failure still said "Noted … is in your tracker", violating the #764 mutation-confirmation contract (Skip handler #1220 is honest). | **P2** (trust) | `src/rico_chat_api.py:10580,10628` | #1235 | 2 new; 173 pass; stash-proven fail pre-fix | review |
| 6 | `POST /subscription/intent` unauthenticated with no rate limit and no field length caps → anonymous storage flood of `subscription_intents`. | **P2** | `src/api/routers/subscription.py:28`; `src/schemas/subscription.py:78` | #1236 | 4 new; 62 pass | review |
| 7 | SSE `done` events serialized with bare `_json.dumps`; a stray non-JSON field raises TypeError mid-stream → generic "Stream error", dropping the persisted reply. Recurred 3× in a week (#1210/#1222/#1225). | **P2** | `src/api/routers/rico_chat.py` (7 done-event sites) | #1239 | 4 new; 162 pass | review |
| 8 | `verify_credentials` env-fallback prod-detection read only `RICO_ENV`/`ENV`; a deploy marking prod via `APP_ENV`/`ENVIRONMENT` left env admin login enabled during a DB outage. | **P2** | `src/api/auth.py:226` vs `_is_production()` `:358` | #1240 | 1 new; 49 pass | review |

All six are backend-only, no schema/migration/env change, global (not
account-specific), each with a documented rollback (revert the squash commit).

---

## Deferred — OWNER DECISION or already tracked (no unilateral change made)

- **JWT revocation on password-reset / logout (P1/P2).** Stateless JWT carries no
  epoch/`jti`; a stolen token stays valid to its TTL after the victim resets.
  **Already implemented in Draft PR #1138** (`auth_version`), which the owner
  explicitly **DEFERRED pending the migration-045 change window.** No action —
  owner-gated. (Sub-item: `reset_password` doesn't purge the user's *other*
  outstanding reset tokens — fold into #1138.)
- **Free daily AI-message cap dodge via public chat (billing P1).** A registered
  free user over their 10/day cap can route conversational AI through
  `/chat/public` with a `session_id` and no email (cap only applies to
  `auth_type=="authenticated"`; bounded by the IP 10/min limit). Fixing this
  means capping anonymous LLM turns on the landing page — a **product decision**
  (anonymous access policy). Not changed unilaterally. `subscription_gating.py:292`.
- **Usage counter fails OPEN on store error (billing P1).** If both the DB and
  memory count paths raise, `count_monthly_ai_messages` returns `0` → unlimited
  free AI during an outage. Failing *closed* blocks all free users during any
  transient DB hiccup — an **availability-vs-cost tradeoff** for the owner.
  `subscription_gating.py:150,172`.
- **TOCTOU on the daily counter (P2/P3).** Count-then-write with no atomic
  reservation; K concurrent messages near the cap over-grant by up to K−1.
  Bounded, no data corruption. Accept as a soft limit or move to an atomic
  per-user/day counter row — owner call. (Confirmed by both billing + DB agents.)
- **Uploads — image attachment charged CV storage quota (P2).** `/upload-cv`
  enforces `cv` quota at function entry, before classification, so a Free user at
  1/1 CVs is blocked from attaching a job screenshot. **Already has Draft PR
  #1230** (independently confirmed real). `rico_chat.py:1666`.

## Recommended smaller hardenings (not yet PR'd — low risk, owner may greenlight)

- **`RegisterRequest.role: Literal["admin","user"]` footgun (L1).** Currently
  ignored (endpoint hardcodes `role="user"`), but advertised in the schema; a
  future refactor passing `req.role` through would reopen public admin creation.
  Drop the field. `src/schemas/auth.py:73`.
- **Env-auth production-detection inconsistency (L2).** `verify_credentials` reads
  only `RICO_ENV`/`ENV` while `_is_production()` also honors `APP_ENV`/
  `ENVIRONMENT`; a deploy marking prod only via `APP_ENV` could allow env-fallback
  admin login during a DB outage. Unify on `_is_production()`. `auth.py:226`.
- **`GET /jobs/{job_id}` legacy global fallback (M2).** Falls back to the
  single-user `applied_jobs.json`/`job_history.json` and returns it to any
  authenticated user. Low practical exposure (ephemeral FS) but breaks isolation.
  `jobs_service.py:214`.
- **Rate-limit coverage gaps (M3).** No `@limiter.limit` on `/agent/chat` (LLM
  cost), `/jobs/*` (incl. apply), `/applications/*`, `/settings/*`. `LIMIT_ADMIN`
  exists but is unused on admin routes.
- **Test pollution (L5).** `tests/test_password_reset.py:21` sets
  `os.environ["RICO_ENV"]="development"` at import (no monkeypatch), shadowing the
  `ENVIRONMENT=production` fixture in `test_1070_guest_identity_binding.py`; two
  fail-closed tests fail together in-suite, pass in isolation. Product behavior is
  correct; the leaky env masks a real regression class in CI.
- **`job_tools.save_job` masks persistence (chat).** Returns `success=True`
  unconditionally, discarding the `saved` bool — orchestrator-tool path only
  (production uses the DB runtime path fixed in #1235). `job_tools.py:121`.
- **CI flakiness (test-quality).** Two frontend/e2e tests are intermittently
  red on unrelated backend PRs and pass on re-run: `chat-confirm-profile.test.tsx`
  ("Use this profile", 832/833) and `e2e/refine-search-structured.spec.ts:168`
  (DOM detachment mid card re-render). Observed red on #1239's first run
  (backend-only) and green after re-trigger. A stability follow-up would stop
  these masking real regressions and forcing re-kicks.

---

## Verified CLEAN (independently confirmed this session)

- **Auth/authz (two independent audits agree):** every per-user route derives
  identity from the JWT, not request-body `user_id`; DB queries scoped by
  `user_id`; webhooks (Jotform/Telegram/GitHub/Paddle) fail-closed with
  constant-time compares + bounded bodies; guest capability HMAC uses a dedicated
  secret; JWT alg pinned HS256; signup forces `role="user"`; XFF rate-limit key
  trusts N-from-right. **No P0/P1 IDOR/auth-bypass.**
- **Billing core:** Paddle signature verify fail-closed + body cap before verify +
  300s replay window; idempotent claim; event ordering guarded; identity DB-first
  (never trusts `custom_data.user_id`); WhatsApp channel grants no entitlement;
  admin-activate is admin-only; UTC daily-reset math correct.
- **Uploads:** streaming body-size cap before buffering; magic-byte type detection
  (client Content-Type never trusted); ELF/MZ executables hard-rejected;
  identity-document blocking with no persistence; content-hash dedupe; sync CV
  parser wrapped in `run_in_executor`.
- **Chat/SSE:** every stream path emits a terminal event (error on exception);
  session ContextVar isolation is per-request (`copy_context`); guest/JWT session
  ids can't collide; provider fallback doesn't double-count usage.
- **DB:** ON CONFLICT arbiters all match real constraints; connection close on all
  paths except the whatsapp repo (fixed); migration numbering gaps 039/042/045 are
  **benign** (signature-based drift check, no contiguous-numbering loader).
- **Infra:** no `pull_request_target` in any workflow; private-cache middleware
  (`no-store` default); notification router never leaks admin alerts to user chat.

---

## Owner actions required

1. Decide the two billing product/availability questions (public-chat cap dodge;
   fail-open counter).
2. Open the migration-045 change window for #1138 (JWT revocation) when ready.
3. Review/merge Draft PRs #1231–#1236 (all backend-only, tested, reversible).
   None may be merged or deployed without owner approval.

_No merges, deploys, production migrations, secret changes, or environment
mutations were performed. All work is in isolated Draft PRs or documented above._

---

## Closure (2026-07-20, same day — owner-directed delivery)

Owner approved and directed the delivery closure ("finish current work and
pendings → merge safely"). Every fix merged **one at a time** with exact-head
CI green (QA Tests), zero unresolved review threads, and a single-revert
rollback path verified before each merge; state re-checked after every merge.

| Finding / fix | PR | Head SHA | Squash on main | Status |
| --- | --- | --- | --- | --- |
| P0 DOCX decompression bomb — classifier path | #1231 | `52b54c5e` | `3c3f58f9` | **merged** |
| P1 /agent/chat idempotency cross-user scope | #1234 | `a5744f62` | `bebab29e` | **merged** |
| P1 whatsapp_requests_repo connection leak | #1232 | `d0f6b715` | `247bc1e3` | **merged** |
| P2 auth env-fallback production detection | #1240 | `774d18a2` | `4b120316` | **merged** |
| P2 telegram roster RealDictCursor decode | #1233 | `fc4f1838` | `5f461211` | **merged** |
| P2 save-card honest failure copy | #1235 | `f50a3c08` | `73979eaa` | **merged** |
| P2 /subscription/intent rate-limit + caps | #1236 | `a120cf7f` | `6c4879b2` | **merged** |
| P2 SSE done-event total encoder | #1239 | `d2caa548` | `09dbe9d9` | **merged** |
| QA stability — spec-side (baseline Playwright race) | #1244 | — | `3e967cd0` | **merged** |
| QA stability — product-side (late empty bootstrap wiped live transcript; deterministic regression, proven fail-pre/pass-post) | #1246 | `5962bbae` | `bc6d8ba0` | **merged** |

The #1239 QA blocker was the refine-search flake: #1244 closed the test-side
race (sessions mock + settle gates, assertions preserved) and #1246 closed the
product-side root cause (welcome effect no longer replaces a non-empty
transcript — same guard contract as the has_history path).

Deferred/owner-decision items above remain open and unchanged (billing
questions, #1138 migration-045 window, PDF extraction bounds, broader
rate-limit coverage, `RegisterRequest.role` dead field, orchestrator→runtime
delegation refactor).
