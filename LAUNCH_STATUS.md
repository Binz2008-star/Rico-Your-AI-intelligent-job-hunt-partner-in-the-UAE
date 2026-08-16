# Rico — Launch Status

> **Authoritative "where we are" snapshot.** Updated 2026-08-16 by the CTO
> engineering review after Phases 1–3 + launch-blocker closure + Docker
> production hardening, **including the post-merge verification of PR #1489 and
> the Docker-build follow-up fix**. This supersedes the older headers in
> `AI_WORKSPACE/CURRENT_STATE.md` for launch-state purposes.

## Verdict

```
PRODUCTION BLOCKED — EXTERNAL ACTIONS ONLY
```

The codebase is **code-frozen**, fully tested, secret-free, and Docker-ready.
PR #1489 (production hardening) is **MERGED into main** and post-merge CI is
green. Every remaining launch item requires access to external platforms
(Railway deploy serving, Vercel account status, GitHub branch protection, Neon
capacity confirmation, coverage-floor tightening, `${BACKEND_IMAGE}` /
`${WEB_IMAGE}` injection). There are **no unexplained code or test blockers**.

## Post-merge verification (2026-08-16)

- **Current `main` HEAD: `6b2a4042`** (PR #1491 merge commit). History:
  `d12624b2` = PR #1489 merge, `6b2a4042` = PR #1491 (Docker-build fix) merge.
- PR #1489 **merged** into `main` 2026-08-16T20:02:52Z via the normal GitHub
  merge mechanism; PR state `MERGED`; no conflicts.
- Post-merge CI on the merge commit — **all green**:
  - `QA Tests` (pytest / postgres-integration / playwright / frontend): success.
  - `Workflow Security Guards`: success. `Test Enumeration Guard`: success.
  - Coverage measured on the first main CI run: **57.55%** total (floor is 30%).
  - `Docker Production Build` (push-to-main run) initially **failed** with two
    genuine workflow defects — fixed in PR #1491 (merged, `6b2a4042`),
    validated end-to-end by `workflow_dispatch` before landing, and green on
    the post-merge main run (4m32s). The defects were:
      1. GHCR rejects mixed-case image paths; `github.repository` preserves the
         repo's original spelling, so the namespace is folded lowercase at
         runtime (`IMAGE_NAMESPACE`).
      2. On Linux runners a container's `localhost` is its own namespace — the
         backend smoke's containers now share a user-defined bridge network and
         reach Postgres via the `ci-pg` service name.
      Ref-tag is sanitized (`/` → `-`) so the workflow is valid on any trigger.
  - Images are pushed to GHCR under **immutable `sha-<git-sha>` references**
    (plus the ref tag).
- `Deploy to Production` (deploy-production.yml) post-merge **FAILED**:
  `https://api.ricohunt.com/health` → HTTP 404, i.e. Railway is not currently
  serving the backend. This is the **external Railway deploy gate** — no code
  change was made to bypass it.
- `Vercel` check: **FAIL** — "Account is blocked" (external platform account
  blockage; not a code or gate issue).
- GitHub **branch protection on `main`: NOT enabled** (API returns "Branch not
  protected") — external launch-control blocker.

## What is DONE (in-repo)

### Phase 1 — Critical production bugs & security
- AI spend gate **fails closed** on DB outage (`QuotaUnavailableError` →
  transient-outage terminal); public-email anti-dodge now actually enforces via
  a content-free usage ledger (migrations 053).
- Paddle refund/dispute/chargeback/termination downgrade entitlement;
  webhook idempotency + stale-guard; unknown price never grants paid.
- Scheduler stale-`running` recovery + `run_pipeline()` return-code
  propagation; Redis distributed lock **fails closed** and renews its TTL
  (heartbeat) every 30 s.
- Telegram: bound accounts run under the account identity (usage counted),
  unbound chats get a bounded daily AI allowance (fail-closed on DB down),
  callbacks respect the same rules, `update_id` dedup marks after success
  (no lost actions), replies no longer double-sent.
- SMTP timeouts, `/health` liveness + `/ready` readiness (DB-aware),
  log-privacy, no hardcoded owner identity.

### Phase 2 — Frontend guest→account merge + test debt
- H-5 guest→account merge wired (login/register offer the guest session;
  backend capability cookie remains authoritative; never mints on login).
- All 7 pre-existing test failures fixed (pool/lock/log-privacy portability,
  obsolete expectations corrected); CI baseline debt 204 → 200.

### Phase 3 — Engineering controls
- CI runs the full suite on **push to main**; `--timeout` turns hangs into
  failures; guards enforced (`check_workflow_security`, `check_test_enumeration`).
- Coverage config + `--cov-fail-under` (temporary 30% floor; baseline to be
  recorded on first protected CI run).
- Deterministic migration runner (`python -m src.db_migrations apply|check|status`):
  advisory-lock serialized, ordered, checksum-verified, fail-loud,
  self-bootstraps the runtime DDL on a fresh DB.
- Bounded per-process DB pool with rollback-on-release, dead-connection
  discard, statement timeout; dual-style rows (dict + positional).

### Launch blockers (closed)
- GitHub Actions SHA-pinned (28/28 workflows, zero `@v\d`); `tj-actions`
  removed.
- **Jotform** existing-account merge requires an out-of-band single-use
  confirmation (migration 054); no unverified overwrite.
- **OCR/vision** requires explicit consent + per-identity daily cap.
- Production API docs gated (`RICO_ENABLE_API_DOCS`, default off).
- Startup migration contract: `RICO_RUN_STARTUP_MIGRATIONS=false` + strict
  fail-closed schema check.
- **Telegram /start** username binds require an emailed single-use code.

### Docker production model (canonical runtime)
- `Dockerfile.backend` (multi-stage, non-root `rico`, no `--reload`,
  `/health` liveness healthcheck) and `apps/web/Dockerfile` (multi-stage,
  `next start`, non-root `node`).
- `docker-compose.prod.yml`: secret-free (`${VAR:?required}` runtime
  injection), `migrate` one-shot → backend → web, restart policies,
  resource limits, isolated network, immutable image placeholders.
- `docker-compose.yml` is explicitly LOCAL DEVELOPMENT ONLY.
- `.dockerignore` (root + web) excludes every secret/credential artifact.
- CI: `.github/workflows/docker-build.yml` builds both images, scans for
  secret artifacts, verifies non-root, smoke-tests (fresh-DB migration,
  `/health`, `/ready`, docs 404), pushes immutable `sha-<git-sha>` images.

## Test evidence (local, before push)

- Backend consolidated: **710 passed, 0 failed**.
- Real-Postgres integration (`tests/integration/`): **186 passed, 2 failed**
  — the 2 are documented pre-existing routing-drift failures in
  `tests/integration/test_chat_cv_job_workflow.py` (unenumerated, out of CI).
- Frontend: **103 files / 992 tests passed**; `tsc` clean for changed files.
- Guards: `check_workflow_security.py` and `check_test_enumeration.py` exit 0.
- Docker: build, fresh-DB migrate, strict-startup boot, `/health` 200 (stays
  200 on DB down), `/ready` 200 → 503 → recovery, docs 404, graceful shutdown,
  restart healthy, image secret scan clean.

## EXTERNAL LAUNCH BLOCKERS (owner actions — still open)

Credential **rotation is CLOSED** (owner completed). What remains is external:

1. **Railway deploy gate — currently FAILING.** `https://api.ricohunt.com/health`
   returns HTTP 404 (backend not serving). The post-merge `Deploy to
   Production` verification workflow correctly failed; deploy
   green-commit-only is **not yet confirmed**. This must be resolved in
   Railway before production can go live.
2. **Vercel account blocked.** The `Vercel` CI check fails with "Account is
   blocked" — an external platform account blockage on Vercel's side. It is
   **not** a code or gate defect; do not weaken CI to bypass it.
3. **Enable GitHub branch protection** on `main` (currently NOT enabled)
   requiring: `QA Tests / pytest`, `QA Tests / postgres-integration`,
   `QA Tests / playwright`, `QA Tests / frontend`, `Workflow Security
   Guards`, `Test Enumeration Guard`, `Log Privacy Ratchet`. All are verified
   green on main and ready to be marked required.
4. **Tighten the coverage floor.** First main-CI baseline recorded: **57.55%**
   (`--cov-fail-under` is 30%). Tighten to `baseline − tolerance` (CTO
   decision) only after the baseline is stable.
5. **Confirm the Neon connection ceiling** against
   `replicas × DATABASE_POOL_MAXCONN (5) + cron pool (5) + migrate (1)`.
6. **Set `${BACKEND_IMAGE}` / `${WEB_IMAGE}`** in `docker-compose.prod.yml` to
   the GHCR immutable `sha-<git-sha>` images now pushed by the pipeline.
7. **Historical credential purge** (separate authorized security-maintenance
   action, not a launch gate): revoke commit-`1882e8b9` `RAPIDAPI_KEY`,
   `EMAIL_USER`, `EMAIL_PASS` if still active; rewrite history only under
   explicit authorization. Do **not** recreate the deleted
   `rico-job-automation-api.env`; secrets are runtime-only.

## How to migrate a database

```bash
# Fresh OR existing database — the runner bootstraps runtime DDL then applies
# all numbered migrations 005..054 in order, under an advisory lock.
python -m src.db_migrations --dsn "$DATABASE_URL" apply
python -m src.db_migrations --dsn "$DATABASE_URL" check   # must report clean
python -m src.db_migrations --dsn "$DATABASE_URL" status  # applied/pending
```

Never run migrations inside the app container; production runs the one-shot
`migrate` compose service with `RICO_RUN_STARTUP_MIGRATIONS=false`.

## New environment variables (runtime)

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_POOL_MINCONN` / `DATABASE_POOL_MAXCONN` | per-process pool bounds | 1 / 5 |
| `DATABASE_POOL_TIMEOUT` | acquire timeout (s) | 5 |
| `DATABASE_CONNECT_TIMEOUT` | connect timeout (s) | 5 |
| `DATABASE_STATEMENT_TIMEOUT_MS` | server-side statement bound | 0 (off) |
| `RICO_RUN_STARTUP_MIGRATIONS` | `false` in production (strict fail-closed check) | true |
| `RICO_ENABLE_API_DOCS` | expose `/api/docs` in production | false |
| `RICO_OCR_DAILY_LIMIT` | per-identity daily external-OCR cap | 20 |
| `RICO_TELEGRAM_GUEST_DAILY_LIMIT` | unbound Telegram daily AI allowance | 10 |
| `BACKEND_API_BASE_URL` | web build-time proxy origin | https://api.ricohunt.com |

## Credential rotation checklist (never print values)

| Provider | Rotate | Inject into | Verify old is dead |
|---|---|---|---|
| Neon | `DATABASE_URL` password | compose `DATABASE_URL` / secret store | `/ready` 503 with old; 200 with new |
| — | `JWT_SECRET` (≥32 chars) | compose `JWT_SECRET` | old tokens → 401 |
| — | `ADMIN_PASSWORD` | compose `ADMIN_*` | old admin login → 401 |
| Paddle | `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET` | compose `PADDLE_*` | webhook HMAC rejected with old |
| Stripe | revoke/delete (retired) | none | — |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` | compose `TELEGRAM_*` | webhook 403/503 with old |
| Jotform | `JOTFORM_API_KEY`, `JOTFORM_WEBHOOK_SECRET` | compose `JOTFORM_*` | webhook 503 with old |
| — | `RICO_CRON_SECRET` | compose + GH Actions | cron 403 with old |
| Render | `RENDER_API_KEY` | GH Actions `RENDER_API_KEY` | Render API 401 |
| OpenAI / DeepSeek | API keys | compose `OPENAI_*` / `DEEPSEEK_*` | provider 401 |
| HuggingFace | `HF_TOKEN` | compose `HF_TOKEN` | HF 401 |
| RapidAPI | `RAPIDAPI_KEY` | compose `RAPIDAPI_KEY` | search 401/403 |
| SMTP/Resend | `SMTP_PASSWORD` / `RESEND_API_KEY` | compose | email auth failure |
| LinkedIn / NaukriGulf | passwords | self-hosted runner secrets | login failure |

## Known accepted risks

- 2 pre-existing routing-drift integration failures (unenumerated file).
- Pipeline double-run only under a >1 h run + >1 h Redis outage (accepted).
- JWT lacks `iss`/`aud`/`jti` (documented MEDIUM; additive).
- Runtime Docker image retains `tests/`/`scripts/` (bloat, not secrets).
