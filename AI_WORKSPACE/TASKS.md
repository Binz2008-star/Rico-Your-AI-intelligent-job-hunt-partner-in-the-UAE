# Tasks

Use this file as the shared task ledger. Each task must be small enough to review in one PR.

## Status values

- `proposed`
- `scoped`
- `in_progress`
- `blocked`
- `review`
- `verified`
- `done`

## Task template

```md
### TASK-YYYYMMDD-001 — <title>

Status: proposed
Owner: <human/model>
Branch: <branch-name>
Issue/PR: <link or number>

#### Objective
<objective only>

#### Context
- Relevant files:
- Relevant docs:
- Existing behavior:

#### Constraints
- Do not touch:
- No migrations unless explicitly required:
- Keep scope limited to:

#### Acceptance criteria
- [ ]
- [ ]
- [ ]

#### Required verification
- [ ] Unit tests:
- [ ] Integration tests:
- [ ] Frontend build:
- [ ] Local smoke:
- [ ] Production/deploy smoke if applicable:

#### Handoff notes
- Changed files:
- Commands run:
- Risks:
- Rollback plan:
```

## Active tasks

### TASK-20260622-031 — PR C: strongest CV/profile selection + session-context retention

Status: scoped
Owner: unassigned
Branch: `fix/profile-context-role-selection` recommended
Issue/PR: PR C not opened yet

#### Objective
Fix the remaining production Tests 1 and 7 after the job-flow stabilization train (#727/#724/#723/#728/#729/#730).

#### Test 1
Prompt: `Find UAE jobs that match my strongest CV profile.`

Expected:
- Do not blindly use stale `target_role` such as Software Engineer.
- Use the strongest confirmed active CV/profile signal.
- If multiple profile tracks exist and confidence is ambiguous, ask the user to choose.
- Do not silently choose stale or irrelevant target_role.

#### Test 7
Prompt: `Search UAE jobs for Environmental Manager.`

Expected:
- Do not silently substitute Environmental Manager with Environmental Officer.
- If exact role is unavailable, ask permission before broadening.
- Preserve authenticated user/CV/session context.
- Do not ask a logged-in Pro user with uploaded CV to sign up or upload again.
- Keep location UAE-focused with safe preference for UAE/Ajman/Dubai/Sharjah/Abu Dhabi.

#### Constraints
- No auth rewrite.
- No billing changes.
- No DB migration.
- No #712 work.
- No landing-page work.
- No provider scraping.
- No repeated real provider searches.
- Use mocks/fixtures only in tests.
- Keep `src/services/job_link.py` as the only canonical resolver.
- Do not reintroduce `src/rico_link_resolver.py`.
- Do not touch unrelated chat flows.

#### Required process
- [ ] Start from clean current `origin/main`.
- [ ] Read-only map current CV/profile selection flow.
- [ ] Read-only map where `target_role` is loaded.
- [ ] Read-only map where auth/CV context is lost.
- [ ] Read-only map where role substitution happens.
- [ ] Report the smallest safe implementation plan before large edits.
- [ ] Add regression tests for T1 and T7.
- [ ] Open Draft PR first.
- [ ] Run focused tests and related chat/profile tests.
- [ ] Merge only if CI is green and scope is clean.
- [ ] Verify `/version` and `/health` after deploy.

#### Handoff notes
- Latest full handoff: `AI_WORKSPACE/HANDOFFS/2026-06-22-job-flow-stabilization-complete.md`.
- Current production baseline before PR C: `38fbf5da19975df6f7d3d21168b137741d502e6d`.
- Rollback plan: revert PR C only; no schema/env changes allowed.

---

### TASK-20260621-030 — CAREER-OS-04 remaining gap: inject uploaded document context into Rico AI prompt

Status: proposed
Owner: unassigned
Branch: —
Issue/PR: —

#### Objective
When a user uploads a non-CV document (offer letter, contract, cover letter, etc.) and then chats
about it, Rico currently has no access to the document type or content in its AI prompt. The upload
route now stores `last_uploaded_document` in `recent_context` (fixed in PR #717), but the chat
handler does not yet inject this into the AI system prompt or message context.

#### Existing behavior after PR #717
- Explicit meta-queries ("what did I upload?", "document type?") → answered from `recent_context`
  without an AI call via `_get_recent_upload_document_reply`.
- All other messages about the document (e.g. "can you review it?") → falls through to normal AI
  routing with no document context injected.

#### Required change
In `rico_chat_api.py` `_process_message_inner` or the AI context builder, check for
`last_uploaded_document` in `recent_context` and if the document is non-CV and recent (< 24h),
inject a brief note into the system prompt / user context:
```
[Uploaded document: {label} ({filename}) — confidence {pct}%]
```
This lets the AI model answer "can you review it?", "summarize this offer letter" etc. with
context about what was uploaded.

For non-trivial document types (offer_letter, contract, cover_letter), also check whether the
document content is available in the user's parsed files (via `user_documents` DB table) and
include a brief extract if available.

#### Constraints
- Do not touch: the document classifier, the upload route, `_get_recent_upload_document_reply`
- No migrations required
- Must not break existing job-search or onboarding flows
- Add regression tests for the injection path

#### Acceptance criteria
- [ ] User uploads a cover letter → types "can you review my cover letter?" → Rico responds
  with content-aware review (not generic advice)
- [ ] User uploads an offer letter → types "summarize it" → Rico summarizes using the document type
- [ ] No regression in job-search or onboarding flows (all existing tests pass)

---

### TASK-20260621-029 — System quality audit: bug fixes and technical debt documentation

Status: review
Owner: Claude
Branch: `claude/system-quality-audit-ikkamf`
Issue/PR: #717 (draft, CI green — pytest ✅ playwright ✅ Vercel ✅)

#### Objective
Continuous codebase audit across auth, DB, repositories, services, migrations, and routers —
fix small isolated bugs immediately, document larger issues for separate PRs.

#### Bugs fixed (all in commit `3c11717`)

1. **`src/repositories/users_repo.py`** — `list_active_users()` omitted `email_verified` from
   SELECT; all User objects silently defaulted to `email_verified=True`. Fixed by adding
   `COALESCE(email_verified, TRUE)` as column 8 and accessing as `row[7]`.

2. **`src/repositories/audit_repo.py`** — `List` used in type annotations for
   `log_profile_hydration` and `_db_write_profile_hydration` but not imported;
   `typing.get_type_hints()` would raise `NameError`. Fixed by adding `List` to
   `from typing import …`.

3. **`src/api/auth.py`** — Duplicate `response.delete_cookie()` call in `register()`
   (second call at lines 580-583 was dead code, identical to lines 482-485). Removed.

4. **`tests/test_users_scheduler.py`** — Mock fixture rows were 7-element tuples; crashed with
   `IndexError: tuple index out of range` after the `users_repo` fix added an 8th column.
   Updated both rows to 8-element tuples.

#### Issues documented (separate PRs required — do NOT touch without explicit scope)

| # | Issue | File | Recommended action |
|---|---|---|---|
| D1 | Runtime DDL bypasses migration system | `audit_repo.py` | Move 3 table creates to numbered migrations |
| D2 | `_DEDUP_CACHE` unbounded memory growth | `audit_repo.py` | Add periodic sweep or size cap in `_mem_seed` |
| D3 | Safety regex over-breadth (`password`, `bypass`) | `rico_safety.py` | Narrow with word-boundary anchors + regression tests |
| D4 | No password complexity enforcement | `src/api/auth.py` | Add length + complexity check at register and reset |
| D5 | No JWT revocation after password reset | `src/api/auth.py` | Token blacklist or rotating JWT family ID |
| D6 | `mark_webhook_event_processed` Optional[str] for UUID FK | `src/rico_db.py` | Validate UUID or change signature to Optional[UUID] |

#### Acceptance criteria
- [x] `list_active_users()` returns correct `email_verified` value from DB
- [x] `audit_repo.py` imports `List` — no `NameError` from `get_type_hints()`
- [x] No duplicate cookie deletion in `register()`
- [x] Test fixture updated to 8-element tuples
- [x] All CI checks green (pytest, playwright, Vercel, Neon)

#### Required verification
- [x] pytest ✅ (all 6 CI checks passed on PR #717)
- [x] playwright ✅
- [x] Vercel ✅ (DEPLOYED)
- [x] No regressions vs main baseline

#### Handoff notes
- Changed files: `src/repositories/users_repo.py`, `src/repositories/audit_repo.py`,
  `src/api/auth.py`, `tests/test_users_scheduler.py`, `AI_WORKSPACE/CURRENT_STATE.md`,
  `AI_WORKSPACE/TASKS.md`, `AI_WORKSPACE/START_HERE.md`
- Rollback plan: revert PR #717 — no DB schema changes, no migrations, no env changes.
- Full detail: `AI_WORKSPACE/HANDOFFS/2026-06-21-system-quality-audit.md`

---

### TASK-20260619-028 — UI/UX live-audit backlog (2026-06-19)

Status: proposed (tracking task — spin each item into its own TASK-NNN when picked up)
Owner: unassigned
Branch: —
Issue/PR: docs-only (this ledger entry)

#### Objective
Track the prioritized recommendations from the 2026-06-19 live production UI/UX audit so they
are not lost in chat history. Full detail (problem + fix + mockups) lives in
`docs/audits/ui-ux-live-audit-2026-06-19.md` (shipped via #658); this entry is the actionable
backlog distilled from it.

#### Source
Direct live audit of `ricohunt.com` covering `/command`, `/flow`, `/profile`, `/upload`,
`/settings`, `/subscription`, and the global sidebar. 20 recommendations, prioritized by
impact vs. effort. `ref` below = the section id in the audit doc.

#### Backlog (grouped by audit impact)

Critical:
- [x] 1-A — Replace A/B/C/D typed options with clickable inline action buttons. DONE via PR #678.
- [x] 1-B — Real fit-score badge on job cards (e.g. "82% match") + skills/gaps/location breakdown. DONE via PR #679.

High:
- [x] 1-D — Sidebar widgets load on every mount. DONE via TASK-20260619-027 / PR #658.
- [ ] 2-D — "Mark as Applied" inline CTA button on Link-opened cards.
- [ ] 3-B — Surface profile conflict warnings as a top-of-page banner.
- [ ] 5-A — Input validation: City (UAE list), Target roles (max 3–4), excluded-vs-target keyword warn.
- [ ] 1-C — Search timeout/countdown indicator with reliable fallback buttons (30s).
- [ ] 3-A — Profile completeness score: single source of truth (sidebar 71% vs profile 54%).

Medium:
- [x] 6-A — Navy/indigo design system. DONE via PR #641 (v4 tokens, `6fac4c0`); live + smoke-PASS 2026-06-20.
- [ ] 2-A — Demote "Link Opened" from a primary pipeline stage to card metadata.
- [ ] 4-A — CV role-mismatch warning banner on My Files.
- [ ] 6-B — First-use onboarding checklist (dismissable).
- [ ] 1-E — Cold-start amber banner ("Rico is starting up ~45s").

Low:
- [ ] 6-D — Move WhatsApp support to a floating help icon; free the sidebar for navigation.

Additional (in the audit body, outside the top-14 priority table):
- [ ] 2-B — Drag-and-drop between pipeline columns / larger stage pill.
- [ ] 2-C — Collapse zero-value pipeline stat boxes; lead with Applied/Interview/Offer.
- [ ] 3-C — "Active CV" indicator chip on the Profile page.
- [ ] 4-B — CV parse-confidence indicator + "Review parsed data".
- [ ] 5-B — Fit-score slider guidance text (explain what 80% hides).
- [ ] 6-C — Visual hierarchy: make "Ask Rico" the dominant sidebar action.

#### Constraints
- Docs/ledger only in this PR — no code changes.
- Each item becomes its own scoped TASK-NNN + branch when implemented. Do not start without
  explicit scope/branch assignment (per the Operating target in `CURRENT_STATE.md`).

#### Notes
- Per the audit, 1-A is the biggest UX win for the least effort — likely first to spin out.
- Sourced solely from the in-repo 2026-06-19 live audit doc. If a separate/larger UI/UX
  review exists, append its items here rather than starting a parallel list.

---

### TASK-20260619-027 — Sidebar status widgets: retry after failed cold-start load

Status: done (verified — production smoke PASS 2026-06-20)
Owner: Claude
Branch: `fix/sidebar-status-retry-653` (merged → `712be79` via PR #658)
Issue/PR: #658 (replaced #653, which was closed/superseded)

#### Objective
Stop the desktop sidebar READINESS/PIPELINE widgets from showing permanent blank grey boxes
when navigating back to a page after a cold-start (backend-idle) load.

#### Root cause
`useSidebarStatus` cached failed/empty cold-start loads for 60s. When the backend was cold,
all sources resolved to `null`, that empty result was cached, and subsequent remounts served
the stuck nulls — so the widgets stayed blank on navigate-back.

#### Fix (PR #658, merged `712be79`, 2026-06-19)
- `loadStatus()` uses `Promise.allSettled` and throws when both core reads (profile + stats)
  reject, so a failed cold-start is never cached and the next mount retries.
- Cached successes are served instantly and revalidated (stale-while-revalidate) to avoid flicker.
- Sidebar shows a retry affordance when status can't load (`navStatusRetry`, en + ar); the chip
  calls a TTL-bypassing `refresh()`.
- Changed files: `apps/web/hooks/useSidebarStatus.ts`,
  `apps/web/components/layout/AppSidebar.tsx`, `apps/web/lib/translations.ts`,
  `docs/audits/ui-ux-live-audit-2026-06-19.md` (audit doc).

#### Verification
- `npm run build` green; CI (pytest + playwright) green on #658.
- Production smoke PASS (2026-06-20): widgets render on mount, repopulate instantly on
  navigate-back (SWR), skeleton→data on hard refresh. Retry chip not exercised (Render warm —
  `status.error` only flips when both core reads reject on a cold mount); rendering path is
  covered by build + the both-locale `navStatusRetry` key. Smoke table recorded on PR #658
  (issuecomment-4756899519).

#### Notes
- Addresses audit item 1-D (see TASK-20260619-028).
- This is NOT TASK-024 — earlier chat shorthand mislabeled it. TASK-024 is BUG-04. The sidebar
  fix had no ledger ID until this entry, which closes that gap.

---

### TASK-20260619-026 — BUG-05: Public-chat onboarding infinite loop

Status: review
Owner: Claude
Branch: `claude/ai-workspace-review-vtdjrb`
Issue/PR: (draft PR created 2026-06-19)

#### Objective
Fix the `/command` public chat returning identical "Welcome to Rico AI…" on every message
after the first, and the double API call from the streaming fallback guard.

#### Root cause
Three compounding issues:
1. `IntentRouter` sends most messages (not starting with `?` / question word / "show me") to
   the legacy classifier.
2. Legacy classifier always returns the onboarding welcome when `profile is None`, and never
   saves state for public sessions (`_persist=False`), creating an infinite loop.
3. Frontend `if (!streamStarted)` fallback fired even when the legacy path already applied a
   response via the SSE `"done"` event — causing a duplicate API call.

#### Fix summary
- **Fix A** (`src/services/chat_service.py`): `_force_ai` gate redirects public no-profile
  legacy decisions to `_conversational_ai_reply`.
- **Fix B** (`src/api/routers/rico_chat.py`): streaming endpoint only takes legacy path when
  `profile is not None`.
- **Fix C** (`apps/web/app/command/page.tsx`): fallback guard changed to
  `!streamStarted && !responseApplied`.
- 7 unit tests in `tests/test_public_chat_no_profile_loop.py` (all PASS).

#### Acceptance criteria
- [x] Public user messages (interview prep, profile data, injection) route to AI, not welcome
- [x] Public user WITH existing profile still routes to legacy (unchanged)
- [x] Authenticated users unaffected (legacy for no-profile, AI for AI-decision)
- [x] No duplicate API call from streaming fallback
- [x] 7 unit tests passing

#### Required verification
- [x] Unit tests: 7/7 PASS (`tests/test_public_chat_no_profile_loop.py`)
- [ ] Frontend build: node_modules not installed in this environment; change is a 1-line guard
- [ ] Render deploy: pending PR merge
- [ ] Production smoke: pending PR merge

#### Handoff notes
- Changed files: `src/services/chat_service.py`, `src/api/routers/rico_chat.py`,
  `apps/web/app/command/page.tsx`, `tests/test_public_chat_no_profile_loop.py`
- Risks: `_force_ai` gate is additive; authenticated users and public users with profiles
  are unaffected. Rollback: revert `_force_ai` conditional in `send_message`.
- Open: #653 sidebar retry still draft; unrelated to BUG-05.

---
