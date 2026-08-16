# Rico — Launch Status

> **Authoritative "where we are" snapshot.** Updated 2026-08-16 by the CTO
> engineering review after Phases 1–3 + launch-blocker closure + Docker
> production hardening. This supersedes the older headers in
> `AI_WORKSPACE/CURRENT_STATE.md` for launch-state purposes.

## Verdict

```
PRODUCTION BLOCKED — EXTERNAL ACTIONS ONLY
```

The codebase is **code-frozen**, fully tested, secret-free, and Docker-ready.
Every remaining launch item requires access to external platforms (credential
rotation, GitHub branch protection, Railway deploy gating, first CI coverage
baseline, Neon capacity confirmation, first registry push). There are **no
unexplained code or test blockers**.

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

## EXTERNAL LAUNCH BLOCKERS (owner actions — not done)

1. **Rotate all credentials** (Neon, JWT_SECRET, ADMIN, Paddle, Stripe-revoke,
   Telegram, Jotform, RICO_CRON_SECRET, Render, OpenAI, DeepSeek, HuggingFace,
   RapidAPI, SMTP/Resend, LinkedIn, NaukriGulf). See
   `LAUNCH_STATUS.md` → "Credential rotation checklist" below.
2. **Revoke historical credentials** from commit `1882e8b9` if still active:
   `RAPIDAPI_KEY`, `EMAIL_USER` (Gmail app password), `EMAIL_PASS`.
3. **Enable GitHub branch protection** on `main` requiring: `QA Tests /
   pytest`, `QA Tests / postgres-integration`, `QA Tests / playwright`,
   `QA Tests / frontend`, `Workflow Security Guards`, `Test Enumeration
   Guard`, `Log Privacy Ratchet`.
4. **Confirm the Railway/production deploy gate** (green-commit-only).
5. **First CI coverage run** → record baseline → set `--cov-fail-under` to
   `baseline − tolerance`.
6. **Confirm the Neon connection ceiling** against
   `replicas × DATABASE_POOL_MAXCONN (5) + cron pool (5) + migrate (1)`.
7. **Push to main / tag** → `docker-build.yml` pushes immutable images to
   GHCR → set `${BACKEND_IMAGE}` / `${WEB_IMAGE}` in `docker-compose.prod.yml`.

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
