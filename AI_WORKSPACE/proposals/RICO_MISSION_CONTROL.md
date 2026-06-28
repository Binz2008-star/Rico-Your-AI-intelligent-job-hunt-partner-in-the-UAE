# Proposal: Rico Mission Control Dashboard (Phase 1)

Status: proposal / PR plan
Owner branch: `claude/rico-mission-control-proposal-a5bndk`
Source-of-truth issues: #746 (Command UX + funnel), #138 (cinematic redesign system),
#99 (Companion UX), #355 (Follow-up reminders/workers), #356 (Inbox Intelligence — design-only, later)

This is **not** a new redesign. It is a small, action-first evolution of the page
that already exists, reusing the existing API surface. No new backend workflow,
no new AI provider, no billing changes, no motion system.

---

## Goal

Turn the **logged-in** experience from chat-first into action-first. When a
returning user lands, the first thing they see is *what to do today*, not an
empty chat prompt. Chat ("Ask Rico") stays one tap away.

Phase 1 surfaces exactly four things:

1. **Today actions** — a prioritized, data-driven to-do list.
2. **Pipeline summary** — scored opportunities / applications in flow / pacing.
3. **Profile / CV readiness** — completeness score + missing fields.
4. **Ask Rico entry point** — a prominent deep-link into `/command`.

---

## 1. Which page becomes Mission Control: `/dashboard` or `/command`?

**`/dashboard`.**

Rationale:

- `/command` (`apps/web/app/command/page.tsx`, ~2,100 lines) **is** the chat-first
  surface — message stream, streaming SSE, CV upload, job cards, permission
  cards. It is the live "Ask Rico" experience and the target of the separate
  `/command` visible-state track in **#746**. Repurposing it as a dashboard
  would collide with that work and with the live chat flow documented in
  `CLAUDE.md` (Public Chat Flow / CV Upload). It should *stay* the conversation
  surface and become Mission Control's "Ask Rico" destination.
- `/dashboard` (`apps/web/app/dashboard/page.tsx`) is already the right shell:
  server component, `force-dynamic`, onboarding-gated (redirects to
  `/onboarding` when `profile_exists === false`), and it already renders a
  sectioned `DashboardContent` (Mission header → Pipeline → "Next Best Actions"
  → Readiness → Momentum → Activity).
- The gap is that today's "Next Best Actions" are **static placeholder
  `StatusCard`s** (hard-coded links to `/command`, `/jobs`, `/settings`) — not
  driven by the user's real state. Making them real is the whole job. That is an
  evolution of one section, not a rebuild.

Net: keep both routes, change their roles only slightly —
`/dashboard` = Mission Control (action-first), `/command` = Ask Rico (chat).
The sidebar/links already point users between them.

---

## 2. Exact files to touch (first PR)

All frontend, all in `apps/web`. Five files, under the 6-file cap:

| # | File | Change |
|---|------|--------|
| 1 | `apps/web/components/DashboardContent.tsx` | **Edit.** Reorder so the new Today panel + Ask Rico card are the top sections; replace the static "Next Best Actions" `StatusCard` trio with `<TodayActionsCard />`. Keep `<DashboardStats />` (pipeline) and the Readiness section (`ProfileSummaryCard` + `ProfileReadinessCard`) as-is. |
| 2 | `apps/web/components/dashboard/TodayActionsCard.tsx` | **New.** Client component. Fetches the existing endpoints, builds a prioritized action list, renders rows with deep links. Loading / empty / error states. |
| 3 | `apps/web/lib/dashboard/today.ts` | **New.** Pure, unit-testable helper: takes the fetched data and returns an ordered `TodayAction[]` (priority + label + href). No I/O, so it can be tested without the network. |
| 4 | `apps/web/components/dashboard/AskRicoCard.tsx` | **New.** Prominent "Ask Rico" entry: links to `/command` plus 2–3 quick-prompt chips using the already-supported `?q=` deep-link (CommandPage reads `?prompt=`/`?q=`). |
| 5 | `apps/web/lib/translations.ts` | **Edit.** Add `en`/`ar` keys for the Today panel and Ask Rico copy (project i18n pattern via `useTranslation`). |

Reused without modification: `DashboardStats.tsx`, `ProfileReadinessCard.tsx`,
`ProfileSummaryCard.tsx`, `DashboardShell.tsx`, all of `lib/api.ts`, and the
`/dashboard` server page (onboarding gate stays).

---

## 3. Data sources already available (no new backend)

Every Phase-1 tile is assembled client-side from endpoints already wired into
`apps/web/lib/api.ts`:

| Tile | Helper (`lib/api.ts`) | Endpoint | Fields used |
|------|----------------------|----------|-------------|
| Today: follow-ups due | `getFollowUpReminders()` | `GET /api/v1/apply/follow-ups` | `ApplicationDraft[]` (`job_title`, `company`, `follow_up_at`) — the #355 reminder surface |
| Today: drafts awaiting approval | `getApplicationQueue()` | `GET /api/v1/apply/queue` | pending `ApplicationDraft[]` (`status === "pending"`) |
| Today: complete-profile nudge | `fetchProfile()` | `GET /api/v1/rico/profile` | `profile_exists`, `completeness_score`, missing fields / `target_roles` |
| Today: review new matches | `getJobs(1,1,0)` | `GET /api/v1/jobs` | `total` (scored opportunities) |
| Pipeline summary | `getJobs` / `getApplications` / `getApplicationStats` / `getSettings` | `…/jobs`, `…/applications`, `…/applications/stats`, `…/settings` | already rendered by `DashboardStats` |
| Profile / CV readiness | `fetchProfile()` | `GET /api/v1/rico/profile` | `completeness_score`, field breakdown (already rendered by `ProfileReadinessCard`) |
| Ask Rico | `fetchMe()` (name only, optional) | `GET /api/v1/me` | `name` for greeting; chips deep-link to `/command?q=…` |

These mirror the visible-state needs called out in #746 (CV/profile status,
latest search, tracked applications, next action) and the "one clear next
action" requirement of #99 — without backend changes.

---

## 4. Missing APIs

**None required for Phase 1.** All four tiles compose from existing endpoints.

Caveats (data freshness, not missing routes):

- `GET /api/v1/apply/follow-ups` only returns items once the **#355** reminders
  sweep (`POST /api/v1/pipeline/reminders`, cron) has transitioned applications
  to `follow_up_due`. If the cron is not yet scheduled in production, this tile
  is simply empty — it degrades gracefully, it does not error. (Scheduling the
  cron is #355's job, out of scope here.)
- Per-application `needs_follow_up` / `days_since_applied` flags exist on the
  applications payload (`applications_repo.get_all`) and the chat
  `application_status` shape, so a follow-up count can also be derived from
  `getApplications()` if we prefer not to depend on the queue endpoint.

**Optional future (NOT this PR):** a single `GET /api/v1/dashboard/today`
aggregator to collapse the client-side fan-out (currently ~4 parallel calls)
into one response. Defer until Phase 1 proves the layout; it is an optimization,
not a blocker.

---

## 5. First PR scope (under 6 files)

**Title:** `feat(dashboard): Mission Control Phase 1 — action-first dashboard`

**In scope:**

- Add `TodayActionsCard` driven by `getFollowUpReminders` + `getApplicationQueue`
  + `fetchProfile` + `getJobs`, ordered by `lib/dashboard/today.ts`.
- Priority order (highest first): drafts awaiting approval → follow-ups due →
  complete profile (when `completeness_score` below threshold) → review N new
  matches. Each row is a single tap with a real destination
  (`/flow`, `/profile`, `/jobs`, `/command?q=…`).
- Add `AskRicoCard` with a primary "Ask Rico" CTA → `/command` and 2–3
  quick-prompt chips via `?q=`.
- Reorder `DashboardContent` so Today + Ask Rico are the top two sections; keep
  `DashboardStats` (pipeline) and the existing Readiness section beneath.
- i18n keys (en/ar). Loading / empty / error states for the new card.

**Explicitly out of scope (per constraints):**

- No new backend route or workflow; no `dashboard/today` aggregator yet.
- No new AI provider; no billing/subscription changes.
- No motion/animation system (#138 cinematic layer stays untouched).
- No `/command` chat changes (that is the #746 visible-state track).
- No Inbox Intelligence (#356 is design-only, later).
- No broad redesign — `DashboardShell`, theme tokens, and other sections unchanged.

**Files:** `DashboardContent.tsx` (edit), `TodayActionsCard.tsx` (new),
`today.ts` (new), `AskRicoCard.tsx` (new), `translations.ts` (edit) = **5 files.**

---

## 6. Acceptance criteria

- [ ] Logged-in `/dashboard` renders **Today actions** and **Ask Rico** as the
      top two sections; pipeline summary and profile/CV readiness remain visible
      below.
- [ ] Today actions are **derived from live data** (follow-ups, pending drafts,
      profile completeness, job match count) — no hard-coded placeholder rows.
- [ ] Actions are prioritized deterministically by `lib/dashboard/today.ts`, and
      each row deep-links to a real destination that performs the action.
- [ ] When a user has nothing pending, the card shows a clear, non-empty empty
      state (e.g. "You're all caught up — ask Rico to find new roles") rather
      than a blank panel.
- [ ] Each data source fails independently: a 401/timeout/empty on one feed
      degrades that tile only and never blocks the rest of the dashboard
      (matches the existing `DashboardStats` per-feed pattern).
- [ ] "Ask Rico" opens `/command`; quick-prompt chips pass a working `?q=`
      deep-link that CommandPage consumes.
- [ ] Onboarding gate is preserved: users without a profile still redirect to
      `/onboarding`.
- [ ] No new env vars, no new backend endpoints, no billing or provider changes.
- [ ] `npm run build` and `npm run lint` pass in `apps/web`; `lib/dashboard/today.ts`
      has unit coverage for the prioritization order.
- [ ] Mobile-friendly and accessible (keyboard-reachable rows, `aria-label`s),
      consistent with #99's mobile/accessibility requirement.

---

## Phasing beyond PR 1 (context only — not this PR)

- **PR 2:** `GET /api/v1/dashboard/today` aggregator to replace client fan-out.
- **PR 3:** richer follow-up actions once #355 cron is live in production.
- **PR 4+:** match-explanation surfacing (#99) and `/command` visible-state cards
  (#746) — separate tracks, not folded into Mission Control.
