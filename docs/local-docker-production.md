# Docker Warm-Standby Readiness — Rico AI

> **Operating model: Cloud-primary + Docker warm standby**
>
> This document describes the prepared Docker standby path for Rico AI.
> The standby is for health validation and emergency readiness only.
> It does NOT replace, migrate, or cut over from the active Vercel/Render/Neon path.

---

## A. Current Active Path (authoritative)

| Component | Platform | How it deploys |
|---|---|---|
| **Frontend** | Vercel | `git push main` → Vercel auto-builds `apps/web` via `vercel.json` |
| **Backend** | Render | `git push main` → GitHub Actions triggers Render deploy hook (`deploy-render.yml`), polls `/version` until commit matches |
| **Database** | Neon (managed PostgreSQL) | `DATABASE_URL` set in Render dashboard, `sync: false` in `render.yaml` |
| **Redis** | Render Redis | `REDIS_URL` set in Render dashboard |
| **CI/CD** | GitHub Actions | `qa-tests.yml` (pytest + Playwright + vitest), `deploy-production.yml` (post-deploy verification) |

**This path remains active and authoritative. No changes in this PR affect it.**

---

## B. Prepared Standby Path (dormant)

| Component | Container | Built from |
|---|---|---|
| **Frontend** | `rico-web-standby` | `apps/web/Dockerfile.production` (multi-stage: build → runtime) |
| **Backend** | `rico-backend-standby` | `Dockerfile.backend.production` (multi-stage: builder → runtime) |
| **Redis** | `rico-redis-standby` | `redis:7-alpine` (with AOF persistence) |
| **Reverse proxy** | `rico-caddy-standby` | `caddy:2-alpine` (Caddyfile: `:80` → web + backend) |
| **RQ worker** | `rico-worker-standby` | Same as backend image, `profiles: ["worker"]` — **disabled by default** |
| **Database** | External | No PostgreSQL container. `DATABASE_URL` must be set in `.env.production` |

### Warm-standby safeguards

The following features are **disabled by default** in both `docker-compose.production.yml` (hardcoded env overrides) and `.env.production.example`:

| Feature | Env var | Value | Why |
|---|---|---|---|
| Auto-apply | `RICO_ENABLE_AUTO_APPLY` | `false` | No job applications from standby |
| Approval required | `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS` | `true` | Belt-and-suspenders on auto-apply |
| Scheduled searches | `RICO_ENABLE_SCHEDULED_SEARCHES` | `false` | No background search sweeps |
| Signup email alerts | `ENABLE_SIGNUP_EMAIL_NOTIFICATIONS` | `false` | No outbound emails on user signup |
| Learning | `RICO_ENABLE_LEARNING` | `false` | No ranking adaptation side effects |
| RQ worker | Docker Compose `profiles: ["worker"]` | Not started | No background task processing |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Empty (compose override) | No Telegram messages |
| Email (SMTP) | `EMAIL_USER`, `EMAIL_PASS`, `SMTP_USER`, `SMTP_PASSWORD` | Empty (compose override) | No outbound email |
| JotForm | `JOTFORM_API_KEY`, `JOTFORM_FORM_ID`, `JOTFORM_RICO_FORM_ID`, `JOTFORM_WEBHOOK_SECRET` | Empty (compose override) | No onboarding webhook integration |
| Paddle billing | `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET` | Empty (compose override) | No billing transactions |
| Telegram alerts | `RICO_ENABLE_USER_TELEGRAM_ALERTS`, `RICO_TELEGRAM_PUBLIC_ALERTS` | `false` (compose override) | No Telegram notification triggers |
| Email alerts | `RICO_ENABLE_EMAIL_ALERTS` | `false` (compose override) | No email notification triggers |
| Billing mode | `BILLING_MODE` | `manual` (compose override) | No automatic billing operations |

**The compose-level env overrides explicitly clear these variables to empty strings, taking precedence over `.env.production` values.** A misconfigured `.env.production` file cannot re-enable these features during routine validation.

### What the standby CAN do during routine validation

- Serve HTTP health checks (`/health`, `/ready`, `/version` — routed directly to backend by Caddy)
- Serve the Next.js frontend
- Serve API docs (`/proxy/api/docs`, `/proxy/api/redoc` — proxied through Next.js BFF)
- Accept authenticated API requests via the Next.js BFF proxy (`/proxy/*` → backend)
- Perform AI reasoning (if `DEEPSEEK_API_KEY` or `OPENAI_API_KEY` is set)

### What the standby CANNOT do during routine validation

- Send emails
- Send Telegram messages
- Process scheduled jobs
- Auto-apply to jobs
- Process RQ background tasks
- Connect to production Neon (unless explicitly configured)
- Receive production user traffic

---

## C. Future Activation Steps (NOT performed in this PR)

> ⚠️ **These steps are documented for future reference only.**
> **Do NOT perform any of these steps as part of this PR.**
> **Activation requires explicit owner approval.**

### C.1. Provision VPS

- Provision a VPS with at least 4 GB RAM, 2 vCPU, 40 GB SSD
- Install Docker Engine and Docker Compose
- Configure firewall: allow 80/443 inbound, restrict SSH

### C.2. Prepare the exact approved commit

```bash
git clone <repo-url> /opt/rico
cd /opt/rico
git checkout <exact-approved-commit-sha>
```

- Verify `git log -1 --oneline` matches the approved commit
- Set `GIT_COMMIT=<exact-approved-commit-sha>` in `.env.production`

### C.3. Database backup

- Take a full backup of production Neon before any standby connection
- Verify the backup can be restored to a test instance
- Document the backup location and timestamp

### C.4. Migration-state verification

- Compare migration files in the repo against applied migrations on Neon
- Run `python scripts/check_migration_drift.py` against the target database
- Resolve any drift before proceeding

### C.5. Configure secrets

- Create `.env.production` from `.env.production.example`
- Set `DATABASE_URL` to the production Neon connection string (only at this step — never during routine validation)
- Set `JWT_SECRET` to a new strong random value
- Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` to production admin credentials
- Set `COOKIE_SECURE=true`
- Set `CORS_ORIGINS` to the production domain
- Set `TELEGRAM_BOT_TOKEN`, `EMAIL_USER`, `EMAIL_PASS` only if the standby should take over these functions
- Set AI provider keys (`DEEPSEEK_API_KEY` or `OPENAI_API_KEY`)
- Set `GIT_COMMIT` to the exact approved commit SHA

### C.6. Build and validate

```bash
# Build and start the standby stack (without worker)
docker compose -f docker-compose.production.yml --env-file .env.production up --build -d

# Wait for health checks
docker compose -f docker-compose.production.yml ps

# Verify backend health
curl -s http://localhost/health | python3 -m json.tool
curl -s http://localhost/version | python3 -m json.tool

# Verify frontend
curl -s -o /dev/null -w "%{http_code}" http://localhost/

# Verify proxy pass-through (Next.js BFF /proxy/* → backend)
curl -s -o /dev/null -w "%{http_code}" http://localhost/proxy/api/v1/version
```

### C.7. Start the RQ worker (only if standby becomes active)

```bash
# Start worker — only after traffic switch, never during validation
docker compose -f docker-compose.production.yml --profile worker --env-file .env.production up -d worker
```

> **Only one worker/scheduler authority:** Ensure the Render backend is stopped or its worker is disabled before starting the standby worker. Both workers must never process the same Redis queue concurrently.

### C.8. Configure domain and switch traffic

- Update DNS A record to point to the VPS IP address
- Update `Caddyfile` to use the production domain (e.g., `ricohunt.com` instead of `:80`)
- Caddy will auto-provision TLS certificates via Let's Encrypt
- Monitor health checks during traffic transition

### C.9. Smoke validation after traffic switch

- Verify `/health` returns 200 with `status: ok`
- Verify `/version` shows the correct commit SHA
- Verify frontend loads at the production domain
- Verify proxy pass-through works (`/proxy/api/v1/version`)
- Test authenticated user flow (login, profile, chat)
- Monitor Sentry for errors

---

## D. Rollback Procedure

> If the standby activation needs to be reversed, the active cloud path is preserved and can be restored.

### D.1. Restore traffic to Vercel/Render

1. Update DNS A record back to the Vercel/Render IP (or CNAME to Vercel)
2. Stop the standby Docker stack:

   ```bash
   docker compose -f docker-compose.production.yml down
   ```

3. Verify Vercel frontend is serving at the production domain
4. Verify Render backend `/health` returns 200
5. Verify Render `/version` shows the correct commit

### D.2. Restore worker authority

1. Stop the standby RQ worker:

   ```bash
   docker compose -f docker-compose.production.yml --profile worker stop worker
   ```

2. Verify the Render backend worker is running (or restart it from Render dashboard)
3. Confirm only one worker is processing the Redis queue

### D.3. Post-rollback verification

- Run smoke tests against the restored Vercel/Render path
- Check Sentry for any errors during the transition
- Verify Neon database integrity (no orphaned writes from standby)
- Document the incident and timeline

---

## E. Local Validation (routine, non-production)

For routine validation of the standby artifacts, use a staging or local database:

### E.1. Using local PostgreSQL (from dev docker-compose)

```bash
# Start the dev PostgreSQL and Redis
docker compose up -d postgres redis

# Copy .env.production.example to .env.production
cp .env.production.example .env.production

# Start the standby stack (without worker)
docker compose -f docker-compose.production.yml --env-file .env.production up --build
```

### E.2. Using a staging Neon branch

1. Create a staging branch in Neon
2. Set `DATABASE_URL` in `.env.production` to the staging branch connection string
3. Start the standby stack as above

### E.3. Health validation

```bash
# Backend health (Caddy routes /health directly to backend)
python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:80/health').read().decode())"

# Backend readiness
python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:80/ready').read().decode())"

# Backend version
python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:80/version').read().decode())"

# Frontend
python3 -c "import urllib.request; r=urllib.request.urlopen('http://localhost:80/'); print(r.status, r.reason)"

# API proxy pass-through (Next.js BFF /proxy/* → backend)
python3 -c "import urllib.request; r=urllib.request.urlopen('http://localhost:80/proxy/api/v1/version'); print(r.status, r.read().decode())"
```

### E.4. Verify safeguards are active

```bash
# Check that auto-apply is disabled
docker exec rico-backend-standby python -c "import os; print('AUTO_APPLY:', os.getenv('RICO_ENABLE_AUTO_APPLY'))"

# Check that scheduled searches are disabled
docker exec rico-backend-standby python -c "import os; print('SCHEDULED:', os.getenv('RICO_ENABLE_SCHEDULED_SEARCHES'))"

# Check that email notifications are disabled
docker exec rico-backend-standby python -c "import os; print('SIGNUP_EMAIL:', os.getenv('ENABLE_SIGNUP_EMAIL_NOTIFICATIONS'))"

# Verify worker is NOT running
docker ps --filter name=rico-worker-standby --format "{{.Names}} {{.Status}}"
# Expected: no output (worker container does not exist)
```

---

## F. Files in this PR

| File | Type | Purpose |
|---|---|---|
| `Dockerfile.backend.production` | New | Multi-stage production backend image (Python stdlib healthcheck) |
| `apps/web/Dockerfile.production` | New | Multi-stage production frontend image (build-time `BACKEND_API_BASE_URL`, Node stdlib healthcheck) |
| `docker-compose.production.yml` | New | Warm-standby compose stack with safeguards, `mem_limit`/`cpus`, explicit side-effect env overrides |
| `Caddyfile` | New | Reverse proxy: `/health`, `/ready`, `/version` → backend; all other traffic → Next.js (preserves `/proxy/*` BFF boundary) |
| `.env.production.example` | New | Environment template with production-safe defaults (`COOKIE_SECURE=true`, `ALLOW_ENV_AUTH_FALLBACK=false`, `host.docker.internal` DATABASE_URL) |
| `.github/workflows/docker-ci.yml` | New | Additive CI validation: disposable Postgres, blocking health checks, `/proxy/*` smoke, no deploy, no push |
| `docs/local-docker-production.md` | New | This document |
| `AI_WORKSPACE/TASKS.md` | Modified | Task entry for Docker warm-standby readiness |
| `AI_WORKSPACE/DECISIONS.md` | Modified | Architecture decision DEC-20260727-001 |

### Files NOT modified

- `render.yaml` — unchanged
- `apps/web/vercel.json` — unchanged
- `apps/web/next.config.js` — unchanged (standalone output not enabled; frontend image is larger but functional)
- `docker-compose.yml` — unchanged (local dev)
- `Dockerfile.backend` — unchanged (local dev)
- `apps/web/Dockerfile` — unchanged (local dev)
- `docs/local-docker.md` — unchanged (local dev docs)
- `.dockerignore` — unchanged
- `apps/web/.dockerignore` — unchanged
- `.env.example` — unchanged
- All `.github/workflows/*.yml` — unchanged (except new `docker-ci.yml`)
- All `src/**/*.py` — unchanged
- All `migrations/*.sql` — unchanged
