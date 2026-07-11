# Handoff — Onboarding restoration + Atelier migration (MERGED — production deploy confirmed; browser smoke PARTIAL: persistence gap)

> **For the next Claude session (continuing on a different account).** Pick up from
> branch `claude/onboarding-restore-atelier` (based on `origin/main` @ `c43bedc`). This
> handoff + `DEC-20260710-004` are the source of truth. Owner already APPROVED Option 1
> (re-enable + migrate onboarding). No onboarding runtime code has been written yet —
> only investigation + the DEC + this handoff.

## ✅ Merge + deployment record (2026-07-10)

The work shipped as **PR #955** (`feat(onboarding): restore /onboarding + Atelier migration
+ status-driven routing`), **squash-merged into `main`** by the owner at `2026-07-10T22:31:08Z`.

- **Merge SHA (verified new `main` HEAD): `3cf539841fd47c7aad7458f8c66bd80aa31ee018`.**
  (Recorded from the merged HEAD of `main`, not a pre-merge test-merge ref.)
- **Pre-merge gates (green on head `ccf74a00b6aca78ddf8dfc5e4333aa32bac11821`):** GitHub QA
  Tests, pytest, frontend/vitest (337 passing), Playwright, Vercel Preview READY, mergeable
  = clean, zero unresolved review threads.
- **Production deployments (both confirmed via CI on `3cf5398`):**
  - Frontend — Vercel "Deploy to Production": **success**.
  - Backend — Render "Deploy Render Backend" (`deploy-render.yml`): **success**. This job
    triggers the deploy hook and **blocks until `/version.commit` matches the pushed SHA**,
    so success confirms the backend at `3cf5398` is live and carries the new read-only
    `GET /api/v1/onboarding/status` endpoint + strict reader.

### Production verification — PARTIAL: persistence gap (owner-run, verified account, 2026-07-11)

Deployments are confirmed live via CI. **Correction to the 2026-07-10 note:** a verified
production test account **was successfully created and used** — email verification worked and
is expected behavior, so it is **not** the reason for PARTIAL. The remaining PARTIAL is due to
an **onboarding persistence gap**, not account availability. (All production checks are
owner-run: the CI/agent container cannot reach production — `403 CONNECT` to
`rico-job-automation-api.onrender.com` / `ricohunt.com`.)

**PASS (owner-verified in production, 2026-07-11)**
- registration and email verification
- authenticated **incomplete** user → `/onboarding`
- the three onboarding steps render and progress
- **Skip for now** → `/command`, and **Skip does not persist completion** (approved contract —
  no `onboarding_skipped` / schema change)
- real CV upload, parsing, and extracted-data review
- unauthenticated `/onboarding` → `/signup?next=%2Fonboarding`; completed user → `/command`
- EN / AR / RTL / mobile; adjacent public pages; no observed cross-user data leakage; basic
  performance acceptable

**Remaining gap (why status stays PARTIAL)**
- the confirmed onboarding CV is **not persisted to My Files**
- extracted **years / current role / target roles** are **not fully hydrated** into the profile
- **final submit persistence** and the **logout → login completion** smoke **cannot be closed**
  until the persistence gap is fixed

Tracked as **#963** (onboarding CV persistence + extracted-field hydration). Related recorded
follow-ups: **#960** (exact-duplicate protection + idempotency) and **#962** (safe consumption
of the login return path — the `next` gap surfaced by #958).

**Backend `503` read-failure contract:** verified via **automated tests only**
(`tests/test_onboarding_status_endpoint.py`, `tests/test_onboarding_repo_readonly.py`); never
tested by disrupting production.

**Findings (from the 2026-07-10 smoke) — current disposition:**
1. `/onboarding` redirect ~2–3s — **PASS** with a low-priority latency note.
2. `/settings` rendered the app shell for a guest — **RESOLVED via PR #958** (shared auth
   guard; guest → `/login?next=%2Fsettings`, no private API), **production-verified 2026-07-11**.
3. `/command` public access — **intentional**, unchanged.
4. Initial Rico message stays **English while the Arabic UI is active** — **confirmed i18n bug,
   still open** (out of scope here; not addressed in #958).
5. `/profile` guest connection error — **RESOLVED via PR #958** (guest → `/login?next=%2Fprofile`,
   no private request fired), **production-verified 2026-07-11**.

**Next (binding order — do not skip to #963):**
1. First implement the **smallest #960** exact-CV-duplicate / idempotency foundation
   (server-side dedupe, atomic idempotency, quota + primary-CV invariants; no onboarding
   wiring). — `TASK-20260711-002`.
2. Then **#963** onboarding CV persistence + extracted-field hydration, wired on top of #960.
   — `TASK-20260711-003`.
3. Then an **owner production smoke** of final-submit persistence + logout→login completion
   with a verified account.
4. **Only then** mark onboarding status **PARTIAL → VERIFIED**.

`#962` (safe consumption of the login return path — `TASK-20260711-004`) is a **separate,
later** auth-UX increment, **not** part of this persistence work. **Do not start the
workspace/dashboard migration** until onboarding is fully verified.

## ⚠️ Evidence correction (2026-07-10) — read before using the "completion signal" notes below

The original evidence in this handoff called `ProfileResponse.profile_exists` the
"canonical completion signal." **That is wrong.** The rest of this file is kept verbatim
for traceability, but where it conflicts with this correction, **this correction wins.**
See the matching correction block in `DEC-20260710-004`.

- **`profile_exists` = career data exists; it does NOT mean onboarding is complete.**
  A partial profile, a merged-guest profile, one skill, one target role, or CV evidence
  all make it `True`. Do not route solely on it (evidence #2, #4, plan step #4 below are
  corrected by this note).
- **Persisted onboarding status is the primary completion signal** —
  `rico_onboarding_states` (`pending` / `in_progress` / `completed`) via
  `get_onboarding_state` / `is_onboarding_complete` / `set_onboarding_status`.
- **The backend minimum-profile gate is the canonical readiness evaluation** —
  `src/services/profile_context_resolver.py::evaluate_minimum_profile`. `POST
  /api/v1/onboarding/submit` already runs it and persists `completed` / `in_progress`.
- **No frontend duplication of `evaluate_minimum_profile`.** Next.js must NOT re-implement
  completion rules; it reads them from the backend.
- **Exposed signal:** `GET /api/v1/onboarding/status` (read-only, authenticated) returns
  `{status, complete, source, missing_fields, profile_exists, profile_completeness}`.
  Frontend routing: after login/submit and on direct `/onboarding` visits, call this
  endpoint and route `complete=true → /command`, `complete=false → /onboarding`. Users
  with no `rico_onboarding_states` row resolve via the gate with `source:"derived_legacy"`
  (a GET never backfills). On a status-request failure, show a recoverable UI
  (Retry / Continue to Rico) — no redirect loop, no false completion claim.
- **Filename correction:** the redirect line is in **`apps/web/next.config.js`** (this
  handoff and the DEC originally wrote `next.config` / `next.config.mjs`). It is line ~81:
  `{ source: "/onboarding", destination: "/command", permanent: false }`.
- **Delivery (this branch/PR):** shipped as ONE focused PR on
  `claude/onboarding-completion-signal-j8qmxz` (branched from `main` @ `c43bedc`, which
  already carries the Atelier token/island layer). Contents: this DEC/handoff correction,
  the read-only `GET /api/v1/onboarding/status` endpoint + backend tests, the frontend
  `fetchOnboardingStatus` client + typed schema, the `/onboarding` Atelier migration
  (`app/_atelier/atelier-onboarding.css` + rewritten `app/onboarding/page.tsx`), the
  removed `/onboarding → /command` redirect in `apps/web/next.config.js`, post-login
  routing on the completion signal, and frontend tests. No completion logic is duplicated
  in Next.js — the UI reads `/onboarding/status`.

## Overall design-migration status (approved `/design-preview` Atelier direction)

| Phase | Status |
|---|---|
| Landing | ✅ done (pre-existing) |
| **Auth** (`/login`,`/signup`,`/forgot-password`,`/reset-password`,`/verify-email`) | ✅ **merged (PR #948, `be312e8`) + production-verified** |
| **Support/contact + Legal** (`/faq`,`/contact`; legal already Atelier) | ✅ **merged (PR #949, `58f46632`) + production-verified** |
| Auth docs bookkeeping | ✅ merged (PR #950, `c43bedc`) |
| **Onboarding** | 🔶 **IN PROGRESS — this handoff** |
| Workspace shell → Dashboard → Profile → Settings → Applications/Flow → Upload CV → Subscription → Command/Chat (last) | ⏳ not started (do NOT start workspace until onboarding PR merged + prod-verified) |

Established Atelier pattern (reuse it): scoped `.atelier` island under `app/_atelier/atelier-tokens.css`
+ per-surface CSS (`atelier-auth.css`, `atelier-support.css`). Shipped examples: `/terms`, `/privacy`,
`/faq`, `/contact` use `.atelier atl-doc`; auth uses `components/auth/AtelierAuthShell.tsx`. Palette:
paper `#f2ece0` / ink `#14110d` / sun-red `#cf3d17`; serif display (Georgia fallback), mono labels.
Verified Atelier dark = `data-atl-theme="dark"` (existing night palette — do not invent new dark colors).

## Owner decision (DEC-20260710-004, accepted)

Option 1 — re-enable + migrate `/onboarding`. Full required flow + rules are in the DEC. Key points:
- Remove **only** the `/onboarding → /command` redirect (`apps/web/next.config`, currently line ~81). Keep every other deprecated-route redirect.
- Gate routing on onboarding completion: incomplete → `/onboarding`; complete → `/command`; after finish → `/command`; "Skip for now" → `/command` (no false completion); completed users never forced back through onboarding.
- Do NOT redesign `/command`. Do NOT change backend APIs / Neon schema / billing / provider routing.

## Repository evidence gathered (verified this session)

1. **Redirect location:** `apps/web/next.config` (mjs) `async redirects()` array, line ~81:
   `{ source: "/onboarding", destination: "/command", permanent: false }`. Server-side 307 → page is unreachable. Remove ONLY this line. (Siblings `/dashboard`,`/jobs`,`/signals`,`/archive`,`/saved-searches`,`/orchestrate` stay.)
2. **Canonical completion signal:** `GET /api/v1/rico/profile` → `ProfileResponse.profile_exists: boolean` (`apps/web/lib/api.ts:237`, fetch at `:264`). **This is the existing signal — use it. Do NOT invent a new flag/schema.**
3. **`/api/v1/me` has NO onboarding flag:** `MeResponse` = `{ email, role, authenticated, guest?, name? }` (`api.ts:178`). So completion must be read from `getProfile()`/`profile_exists`, not `/me`.
4. **Existing onboarding page** (`apps/web/app/onboarding/page.tsx`, 466 lines, dark/Nocturne) already implements the REAL flow — preserve its behavior, restyle to Atelier:
   - Auth guard: `fetchMe()` → if `!authenticated` → `router.replace(buildAuthHref("/signup","/onboarding"))`.
   - Upload: `uploadCV(file)`; accepted types = pdf/doc/docx/jpeg/png/webp; **non-CV rejection** = `res.status === "classified" && res.document_type !== "cv"` → error `onboardingErrNotCv`; 413 → `cmdCvTooLarge`; auth failure → `router.replace(loginHref)`.
   - States: `PageState = upload | parsing | form | submitting | done | error`; `StepIndicator` (Upload → Complete → Ready).
   - Form: prefill `skills` from parsed CV; fields `target_roles, preferred_cities, salary_expectation_aed, years_experience, skills` (list/number parsing preserved).
   - Submit: `submitOnboarding(payload)` → `done`; failure keeps `form` state + error (**must not show success on failure**).
5. **Misleading destinations to fix (3 usages in onboarding/page.tsx):** `/dashboard?skip=1` at lines ~343 (have-profile link), ~414 (Skip for now), ~434 (CompletionCard onGo). Per DEC → route these to **`/command`**. (`/dashboard` itself redirects to `/command`; `?skip=1` falsely implies completion.)
6. **Post-signup routing today:** `components/auth/SignupForm.tsx` does `router.push('/onboarding')` on the no-verification path (currently bounces to `/command` via the redirect). After removing the redirect this reaches onboarding. Verify the verification→login return path (`buildAuthHref` / `lib/redirect.ts`) preserves intended return to `/onboarding`.
7. **Guest→auth merge:** check how `public_user_id_to_merge` (used in `login()`/`register()`) affects `profile_exists` — ensure a merged guest with a complete profile is treated as complete.

## Still to verify before/while coding
- Where the **post-login/post-verify redirect** is decided (login success handler, `lib/redirect.ts`, `buildAuthHref`) so incomplete→`/onboarding` vs complete→`/command` is enforced at the right layer (login flow and/or an onboarding-page guard that bounces already-complete users to `/command`).
- Whether any middleware or layout also gates these routes.
- Confirm `submitOnboarding` persistence makes `profile_exists` true on next `getProfile()` (so refresh/return skips onboarding).

## Implementation plan (one focused PR)
1. `next.config`: remove ONLY the `/onboarding` redirect line.
2. New `apps/web/app/_atelier/atelier-onboarding.css` (scoped `.atelier`) OR reuse `atl-doc` + a small onboarding CSS: stepper, dropzone, parsed-CV plate, fields, primary/skip actions, states — paper/ink/sun-red.
3. Rewrite `apps/web/app/onboarding/page.tsx` to the Atelier island, **preserving all behavior** in evidence #4; swap the 3 `/dashboard?skip=1` → `/command`; completion + skip → `/command`.
4. Add an already-complete guard: on mount, if `getProfile().profile_exists` → `router.replace('/command')` (so completed users aren't forced through onboarding). Confirm this matches how login routes users too.
5. Ensure the incomplete→`/onboarding` / complete→`/command` decision is enforced in the login/verify success path (wherever the post-auth redirect lives).
6. EN/AR + RTL via `useLanguage`; keep translation keys (`onboarding*`) — add Atelier ones as needed.

## Required tests (from owner)
- unauth user cannot access onboarding (redirect to signup/login)
- authed **incomplete** user reaches onboarding
- authed **completed** user reaches `/command` (not forced through onboarding)
- verification-required signup journey reaches onboarding after login
- valid CV upload; non-CV rejection; upload failure
- profile submit success; **submit failure does NOT show success**
- refresh preserves persisted completion behavior
- completion and skip route correctly (both → `/command`; skip does not claim completion)
- EN/AR, RTL, desktop, mobile, keyboard, no overflow, no console errors

Test infra: Vitest (`apps/web`, currently 320 passing), Playwright (chromium at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`; **cannot reach ricohunt.com from container** — smoke prod via `curl` cache-busted `?cb=$ts`). Gates: `npm run build` + `npx vitest run` must be green.

## Delivery (owner instructions)
One focused Onboarding PR (restoration + Atelier migration) including the tied DEC-20260710-004 + AI_WORKSPACE updates. Draft PR → wait required CI (frontend/pytest/playwright) → merge only when green + no blocking review → sync main → delete branch → verify Vercel production on merge SHA → smoke `/onboarding` + the routing flow. Then continue to Workspace phase.

## Git state at handoff
- Branch `claude/onboarding-restore-atelier` @ `origin/main` (`c43bedc`). **Uncommitted at handoff:** this handoff + the `DEC-20260710-004` entry in `AI_WORKSPACE/DECISIONS.md` (docs only). No onboarding runtime changes yet. Committed + pushed so the next session can resume from origin.
- All prior phase branches deleted; backup deleted; no other open PRs from this work.
