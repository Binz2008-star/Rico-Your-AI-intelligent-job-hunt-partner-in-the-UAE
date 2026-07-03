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

### TASK-20260703-036 — BUG-14: pipeline save idempotency (owner-gated migration)

Status: in_progress (migration 011 APPLIED 2026-07-03; only draft PR #784 + smoke remain)
Owner: a coder for #784 + owner authenticated smoke
Branch: — (PR #784)
Issue/PR: BUG-14; draft PR #784; migration drift #711

#### Objective
Make a second "save this job" a no-op (no counter increment) on both save paths.

#### Context
- Diagnosed 2026-07-03. The chat ordinal-save persists via
  `rico_db.upsert_recommendation`, whose `ON CONFLICT (user_id, job_key) WHERE job_key
  IS NOT NULL` requires the partial unique index from **migration 011**
  (`idx_rico_recommendations_user_job_unique`) — **APPLIED in production, owner-verified
  2026-07-03** via `pg_indexes`. So the chat ordinal-save path is now idempotent.
- The non-ordinal `jobs_service.save_job/skip/block` path dedups via the JSON-file
  `is_applied()`, which returns False for DB-backed SaaS users → duplicates. Fixed only
  in **draft PR #784** (`skip/save/block` → `applications_repo.find_by_job_id`), unmerged.
- Runbook for applying migration 011 safely (dedup DELETE + partial unique index):
  `docs/runbooks/production-drift-005-011.md` (Step A).

#### Constraints
- Migration is owner-gated and includes a destructive dedupe `DELETE` — apply only at the
  Neon console after the runbook's pre-checks. Sandbox cannot reach Neon.
- No new idempotency scheme; reuse the existing `save_key` / unique-index design.

#### Acceptance criteria
- [x] Migration 011 applied to production Neon (unique index present) — verified 2026-07-03.
- [ ] PR #784 reviewed + merged (non-ordinal path uses `applications_repo`).
- [ ] Owner smoke: "save the second job" twice → count +1 then unchanged; repeat on the
      non-ordinal save path.

---

### TASK-20260702-035 — JobFromAttachmentService: first-class job entities from attachments

Status: proposed (owner architecture note, 2026-07-02)
Owner: unassigned
Branch: —
Issue/PR: follows merged PR #807 (`c7d8343`)

#### Objective
Replace the #807 heuristic fallback with a first-class service that turns any attachment
transcript into a job entity and links it to the user's pipeline. Owner-sketched design:
`JobFromAttachmentService(attachment_text, user_id)` → `extract_job_entities` (company,
title, location — NER or stronger regex) → fuzzy/trigram match against the user's existing
pipeline jobs → create a new `JobAd` (`source_type="screenshot"`) when no match → build a
`JobApplication` with `confidence_source="user_confirmed_from_screenshot"` on user
confirmation.

#### Context
- PR #807 shipped the interim behavior: `_applied_from_screenshot_fallback` +
  `_extract_job_entities_from_transcript` in `src/rico_chat_api.py` (heuristics; one-click
  confirm / disambiguation buttons; no pipeline matching, no new entities).
- Known limits of the interim fix this service should close: no fuzzy match against
  already-tracked jobs (can create near-duplicates), heuristic extraction (role-keyword
  lists), no `source_type` provenance on the created record beyond `source="chat"`.

#### Constraints
- Keep `src/rico_safety.py` guardrails and the mark-applied confirmation gate.
- No schema change without owner sign-off (JobAd/JobApplication entities imply migrations).
- False-positive guard: never create an application without explicit user confirmation.

#### Acceptance criteria
- [ ] Screenshot of an already-tracked job matches the existing pipeline row (no duplicate).
- [ ] Screenshot of a new job creates one record with screenshot provenance.
- [ ] Multi-job screenshot produces a disambiguation step (parity with #807).
- [ ] CV / identity transcripts never produce job entities.

---

### TASK-20260702-033 — Enable personalized job-alert emails (PR-3, owner-gated)

Status: in_progress (migration applied + plumbing smoke done; activation still owner-gated)
Owner: unassigned (owner-gated enable steps)
Branch: —
Issue/PR: follows merged PR #805 (`f64e7e0`)

#### Objective
Turn on the opt-in job-alert emails shipped inert in PR #805. No new feature code required to
start; this is the enable + harden pass.

#### Context
- Feature merged and gated/inert. See `CURRENT_STATE.md` → "Email job alerts — PR #805".
- Key files: `src/services/email_alert_service.py`, `src/services/email_notifications.py`,
  `migrations/033_email_job_alerts.sql`, `.github/workflows/job-alert-emails.yml`.

#### Enable steps (in order)
- [x] Apply `migrations/033` to Neon (done 2026-07-02; both tables + idx_eal_user_sent /
      idx_eut_token + primary/unique indexes verified).
- [x] Plumbing smoke: `POST /api/v1/pipeline/job-alert-emails?dry_run=true` (X-Cron-Secret) →
      `{status: ok, users: 0, sent: 0, dry_run: true}` (2026-07-02). Endpoint deployed + cron
      auth OK + dry-run bypasses kill-switch without sending. (Optional GitHub-workflow path
      still needs `RICO_API_URL` / `RICO_CRON_SECRET` repo secrets if run via CI instead.)
- [ ] Match-quality smoke: opt in one test/owner account (`POST /api/v1/settings/email/opt-in`),
      re-run the dry-run; expect `users:1` and non-zero would-send or a match-related skip reason.
- [ ] Set `RICO_ENABLE_EMAIL_ALERTS=true` on Render.
- [ ] Enable the daily `schedule:` in `job-alert-emails.yml`.
- [ ] Monitor `email_alert_log` for the first sends; verify unsubscribe link end-to-end.

#### Hardening (address before/with scale — review findings #3/#5)
- [ ] #3 — cron runs live JSearch per user sequentially in a sync request: move to async/batched
      or a queue so large opt-in volume doesn't time out or exhaust JSearch quota.
- [ ] #5 — dedup opens a new DB connection per candidate job: fetch the user's already-sent
      job_keys once per user instead of per-job.

#### Follow-on
- [ ] Arabic (RTL) email localization (English-only in MVP).

#### Rollback
Unset `RICO_ENABLE_EMAIL_ALERTS` (runtime off), disable the workflow schedule; migration 033 is
additive and code tolerates the tables being present.

### TASK-20260630-032 — Rico UX Improvements: Search & Intent Flow (engineering spec, owner-authored)

Status: proposed (tracking task — spin each item into its own TASK-NNN when picked up)
Owner: unassigned
Branch: —
Issue/PR: docs-only (this ledger entry)

#### Objective
Capture the owner's engineering spec for chat/intent-flow UX so it is not lost in chat
history. Source: owner review of the conversational search/recommendation flow, reframed as
a directly-implementable spec ("لكنني سأعيد صياغتها لتكون Engineering Spec قابلة للتنفيذ
مباشرة بدون إدخال حلول قد تقيد التصميم" — agree with most points, but reframed as an
implementable engineering spec without baking in solutions that would constrain design).
Priority: P1 (Core Conversation UX). No implementation in this entry — docs/ledger only.

#### Source
Owner-authored spec, pasted verbatim into this session on 2026-06-30, titled "Rico UX
Improvements — Search & Intent Flow." Touches `src/rico_chat_api.py` (intent classification /
role intelligence pipeline), `src/services/chat_service.py`, and the public/`/command` and
`/chat` frontends. Any implementation must continue to respect `src/rico_safety.py` guardrails
and `src/agent/runtime.py` approval-gating — interrupting a pending confirmation flow must
never be used to bypass an approval-gated action (e.g. apply).

#### Backlog (spec sections, in the owner's priority order)

1. **Interruptible Conversation Flow** — a newly detected high-confidence intent should
   interrupt a pending confirmation flow instead of Rico continuing to wait on the stale
   question. Interrupt only when: intent confidence is high, the new intent differs from the
   pending confirmation, and the request is executable immediately. Do NOT interrupt when the
   user is answering the pending question or genuine clarification is required.
   Example: Assistant asks "What sounds best to you?"; user says "Find me a job" — Rico should
   immediately start the job search ("Got it. I'll start searching for jobs that match your
   profile.") rather than re-asking the original question.
2. **Search-first Principle** — for "Find me a job" / "Find jobs from my CV" / "Search jobs",
   the primary goal is to search immediately and return results, then offer improvements —
   not to pause for configuration questions first unless search is genuinely impossible
   without them. Preferred flow: Search → Return results → Offer improvements (not the
   reverse).
3. **Internal Terms Must Never Reach Users** — internal state labels (`STALE`, `DIRTY`,
   `NEEDS_REFRESH`, `LOW_CONFIDENCE_ROLE`, etc.) must be translated into natural language
   before reaching user-facing text. E.g. not "Target roles are STALE" but "Your saved target
   roles no longer fully reflect your current experience."
4. **Recommendation Confidence** — role recommendations should surface a match percentage
   (e.g. ESG Manager 96%, Compliance Manager 94%, Operations Manager 93%, HSE Manager 92%)
   with a brief explanation of why each role is recommended.
5. **Preserve Valid Existing Roles** — do not reject a user's saved role outright just because
   stronger matches exist; grade existing + recommended roles together (✅ Strong match / ✅
   Moderate match / ❌ Weak match) instead of a categorical rejection like "Logistics doesn't
   fit." Prefer comparative phrasing: "Logistics-focused roles are a weaker match than
   Operations, ESG, Compliance, and HSE positions based on your experience."
6. **Immediate Actions** — after recommendations, present executable actions (e.g. "Search
   these roles now", "Update my saved target roles", "Compare current vs recommended roles",
   "Keep my current target roles") instead of another open-ended question; these actions
   should execute immediately when chosen.
7. **Long-running Search Experience** — searching should show an elapsed timer and progress
   updates, with a single retry if appropriate. Target max wait: 20s. If the search can't
   complete in time, return partial results when possible; otherwise explain clearly
   (provider unavailable / timeout / retry available) rather than leaving the user waiting
   indefinitely.
8. **Preserve User Intent** — the user's original request must complete before optional
   improvements are offered. E.g. for "Find jobs from my CV": (1) search jobs, (2) return
   results, (3) suggest role improvements, (4) offer to save new target roles — never reverse
   this order.

#### Owner's overall assessment (verbatim)
"The current implementation demonstrates good profile reasoning and CV understanding. The
biggest remaining UX gap is execution flow: Rico identifies improvements well, but it
sometimes pauses for confirmation instead of completing the task the user explicitly
requested. Prioritizing task completion first, followed by optional optimization, will make
the assistant feel significantly more responsive and aligned with user intent."

#### Constraints
- Docs/ledger only in this entry — no code changes.
- Each numbered item becomes its own scoped TASK-NNN + branch when implemented. Do not start
  without explicit scope/branch assignment.
- Implementation must not weaken `src/rico_safety.py` guardrails or
  `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS` — "interruptible flow" (item 1) is about routing a
  new intent, not about skipping approval gates for high-impact actions.

#### Notes
- Logged per explicit owner instruction ("note the following as we need to work on it as
  well") on 2026-06-30, immediately after BUG-2/BUG-3/BUG-6 closure. Not yet prioritized
  against BUG-7/BUG-9/BUG-10/BUG-11.

---

### TASK-20260622-031 — PR C: strongest CV/profile selection + session-context retention

Status: done (merged as PR #801 `b94ec1f` on 2026-07-01, deployed; branch deleted)
Owner: Claude
Branch: `fix/profile-context-role-selection` (merged + deleted)
Issue/PR: PR #801

#### Objective
Fix the remaining production Tests 1 and 7 after the job-flow stabilization train (#727/#724/#723/#728/#729/#730).

#### Test 1 — ✅ fixed (pending PR/merge)
Prompt: `Find UAE jobs that match my strongest CV profile.`

Expected:
- Do not blindly use stale `target_role` such as Software Engineer.
- Use the strongest confirmed active CV/profile signal.
- If multiple profile tracks exist and confidence is ambiguous, ask the user to choose.
- Do not silently choose stale or irrelevant target_role.

Fix: search-first behavior in `job_search_profile_match` and the location-guard path of
`_classified_role_search` (`src/rico_chat_api.py`) — when a saved role is stale but the CV
yields a clear single-family suggestion list, search the top CV-evidenced role immediately
with an explanatory note instead of pausing to ask. Falls back to ask-to-choose when CV
suggestions are empty or span 2+ families. Commit `48e9cba` on `fix/profile-context-role-selection`.

#### Test 7 — ✅ fixed, already on `main`
Prompt: `Search UAE jobs for Environmental Manager.`

Expected:
- Do not silently substitute Environmental Manager with Environmental Officer.
- If exact role is unavailable, ask permission before broadening.
- Preserve authenticated user/CV/session context.
- Do not ask a logged-in Pro user with uploaded CV to sign up or upload again.
- Keep location UAE-focused with safe preference for UAE/Ajman/Dubai/Sharjah/Abu Dhabi.

Fix landed directly on `main` at `bd4c4f8` ("honor verbatim role text in classified role
search") — `_classified_role_search`'s `profile_relevant` branch now passes `role_text.strip()`
instead of the taxonomy canonical alias.

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
- [x] Start from clean current `origin/main`.
- [x] Read-only map current CV/profile selection flow.
- [x] Read-only map where `target_role` is loaded.
- [x] Read-only map where auth/CV context is lost.
- [x] Read-only map where role substitution happens.
- [x] Report the smallest safe implementation plan before large edits.
- [x] Add regression tests for T1 and T7.
- [x] Open PR (merged as #801).
- [x] Run focused tests and related chat/profile tests — 27/27 in
      `tests/unit/test_profile_context_role_selection.py`; 143/143 across
      `test_bug17_pipeline_reset.py`, `test_bug12_arabic_search_locale.py`,
      `test_arabic_context_retention.py`, `test_apply_tracking_and_freshness.py`,
      `test_manual_application_tracking.py`, `test_lifecycle_followup.py`,
      `test_application_tracking_intelligence.py`, `test_p0_trust_fixes.py`.
- [x] Merge only if CI is green and scope is clean (merged #801, CI green).
- [x] Verify `/version` and `/health` after deploy (verified through the #806/#807/#808
      deploy chain — production at `a2a53b4`, health ok, 2026-07-02).

#### Handoff notes
- Latest full handoff: `AI_WORKSPACE/HANDOFFS/2026-06-22-job-flow-stabilization-complete.md`.
- Current production baseline before PR C: `38fbf5da19975df6f7d3d21168b137741d502e6d`.
- T1 fix source: an unmerged background session left the search-first behavior on
  `origin/claude/workflow-progress-check-qycxuo` (commit `52e44b8`) alongside T7 and TASK-030
  fixes that had already been hand-ported to `main` separately (`bd4c4f8`, `77563af`). Only the
  search-first hunks were hand-applied to `fix/profile-context-role-selection` — that branch
  also carried a stale `_build_tracking_message` hunk (pre-dating PR #797's opened/applied
  stage-count fix) which was intentionally NOT ported, since applying it would have regressed
  that fix. `claude/workflow-progress-check-qycxuo` has since been deleted as fully superseded.
- Rollback plan: revert the merge commit for `fix/profile-context-role-selection`; no
  schema/env changes, isolated to `src/rico_chat_api.py` chat-routing logic.
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
