---
name: deploy-rico
description: Read-only deployment verification for Rico. Check, verify, confirm, status, health, stale, deployed, commit, Render, Vercel, production. Use when asked to check if Rico is deployed, confirm the backend is live, verify Render is up to date, or check production health.
---

# deploy-rico

Read-only deployment verification for Rico Hunt. Checks whether the Render backend and Vercel frontend match `origin/main`, reports health status, and prints safe next steps. **Never deploys. Never changes env vars. Never touches Neon, Stripe, JotForm, or any production DB.**

The driver is `.claude/skills/deploy-rico/check.sh`.

---

## What it checks

| Check | Endpoint | Purpose |
|---|---|---|
| GitHub commit | `git fetch origin main` | Source of truth for expected commit |
| Render `/version` | `rico-job-automation-api.onrender.com/version` | Deployed commit, env, app name |
| Render `/health` | `rico-job-automation-api.onrender.com/health` | Backend liveness |
| Vercel proxy | `ricohunt.com/proxy/health` | Frontend → backend proxy rewrite working |
| Vercel root | `ricohunt.com/` | Frontend itself is up |

---

## Run (agent path)

```bash
bash .claude/skills/deploy-rico/check.sh
```

Machine-readable JSON output:

```bash
bash .claude/skills/deploy-rico/check.sh --json
```

Exit codes: `0` = all checks passed and Render is current. `1` = stale, unhealthy, or unreachable.

---

## Interpreting output

**`STATUS: ✓  All checks passed`** — Render is deployed from `origin/main` and health endpoints are green.

**`STATUS: ⚠  Render backend is stale`** — The commit Render is running does not match `origin/main`. The script prints safe next steps: open the Render dashboard and trigger a manual deploy. Do not redeploy from this script.

**`STATUS: ⚠  One or more checks did not pass`** — A health endpoint returned non-200 or no response. Possible causes:
- Render service is sleeping (free tier spins down). Wait ~30s and re-run.
- Network policy in the execution environment blocks outbound to Render/Vercel. This is expected in isolated CI containers — run from a machine with public internet access.
- Production outage.

---

## Sample output

```
═══════════════════════════════════════════════════
  Rico Deployment Verification
  2026-06-06 22:49:30 UTC
═══════════════════════════════════════════════════

── Render backend (https://rico-job-automation-api.onrender.com) ──
[  OK  ] GET /version  →  app=ricohunt  env=production  commit=e3fcfb7  deployed_at=2026-06-06T21:00:00Z
[  OK  ] GET /health   →  HTTP 200  status=ok

── Vercel frontend (https://ricohunt.com) ──
[  OK  ] GET /proxy/health  →  HTTP 200  status=ok
[  OK  ] GET /           →  HTTP 200

── Commit comparison ──
[ INFO ] origin/main      →  e3fcfb7
[ INFO ] Render deployed  →  e3fcfb7
[  OK  ] Render is up to date with origin/main (e3fcfb7)

═══════════════════════════════════════════════════
  STATUS: ✓  All checks passed
═══════════════════════════════════════════════════
```

---

## Gotchas

- **Render free tier sleeps** after 15 min of inactivity. The first request may time out or return a cold-start error. Wait 30s and re-run — if health comes back green, the service is fine.
- **Network policy in isolated containers** (this execution environment) blocks outbound to Render and Vercel. The script will show WARN/FAIL for all remote checks. Run from a local machine or a CI runner with public internet access for real results.
- **`/version` `commit` field is `"unknown"`** when Render deployed without a `COMMIT_SHA` env var set. This is a Render config issue, not a code issue. The health check is still valid.
- **`/proxy/health` returns 403 or 404** when the Vercel project env `NEXT_PUBLIC_RICO_API` is not set or the proxy rewrite is misconfigured. Check `apps/web/next.config.js` and Vercel project settings.

---

## Safety constraints

This skill is **read-only**. It will never:

- Run `git push`, `git merge`, or any write operation.
- Call any Render deploy API or webhook.
- Read or write `DATABASE_URL`, `JWT_SECRET`, or any secret env var.
- Connect to Neon, Stripe, JotForm, Telegram, or any external service other than the three HTTP GETs above.
- Modify any file outside `/tmp`.

To deploy: push to `main` and use the Render dashboard or Render CLI. Get approval first.
