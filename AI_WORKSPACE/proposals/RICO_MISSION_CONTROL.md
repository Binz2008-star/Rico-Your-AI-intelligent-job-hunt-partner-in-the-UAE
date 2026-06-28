# Proposal: Rico Mission Control — Career Operating System

Status: proposal / PR plan (direction approved with "Mission as philosophy" revision)
Owner branch: `claude/rico-mission-control-proposal-a5bndk`
Source-of-truth issues: #746 (Command UX + funnel), #138 (cinematic redesign system),
#99 (Companion UX), #355 (Follow-up reminders/workers), #356 (Inbox Intelligence — design-only, later)

This is **not** a new redesign and **not** a one-shot rebuild. It is a small,
action-first first step that also commits to a product **identity**: Rico is a
**Career Operating System** that runs the user's *career mission*, not a chat box.
The first PR stays frontend-only and reuses existing APIs. The layered system
below is the North Star the PRs grow toward — it is explicitly *not* Phase-1 scope.

---

## 0. Product philosophy — "Mission", not "Dashboard"

Every Rico decision answers one question: **does this move the user closer to their
career mission?** If yes, surface it. If no, keep it out of the user's way.

This reframes the unit of work. Instead of `code → function → file → feature`, Rico's
unit of automation is:

```
Job → Application → Pipeline → Career → Mission → Career Lifecycle
```

Consequence for the codebase: the logged-in surface and its components adopt a
**Mission** vocabulary — not `Dashboard`:

```
MissionControl   (the page-level surface)
CurrentMission   (the 🎯 header: role · city · salary · progress)
MissionTodayCard (today's prioritized actions)
MissionFeed      (later: "12 new jobs — review?")
MissionTimeline  (later: today's events as a timeline, not chat)
MissionAction / MissionStatus / MissionAssistant (later)
```

The route stays `/dashboard` in Phase 1 (avoids breaking existing links and the
onboarding redirect); a `/mission` alias can be added later once the surface is proven.

---

## 1. North Star — Rico Career Operating System (target architecture)

This is the destination, captured so every PR can be checked against it. **None of
the lower layers ship in Phase 1.**

```
                 Rico Career Operating System
                 ┌─────────────────────────┐
                 │   CAREER MISSION (top)   │  ← role, salary, city, deadline, progress
                 │  "Land a better job"     │
                 └────────────┬─────────────┘
             ┌────────────────▼─────────────────┐
             │        Rico Orchestrator          │  ← decides which agent runs next
             └────────────────┬─────────────────┘
PROFILE LAYER     CV · Skills · Experience · Target Roles · Salary · Cities · Prefs
MEMORY LAYER      Saved jobs · Applications · Conversations · Recruiter history · Follow-ups · Docs
INTELLIGENCE      Job Matching · CV Optimization · ATS · Interview Coach · Cover Letter · Advisor · Market Intel
ACTION LAYER      Search · Save · Track · Follow-up · Prepare Interview · Notify
AUTOMATION        Daily Scan · Telegram · Email Digest · Reminder Engine · Opportunity Radar
AGENTS            Career Manager → Search · CV · ATS · Interview · Recruiter · Follow-up · Reminder · Analytics
TOOLS             Job APIs · Browser · PDF/Word · Email · Telegram · Calendar · Neon · Stripe · OpenAI · DeepSeek
GOVERNANCE        Permissions · Audit Logs · Rate Limits · AI Cost Control · PII · Consent · RBAC · Observability · Flags
```

What already exists in the repo (so we build *on* it, not beside it):

- **Profile / Memory:** `fetchProfile`, applications, saved searches, chat history.
- **Intelligence:** job matching + match reasons (#99), CV parsing/upload.
- **Action:** `src/agent/runtime.py` (idempotent dispatcher), `actions` router.
- **Automation:** `src/run_daily.py` (daily scan), Telegram router, `#355` reminders sweep.
- **Governance:** `src/rico_safety.py`, rate limits, approval mode, notification audience rules.

The orchestrator + multi-agent split is the long-term path — **not** invented now.

---

## 2. Phased rollout (UI-first, low-risk)

| Phase | Theme | What ships |
|------|-------|-----------|
| **1 — Mission Control surface (this PR plan)** | Action-first home | `/dashboard` → MissionControl: 🎯 Current Mission header, Today's Actions, pipeline summary, profile/CV readiness, Ask Rico. Frontend only, existing APIs. |
| 2 — Mission Feed | "Pull", not "ask" | Rico opens with "12 new jobs — review?" instead of an empty prompt. Reuses `getJobs`. |
| 3 — Mission Timeline | Events, not chat | Today's progress as a timeline (found 12, CV updated, follow-up sent, awaiting Amazon, interview tomorrow). |
| 4 — AI Workspace | Visible operations | Each mission step shows progress (Searching → Matching → Optimizing CV), Cursor-style. May need a job/operation status feed. |
| 5 — Operating System | Morning brief | "Good morning Roben. Today: 4 interviews, 17 new jobs, 2 follow-ups, 1 recruiter replied. Recommended mission: apply to Emirates." Backed by automation + orchestrator. |

Backend work (a real `Mission` model, orchestrator, agents, governance hardening)
is layered in only when a phase needs it — never ahead of the UI that uses it.

---

## 3. Which page becomes Mission Control: `/dashboard` or `/command`?

**`/dashboard`** (kept as the route; renamed to `MissionControl` in code).

- `/command` (`apps/web/app/command/page.tsx`, ~2,100 lines) **is** the chat surface
  and the target of #746's visible-state track — it stays the "Ask Rico" / conversation
  destination, reached from Mission Control.
- `/dashboard` already has the right shell: server component, `force-dynamic`,
  onboarding gate (redirect to `/onboarding` when `profile_exists === false`), and a
  sectioned content component. Today its "Next Best Actions" are **static placeholder
  cards** — turning them into real, mission-driven actions is the whole Phase-1 job.

---

## 4. Exact files to touch (first PR — 5 files, under the 6-file cap)

All frontend, all in `apps/web`. Existing `DashboardStats` and `ProfileReadinessCard`
are reused unchanged inside MissionControl.

| # | File | Change |
|---|------|--------|
| 1 | `apps/web/app/dashboard/page.tsx` | **Edit.** Render `<MissionControl />` instead of `<DashboardContent />`. Onboarding gate unchanged. |
| 2 | `apps/web/components/mission/MissionControl.tsx` | **New.** Page composition. Top→bottom: `CurrentMission` header (inline) → `MissionTodayCard` → `DashboardStats` (pipeline, reused) → readiness (`ProfileSummaryCard` + `ProfileReadinessCard`, reused) → Ask Rico CTA (inline). |
| 3 | `apps/web/components/mission/MissionTodayCard.tsx` | **New.** Today's prioritized actions from existing endpoints, with loading/empty/error states. |
| 4 | `apps/web/lib/mission/today.ts` | **New.** Pure, unit-testable: input = fetched data, output = ordered `MissionAction[]` (priority + label + href). No I/O. |
| 5 | `apps/web/lib/translations.ts` | **Edit.** `en`/`ar` keys for Current Mission, Today's Actions, Ask Rico. |

> The 🎯 Current Mission header and Ask Rico block live inline in `MissionControl` for
> Phase 1 to respect the 5-file cap; extract to `CurrentMissionHeader.tsx` /
> `MissionAssistantCard.tsx` in a follow-up once they grow. The old `DashboardContent.tsx`
> can be deleted in the same PR (it becomes dead) or kept one release as a thin re-export.

Reused without modification: `DashboardShell`, `DashboardStats`, `ProfileReadinessCard`,
`ProfileSummaryCard`, all of `lib/api.ts`.

---

## 5. Data sources already available (no new backend)

| Surface | Helper (`lib/api.ts`) | Endpoint | Fields |
|--------|----------------------|----------|--------|
| 🎯 Current Mission: role / city / salary | `fetchProfile()` | `GET /api/v1/rico/profile` | `target_roles[0]`, `preferred_cities[0]`, `salary_expectation_aed` |
| 🎯 Current Mission: progress | `fetchProfile()` + pipeline | `…/rico/profile`, `…/applications/stats` | proxy from `completeness_score` + pipeline activity |
| Today: drafts awaiting approval | `getApplicationQueue()` | `GET /api/v1/apply/queue` | pending `ApplicationDraft[]` |
| Today: follow-ups due | `getFollowUpReminders()` | `GET /api/v1/apply/follow-ups` | `ApplicationDraft[]` (`follow_up_at`) — #355 surface |
| Today: complete-profile nudge | `fetchProfile()` | `GET /api/v1/rico/profile` | `completeness_score`, missing fields |
| Today: review new matches | `getJobs(1,1,0)` | `GET /api/v1/jobs` | `total` |
| Pipeline summary | `getJobs` / `getApplications` / `getApplicationStats` / `getSettings` | (existing) | rendered by `DashboardStats` |
| Profile / CV readiness | `fetchProfile()` | `GET /api/v1/rico/profile` | rendered by `ProfileReadinessCard` |
| Ask Rico chips | — | `/command?q=…` deep-link (already supported) | — |

---

## 6. Missing APIs

**Phase 1: none required.** Every tile composes from existing endpoints, so the first
PR ships with zero backend change.

Honest gaps (data, not routes — handled by graceful degradation now, real backend later):

- **No `Mission` model yet.** `deadline` and a true `progress %` are not stored, so the
  🎯 header shows role/city/salary now and treats deadline + progress as **optional**
  (progress = a transparent proxy from `completeness_score` + pipeline activity, labelled
  as such — never a fake number). A real `missions` table + `GET/PUT /api/v1/mission` is
  the first backend item when Phase 2/3 needs it.
- **Follow-ups depend on the #355 cron** running in production to populate `follow_up_due`;
  until then that tile is simply empty (degrades, never errors).
- **Optional later:** `GET /api/v1/dashboard/today` (or `/mission/today`) aggregator to
  collapse the ~4 parallel client calls into one. Deferred — optimization, not a blocker.

---

## 7. First PR scope (under 6 files)

**Title:** `feat(mission): Mission Control Phase 1 — action-first career home`

**In scope:**
- `/dashboard` renders `MissionControl` (Mission-named components).
- 🎯 `CurrentMission` header from real profile data (role · city · salary · progress proxy).
- `MissionTodayCard`: prioritized actions, ordered by `lib/mission/today.ts`:
  drafts awaiting approval → follow-ups due → complete profile → review N new matches.
  Each row is one tap to a real destination (`/flow`, `/profile`, `/jobs`, `/command?q=…`).
- Ask Rico CTA → `/command` + 2–3 quick-prompt chips via `?q=`.
- i18n (en/ar); loading/empty/error states.

**Out of scope (constraints honoured):** no new backend route/workflow; no `Mission`
table yet; no new AI provider; no billing changes; no motion/animation system (#138);
no `/command` chat changes (#746 track); no Inbox Intelligence (#356, design-only);
no orchestrator/agents/governance work; no broad redesign (`DashboardShell` + theme unchanged).

**Files:** 5 (see §4).

---

## 8. Acceptance criteria

- [ ] Logged-in `/dashboard` renders **MissionControl** with the 🎯 Current Mission header
      and Today's Actions as the top two blocks; pipeline + profile/CV readiness below.
- [ ] Current Mission header uses **real profile data**; when role/salary/city are missing
      it shows a "set your mission" prompt, never invented values; progress is a labelled proxy.
- [ ] Today's actions are **derived from live data** (queue, follow-ups, profile, matches) —
      no hard-coded placeholder rows.
- [ ] Actions are prioritized deterministically by `lib/mission/today.ts` (unit-tested),
      and each row deep-links to a destination that performs the action.
- [ ] Caught-up state shows a clear non-empty message ("All clear — ask Rico to find new
      roles"), not a blank panel.
- [ ] Each feed fails independently: a 401/timeout/empty on one tile never blocks the rest
      (same per-feed pattern as `DashboardStats`).
- [ ] Ask Rico opens `/command`; quick-prompt chips pass a working `?q=` deep-link.
- [ ] Onboarding gate preserved (no profile → `/onboarding`).
- [ ] No new env vars, backend endpoints, billing, or provider changes.
- [ ] `npm run build` and `npm run lint` pass in `apps/web`.
- [ ] Mobile-friendly and accessible (keyboard-reachable rows, `aria-label`s) per #99.

---

## 9. Beyond PR 1 (context only)

- **PR 2:** Mission Feed ("12 new jobs — review?") on top of `getJobs`.
- **PR 3:** Mission Timeline (events, not chat) + `missions` table for deadline/progress.
- **PR 4:** AI Workspace operation states; richer follow-ups once #355 cron is live.
- **PR 5:** Morning brief + orchestrator; agent split (Search/CV/ATS/Interview/Recruiter/
  Follow-up/Reminder/Analytics) introduced one agent at a time behind feature flags.
- Governance (audit, cost control, PII, RBAC, observability) hardens alongside automation —
  not deferred to the end.
