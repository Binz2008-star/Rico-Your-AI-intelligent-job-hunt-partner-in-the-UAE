# Production Readiness

Operational documentation. **Updated 2026-08-16** — supersedes the earlier
Render-era status (the retired `rico-job-automation-api.onrender.com` host and
the stopped-Render notes no longer apply).

## Production URLs

- Frontend: `https://ricohunt.com`
- Backend: `https://api.ricohunt.com` (canonical, Railway; see
  `.github/workflows/deploy-production.yml`)
- Local/Docker: `docker-compose.prod.yml` exposes backend `:8000`, web `:3000`

## Launch status

```
PRODUCTION BLOCKED — EXTERNAL ACTIONS ONLY
```

The codebase is frozen, tested, and Docker-ready. All in-repo blockers are
closed. The remaining gate items are external platform actions — see
[`LAUNCH_STATUS.md`](../LAUNCH_STATUS.md) for the full snapshot and the exact
owner checklist:

1. Rotate/revoke production credentials (Neon, JWT_SECRET, admin, Paddle,
   Telegram, Jotform, cron secret, providers, SMTP; revoke the historical
   commit-`1882e8b9` RapidAPI/Gmail values if active).
2. Enable GitHub branch protection on `main` (required checks: QA Tests/pytest,
   QA Tests/postgres-integration, QA Tests/playwright, QA Tests/frontend,
   Workflow Security Guards, Test Enumeration Guard, Log Privacy Ratchet).
3. Confirm the Railway/production deploy gate (green-commit-only).
4. Record the first CI coverage baseline and tighten `--cov-fail-under` to
   `baseline − tolerance`.
5. Confirm the Neon connection ceiling against
   `replicas × DATABASE_POOL_MAXCONN + cron pool + migrate one-shot`.
6. Push to main / tag to build and push immutable Docker images, then set
   `${BACKEND_IMAGE}` / `${WEB_IMAGE}` in `docker-compose.prod.yml`.

## Runtime model

- **Docker is the canonical runtime.** Non-root containers, `/health` liveness
  (never restart-looped on a DB blip), `/ready` readiness (503 on DB-down in
  production), production docs gated off by default, strict startup schema
  check (`RICO_RUN_STARTUP_MIGRATIONS=false`), migrations via the explicit
  runner / `migrate` one-shot.
- **Secrets are runtime-only.** No plaintext secret files; `docker-compose.prod.yml`
  uses `${VAR:?required}` placeholders; `.dockerignore` excludes every
  credential artifact from images.
- **Bounded DB pool** (default max 5/process) with rollback-on-release,
  dead-connection discard, and statement timeout.
- **Scheduler:** exactly one web process per container, no in-process
  scheduler; scheduled jobs run via external cron guarded by the Redis
  distributed lock (fail-closed).

## Verification

See `LAUNCH_STATUS.md` → "Test evidence" and "Docker production model".
Backend 710 / frontend 992 / real-Postgres 186 (2 documented pre-existing
routing-drift failures, unenumerated). All CI guards pass; all 28 workflows
SHA-pinned.
