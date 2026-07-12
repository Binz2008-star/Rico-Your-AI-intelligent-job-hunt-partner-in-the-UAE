# Handoff — Pre-launch access gate and waitlist intake

**Status:** implementation draft; not activated; not merged  
**Date:** 2026-07-11 (rebased onto `main` @ `241b85d` on 2026-07-12)  
**Owner decision:** approved for direct implementation with strict production isolation  
**Issue:** #966 · **PR:** #967  
**Branch:** `feat/pre-launch-gate`

> **Rebase reconciliation (2026-07-12):** brought current on `main` after #969/#975
> merged. Waitlist migration renumbered **037 → 039** (037 = `user_documents`
> content_hash, 038 = `cv_upload_artifacts` now occupy those slots). Owner
> account `robenedwan@gmail.com` added to `INTERNAL_ALLOWLIST_EMAILS` in
> `.env.example`. Env var stays `RICO_LAUNCH_MODE` (repo `RICO_*` convention) with
> **default `live`** — deliberately safe: merging cannot close production;
> activation is an explicit operator flip. See `AI_WORKSPACE/DECISIONS.md`.

## Why this exists

Rico is live while onboarding persistence remains PARTIAL. The owner approved a reversible
pre-launch mode that keeps the current product code intact but can temporarily limit public
access to a bilingual waitlist surface. The gate must protect both Vercel navigation and direct
FastAPI access; a frontend-only redirect is insufficient.

This handoff is the execution and activation source for #966. Update it whenever the gate,
activation requirements, smoke evidence, or rollback procedure changes.

## Binding decision

1. Introduce `RICO_LAUNCH_MODE=live|waitlist` on both frontend and backend.
2. Missing or invalid configuration resolves to `live`; merging code alone cannot close production.
3. In `live`, all existing behavior is preserved.
4. In `waitlist`:
   - `/` renders the Atelier EN/AR waitlist page;
   - public marketing/legal and auth-recovery pages remain reachable;
   - signup, public chat, CV upload/confirmation, and product APIs are blocked by FastAPI;
   - only server-side allowlisted emails may create an authenticated session and use the app;
   - `/login` remains available for internal users;
   - waitlist registration is consented, rate-limited, normalized, and idempotent per email.
5. The backend is authoritative. Next.js middleware is only the navigation/UX layer.
6. Production configuration and Neon are not changed by the PR.

## Repository corrections applied

The original proposal was not copied literally. Current repository evidence required these
corrections:

- auth cookie: `access_token`, not `rico_session`;
- frontend backend path: `/proxy/api/v1/...`;
- migration sequence: `039_create_waitlist.sql`, not `0011`;
- robots policy already lives in `apps/web/app/robots.ts` and already excludes private routes;
- internal access is derived from server environment (`INTERNAL_ALLOWLIST_EMAILS` plus
  `ADMIN_EMAIL`), never from a client-controlled email or invitation cookie;
- waitlist persistence lives in FastAPI/Neon, not a Next.js-only database path.

## Scope

### Runtime

- `src/services/launch_mode.py`
- `src/api/middleware/prelaunch_login.py`
- `src/api/routers/prelaunch.py`
- `src/api/routers/waitlist.py`
- `src/repositories/waitlist_repo.py`
- `src/schemas/waitlist.py`
- `src/api/app.py`
- `src/api/rate_limit.py`
- `migrations/039_create_waitlist.sql`
- `apps/web/lib/launch-mode.ts`
- `apps/web/lib/prelaunch-paths.ts`
- `apps/web/middleware.ts`
- `apps/web/app/page.tsx`
- `apps/web/components/home/HomePageClient.tsx`
- `apps/web/components/waitlist/*`
- `apps/web/app/_atelier/atelier-waitlist.css`

### Verification

- `tests/test_prelaunch_gate.py`
- `apps/web/__tests__/prelaunch-mode.test.tsx`

## Explicitly out of scope

- changing any production environment variable;
- applying migration 039 to production or preview Neon;
- auto-inviting users or sending confirmation/invitation emails;
- admin waitlist UI;
- invitation cookies;
- changing existing user roles or account records;
- #960, #962, #963;
- remaining authenticated-route guards;
- command i18n;
- workspace/dashboard implementation;
- #961 or any autonomous loop.

## Required CI and review gates

- [ ] focused backend tests pass;
- [ ] existing required pytest selection passes;
- [ ] frontend Vitest includes the new pre-launch tests without new failures;
- [ ] `apps/web` build passes;
- [ ] Vercel preview is READY;
- [ ] independent review confirms direct FastAPI and proxy policy match;
- [ ] changed files contain no unrelated runtime work;
- [ ] migration is reviewed as additive/idempotent;
- [ ] desktop EN, desktop AR/RTL, and mobile waitlist screenshots are attached;
- [ ] owner approves preview behavior before merge;
- [ ] PR remains draft until all blockers are closed.

## Staged activation runbook

Do not activate from the PR branch.

1. Merge only after CI, review, screenshots, and owner approval.
2. Keep `RICO_LAUNCH_MODE=live` or unset on both Vercel and Render.
3. Apply `migrations/039_create_waitlist.sql` to the approved Neon environment.
4. Verify the table, unique normalized-email constraint, and no existing-table mutation.
5. Configure the same `INTERNAL_ALLOWLIST_EMAILS` value on Vercel and Render.
6. In a non-production preview/staging environment, set `RICO_LAUNCH_MODE=waitlist` on both
   services and redeploy.
7. Smoke:
   - `/` shows EN/AR waitlist;
   - repeated email submission returns the same generic success and creates one row;
   - `/signup`, `/command`, `/onboarding`, and private pages redirect to `/`;
   - direct and proxied signup/public-chat/upload calls return 403;
   - non-allowlisted login returns 403 with no auth cookie;
   - allowlisted login succeeds and private app/API access works;
   - health, version, privacy, terms, password reset, and email verification remain reachable.
8. Record preview evidence in this handoff.
9. Production activation requires a separate explicit owner instruction.
10. Activate by setting `RICO_LAUNCH_MODE=waitlist` on both Render and Vercel, then redeploy and
    repeat the smoke matrix.

## Rollback

Primary rollback:

1. Set `RICO_LAUNCH_MODE=live` on both services.
2. Redeploy Render and Vercel.
3. Verify `/`, `/command`, signup, public chat, and normal authenticated routes.

Code rollback: revert the merge PR and redeploy.  
Database: no destructive rollback is required; preserve waitlist rows. Migration 039 is additive.

## Current evidence

- Main/base at branch creation: `9ceb87b1b6b4e112ffb5940b167408e8ef0cb16e`.
- Production configuration, Vercel, Render, and Neon have not been mutated.
- Automated CI has not yet completed; do not describe the branch as merge-ready.

---

## Continuity Block — 2026-07-12 (WRITER: Claude, sole writer on #967)

**Active goal:** one Pre-launch page on ricohunt.com = launch film + Atelier EN/AR + waitlist form + app/API gate + internal login for `robenedwan@gmail.com`.

**Branch/PR:** `feat/pre-launch-gate` / **PR #967** (NO parallel branch/PR). HEAD `2ca3d1f8`.

**Done this session (code, not activated):**
- Merged latest `main` into the branch (teaser gate, `/explainer/*` film, PR #1004 abs-path fix, recent app changes preserved).
- Unified `apps/web/middleware.ts` to a SINGLE gate: the `RICO_LAUNCH_MODE` backend-authoritative pre-launch middleware. Removed the `NEXT_PUBLIC_SITE_LIVE` teaser variant (no refs remain).
- `apps/web/lib/prelaunch-paths.ts`: allow `/explainer` + `/explainer/*` public during waitlist.
- `apps/web/components/waitlist/WaitlistLanding.tsx`: embedded the film in-page via `<iframe src="/explainer/">` (not only a separate route).
- Waitlist form unchanged → `POST /proxy/api/v1/waitlist/register`. Migration stays `039_create_waitlist.sql`.
- Kept all `apps/web/public/explainer/*`; dropped stray local files from the PR.

**PENDING verification (NOT run — token-limited session; browser/preview tools disconnected):**
`cd apps/web && npm run build` · `npm run test -- prelaunch` (Vitest `__tests__/prelaunch-mode.test.tsx`) · backend `python -m pytest tests/test_prelaunch_gate.py -q` · Vercel preview READY on `web-git-feat-pre-launch-gate-robens-projects.vercel.app` · EN/AR + RTL + desktop/mobile visual · film plays inside waitlist page · `/dashboard`,`/command` → `/` in waitlist mode · `/login` works · waitlist form success.

**Activation plan (owner decision required — DO NOT do yet):**
1. Neon: apply `migrations/039_create_waitlist.sql` (creates `waitlist`).
2. Render (backend): set `RICO_LAUNCH_MODE=waitlist`, `INTERNAL_ALLOWLIST_EMAILS=robenedwan@gmail.com` (+ `ADMIN_EMAIL`). Redeploy.
3. Vercel (frontend): set `RICO_LAUNCH_MODE=waitlist` (+ ensure `NEXT_PUBLIC_RICO_API`/backend base URL present). Redeploy `main` AFTER PR #967 merges.
4. Merge PR #967 → main. Smoke: `/` = waitlist+film, `/dashboard`→`/`, `/login` OK, register writes a row, owner email can enter.

**Rollback:** set `RICO_LAUNCH_MODE=live` (or unset) on Render+Vercel → instant full site. Default is `live`; merging alone cannot close production. Migration 039 is additive (a new table) — safe to leave.

**Risks:** (1) frontend gate is UX-only; backend `prelaunch_login`/`prelaunch/access` is the real authority — both env vars must be `waitlist`. (2) film iframe CTA/Skip target `/signup` which is blocked in waitlist → bounces to `/` (acceptable; primary CTA is the waitlist form). (3) verify `BACKEND_API_BASE_URL`/`NEXT_PUBLIC_RICO_API` set on Vercel so middleware's `/prelaunch/access` fetch resolves, else it fails-closed to `/`.
