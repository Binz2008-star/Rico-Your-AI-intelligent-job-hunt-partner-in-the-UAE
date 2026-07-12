# Build spec — /flow (applications) → Atelier "Your pipeline." (2026-07-12)

Resumable spec so any agent can execute the `/flow` migration cleanly with a
fresh token budget. Off clean `main`, one PR, owner visual approval before merge.
Branch already created: `feat/atelier-applications-flow`.

## Context

- `/applications` is a `redirect("/flow")` — the real page is `app/flow/page.tsx`
  (~604 lines). The sidebar links to `/applications`.
- Reference: `apps/web/public/design-preview/en-applications-desktop.png` (+ `-mobile`,
  `ar-applications-*`). Shows: eyebrow `APPLICATIONS`, serif **"Your pipeline."**,
  subtitle "Every conversation Rico has started on your behalf.", top-right
  **BOARD / LIST** toggle + a **SAMPLE** toggle + a **DEMO ACTION** banner, then a
  Kanban with columns **SAVED · APPLIED · INTERVIEW · OFFER · CLOSED** (count
  badges) and cards (company, a score number, role, relative time).

## Reference reconciliation (honesty — no fake data)

- **Score per card:** the reference cards show 81/88/92… `Application` has NO
  score field (`title, company, location, status, applied_at, updated_at, notes,
  apply_url`). → OMIT the score (do not fabricate).
- **SAMPLE toggle + DEMO ACTION banner:** prototype chrome. → DROP (like the
  /settings "REQUIRES BACKEND" banner). Real data only.
- **Columns:** Rico's canonical stages are 4 (`STAGE_DEFS` in
  `lib/applicationStatus.ts`: lead · applied · interview · outcome) and the
  per-card status `<select>` uses the real `ApplicationStatus` enum. The
  reference's 5 columns (SAVED/APPLIED/INTERVIEW/OFFER/CLOSED) are a design
  choice. **Keep Rico's real `STAGE_DEFS` grouping as the source of truth**
  (never invent statuses); label columns with the reference vocabulary where the
  stage aligns. Do NOT split into 5 columns unless `STAGE_DEFS` is changed
  (out of scope — that's a backend/taxonomy change).

## Controls to PRESERVE (every one — no behavior loss)

From `app/flow/page.tsx`:
- Data: `getApplications(undefined,1,50)` + `getApplicationStats`; `total`,
  "showing first N" when `total > applications.length`.
- **List/Board toggle** (`viewMode`), default `board` per reference.
- **Stats grid** (7 cells, `STATUS_COUNT_ORDER`, `grouped` counts).
- **Board**: `KANBAN_COLS` from `STAGE_DEFS`; per-card title, company, apply_url
  ("View listing ↗"), `DateProvenance`, and the **status `<select>`** →
  `changeStatus` → `updateApplicationStatus(job_id,{status})` with OPTIMISTIC
  local update (revert on error). Keep the `sr-only` label per select (a11y).
- **List view**: card with title/company/location, `StatusBadge`,
  `isLeadWithNoUrl` warning, status select, apply link, notes (read lines
  454-604 for the rest before building).
- **"Track application" modal** (`showModal`) → `createManualApplication`
  (manual add). Preserve all fields + validation.
- Empty / loading / error states; `handleLogout`; i18n via all existing `flow*`
  translation keys; RTL (`isRTL`).

## Atelier target (apply the control-center model)

- Wrap in `WorkspaceShell` (Shell C) instead of `AppShell`; palette via
  `useWorkspaceTheme()`. Header: eyebrow `APPLICATIONS` + serif "Your pipeline."
  + hairline + subtitle "Every conversation Rico has started on your behalf."
- Reframe as **Rico's operational memory**, not a bare board: what Rico saved /
  applied to / is interviewing / closed, and (from real fields only) the
  provenance/date. Columns + cards in the Atelier grammar (corner-tick plates,
  Mono labels, Fraunces headings, one-sun-red accents, `WORKSPACE_THEME`).
- **"Discuss with Rico"** links (reuse the honest `RicoChatLink` pattern from
  #1002 once merged) ONLY where a real chat path exists. VERIFY per action
  before labelling — e.g. status changes: chat CAN act on applications via
  `agent/runtime.handle_action` (apply/save/skip). Confirm the intent→mutation
  path in `src/rico_chat_api.py` / `src/agent/` before any execution-claiming
  copy; otherwise "Discuss with Rico" + log a gap.

## Auth + shell

- Add `useRequireAuth` guard + neutral `role=status` loader (like /settings and
  /dashboard) so a guest is bounced to `/login?next=/flow` and no private request
  fires. (Current /flow uses AppShell's own gating — replicate the guard.)
- Reuse the `<main>` landmark auth-guard test convention; the `next/font` vitest
  mock is already on main.

## Verification checklist (same bar as #1000–#1002)

- Preserve list/board/manual-add/stats/status-mutations/i18n; no backend/auth/
  cookie/schema change.
- `npx vitest run` green (+ a focused test for any new `/command?q=` links and
  the status-select mutation call). `npm run build`, lint, typecheck clean.
- Temp preview route `app/zz-preview-flow` (NO leading underscore),
  `NEXT_PUBLIC_USE_MOCK=true` (`getApplications` honors USE_MOCK →
  `MOCK_APPLICATIONS`), Playwright `executablePath:/opt/pw-browsers/chromium`;
  capture EN/AR × light/dark × desktop/mobile × board+list; DELETE temp route
  before commit.
- Draft PR; owner visual approval before merge.

## Session status (2026-07-12)

- MERGED: #1000 (`/settings` reference composition), #1001 (`/settings` control
  center).
- DRAFT, awaiting owner review (do NOT merge): #1002
  (`feat/settings-ask-rico-honesty`) — "Ask Rico" → honest "Discuss with Rico"
  + capability gaps logged.
- NEXT: this `/flow` build, then `/upload`, then `/profile` shell swap. Deferred:
  #995 preview cookie.
