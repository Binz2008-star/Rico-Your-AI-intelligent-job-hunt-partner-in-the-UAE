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
<one objective only>

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

### TASK-20260618-011 — Guard preferred_cities against yes/no input

Status: in_progress
Owner: Claude
Branch: `claude/magical-allen-343jp2`
Issue/PR: (pending)

#### Objective
Prevent non-city strings ("نعم", "لا", "yes", "no") from being stored in
`preferred_cities` when collected via the chat pending-field handler or Jotform webhook.
Also provide a SQL data patch for the one known bad record (`robenedwan@gmail.com`).

#### Context
- Relevant files:
  - `src/rico_chat_api.py` — pending-field handler for `preferred_cities` (line ~4136)
  - `src/rico_jotform_webhook.py` — `map_jotform_payload()` line 116
  - `src/services/matching_guardrails.py` — `is_uae_city()` already warns on stored invalid cities
- Root cause: when Rico asks "What city do you prefer?" and the user replies "نعم",
  the chat handler accepts it (not an intent verb, short enough) and stores it. Jotform
  field mapping has no validation at all.
- Existing behavior: matching_guardrails warns on retrieval but does not prevent storage.

#### Constraints
- No DB schema changes. No frontend changes. No scoring changes.
- Do not add a new service module — filter inline or as a module-level constant.
- Data patch is provided as SQL in PR description; user runs it manually on Neon.
- Keep tests unit-only, no DB/network.

#### Acceptance criteria
- [x] Replying "نعم" / "yes" / "no" / "لا" to Rico's city prompt is rejected (returns None,
      prompts again) — preferred_cities not updated.
- [x] Valid city ("Dubai", "دبي") still accepted and saved correctly.
- [x] Jotform `preferred_cities` field strips yes/no strings before storage.
- [x] Unit tests cover yes/no rejection and valid-city acceptance.
- [x] Backend test suite passes with no regressions.

#### Required verification
- [x] `python -m py_compile` clean on changed files.
- [x] `python -m pytest tests/unit/test_preferred_cities_guard.py` — 21/21 passed.
- [x] Full backend test suite: 2768 passed, no regressions.
- [x] Frontend build: not required (no frontend changes).

#### Handoff notes
- Changed files:
  - `src/rico_chat_api.py` — `_CITY_REJECT_WORDS` class constant + one-line filter in
    `_resolve_pending_field` preferred_cities branch
  - `src/rico_jotform_webhook.py` — `_CITY_REJECT_WORDS` module constant +
    `_as_city_list()` helper; `map_jotform_payload()` uses it
  - `tests/unit/test_preferred_cities_guard.py` — 21 new unit tests
  - `AI_WORKSPACE/TASKS.md`
- Data patch SQL (run on Neon after merge):
  ```sql
  UPDATE rico_profiles
  SET profile = jsonb_set(profile, '{preferred_cities}', '[]'::jsonb)
  WHERE profile->'preferred_cities' @> '["نعم"]';
  ```
- Rollback plan: revert the two source files.

---

### TASK-20260617-010 — Fix chat composer clip icon UX

Status: done
Owner: Claude
Branch: `claude/magical-allen-343jp2`
Issue/PR: #623

#### Objective
Make the chat composer clip icon reliably open the file picker on all browsers,
including mobile Safari and WebViews that block programmatic `input.click()`.

#### Context
- Relevant files:
  - `apps/web/app/command/page.tsx` (hidden file input + clip button in composer)
- Root cause: `<button onClick={() => fileInputRef.current?.click()}>` silently fails on
  some mobile browsers because programmatic `.click()` on a hidden file input is treated
  as an untrusted event. The `/upload` page works because it uses native label/input wiring.
- Existing behavior: clip button exists and is wired, but the file picker never opens on
  affected browsers.

#### Constraints
- Frontend composer only. No backend, no CV parser, no DB, no scoring, no AI provider.
- Do not change upload logic (handleCVUpload, confirmCVProfile, etc.).
- Do not change tests beyond what is practical for the click behaviour.

#### Acceptance criteria
- [x] Clicking the clip icon opens a native file picker on desktop and mobile.
- [x] Icon is visually dimmed and non-interactive during `checking`/`thinking` state.
- [x] Accept attribute extended to `.pdf,.doc,.docx` (more useful than `.pdf` only).
- [x] Frontend build passes with no TypeScript errors.

#### Required verification
- [x] `npm run build` clean in `apps/web`.
- [x] CI QA Tests (pytest + playwright) green on PR.
- [x] Manual smoke: click clip icon on desktop → file chooser opened (Playwright confirmed).
- [x] Manual smoke: click clip icon on mobile (iPhone 14 Pro UA) → file chooser opened.
- [x] Disabled/checking state: no `for` attr + `pointer-events-none` + `opacity-30` confirmed.
- [x] Upload flow (setInputFiles): no crash confirmed.

#### Handoff notes
- Changed files:
  - `apps/web/app/command/page.tsx` — hidden `<input>` gets `id="cv-file-upload"` and
    `accept=".pdf,.doc,.docx"`; `<button>` replaced with `<label htmlFor="cv-file-upload">`
    with equivalent disabled/aria styling.
  - `AI_WORKSPACE/TASKS.md`
- Risks: None. `<label htmlFor>` pattern is universally supported and more reliable than
  programmatic `.click()`. The `ref` on the input is kept for the `__cv_upload__` magic
  message path (line ~811) which is unaffected.
- Rollback plan: revert the single file `apps/web/app/command/page.tsx`.
- Non-blocking follow-up: `aria-disabled`/`tabIndex` polish (SSR/hydration timing nuance,
  functional behaviour is correct via `pointer-events-none` + missing `for` attr).
- Production: squash-merged to main as `4df959bdee354d4bf431925c5d3fbb10354801ba` (#623).
  Deployed to Vercel automatically (Deploy to Production ✅ 2026-06-17T22:08 UTC).
  Render backend also live as of 2026-06-17T22:12 UTC (separate manual deploy).

---

### TASK-20260617-009 — CV extraction quality warnings

Status: done
Owner: Claude
Branch: `claude/magical-allen-343jp2`
Issue/PR: #621

#### Objective
Surface lightweight advisory warnings when a CV upload produces low-quality extraction,
an unrealistic years_experience value, very few detected skills, or a role mismatch between
the CV's current_role and the user's target_roles. Warnings are advisory only — saves are
never blocked and scoring is never changed.

#### Context
- Relevant files:
  - `src/services/cv_quality_warnings.py` (new)
  - `src/api/routers/rico_chat.py` (upload response, confirm-cv response)
  - `src/cv_parser.py` (ParsedCV.extraction_quality, skills, years_experience_hint)
  - `src/services/matching_guardrails.py` (pattern reference)
  - `tests/unit/test_cv_quality_warnings.py` (new)
- Existing behavior: `extraction_quality` is computed during parsing but no warnings
  are surfaced to the caller.

#### Constraints
- Do not add migrations or change DB schema.
- Do not change scoring or search ranking.
- Do not change auth, billing, or env config.
- Do not touch unrelated UI pages or Application Pipeline work.
- Advisory only — no saves blocked.

#### Acceptance criteria
- [x] `build_cv_quality_warnings()` warns on `extraction_quality` "poor"/"partial".
- [x] Warns when `years_experience` > 25 (high) or > 50 (unrealistic).
- [x] Warns when fewer than 3 skills are detected (but list is non-empty).
- [x] Warns when CV `current_role` shares no keywords with `target_roles`.
- [x] Upload response includes `warnings` field.
- [x] Tests cover all four warning scenarios plus the no-warnings path.

#### Required verification
- [x] Unit tests: `tests/unit/test_cv_quality_warnings.py` — 30/30 passed.
- [x] Syntax check: `python -m py_compile` clean on both changed files.
- [x] Full backend test suite: 2620/2620 passed, no regressions.
- [x] Frontend build: not required; no frontend files changed.
- [x] CI: pytest ✅ playwright ✅ Vercel ✅ Neon/setup ✅ on PR #621.

#### Handoff notes
- Changed files:
  - `src/services/cv_quality_warnings.py` (new)
  - `src/api/routers/rico_chat.py` (import + `warnings` field in upload response)
  - `tests/unit/test_cv_quality_warnings.py` (new)
  - `AI_WORKSPACE/TASKS.md`
- Risks: role-mismatch check is keyword-overlap heuristic; unusual role phrasings may
  produce a false positive. Warning is advisory so the impact is low.
- Rollback plan: revert the three source/test files.
- Production: squash-merged to main as `b9708c91c0afd1b8d8a5ea83d7ff29aee02f5fb2` (#621).
  Render deploy not yet triggered. CV quality warnings are on main but not confirmed
  production-live. Trigger Manual Render Deploy before smoke-testing this feature.

---

### TASK-20260617-008 — Add session-level job search history

Status: done
Owner: Codex
Branch: `codex/task-20260617-008-session-job-history`
Issue/PR: #617

#### Objective
Track lightweight job-search summaries in the current Rico chat session so Rico can answer
how many jobs it found earlier in the same conversation.

#### Context
- Relevant files:
  - `src/rico_chat_api.py`
  - `tests/unit/test_rico_job_search_tracker_flow.py`
  - `tests/unit/test_followup_fast_path.py`
  - `AI_WORKSPACE/EVALS/2026-06-17-post-615-616-verification.md`
- Existing behavior: Rico caches recent search matches but count follow-ups only read the
  current cached match list and can miss Arabic/session-count phrasing such as
  `كم عدد الوظائف التي وجدتها منذ بداية المحادثة`.

#### Constraints
- Do not add Redis unless already wired and necessary.
- Do not change DB schema.
- Do not change scoring/search ranking.
- Do not touch unrelated UI pages.
- Do not change Settings/Profile guardrails from #616.

#### Acceptance criteria
- [x] When Rico returns N jobs, store a lightweight search summary for the session.
- [x] User can ask how many jobs Rico found in the current conversation.
- [x] Response includes last search count, role/query, city if available, and top match if available.
- [x] If no searches happened in the current session, Rico says that clearly.
- [x] Regression tests cover storing, follow-up count, and no-history path.

#### Required verification
- [x] Unit tests: focused session job history tests.
- [x] Existing chat/job routing tests: focused nearby tests attempted; existing local routing fixture failures are noted below.
- [x] Frontend build: not required; no frontend files changed.
- [x] Production/deploy smoke: not in this PR; post-#615/#616 deploy health was recorded before starting.

#### Handoff notes
- Changed files:
  - `AI_WORKSPACE/EVALS/2026-06-17-post-615-616-verification.md`
  - `AI_WORKSPACE/TASKS.md`
  - `src/rico_chat_api.py`
  - `tests/unit/test_followup_fast_path.py`
  - `tests/unit/test_rico_job_search_tracker_flow.py`
- Commands run:
  - `git fetch origin main`
  - `gh run list --branch main --limit 10 --json ...`
  - `gh run view 27713530030 --json ...`
  - `Invoke-RestMethod https://rico-job-automation-api.onrender.com/health`
  - `Invoke-RestMethod https://rico-job-automation-api.onrender.com/version`
  - `Invoke-RestMethod https://rico-job-automation-api.onrender.com/api/v1/version`
  - `python -m py_compile src\rico_chat_api.py`
  - `python -m pytest tests\unit\test_rico_job_search_tracker_flow.py tests\unit\test_followup_fast_path.py::TestResultCount -q`
  - `python -m pytest tests\unit\test_rico_routing_fix.py tests\unit\test_job_search_role_extraction.py tests\unit\test_rico_profile_job_search_role_list.py tests\unit\test_self_ref_role_resolution.py tests\unit\test_role_context_routing.py -q`
- Test results:
  - Focused acceptance suite: `24 passed`.
  - Syntax check: passed.
  - Existing local routing subset: `107 passed, 2 failed`; failures were in
    `tests/unit/test_rico_routing_fix.py` expecting `run_for_profile` calls and match the known
    stale local routing fixture pattern. No routing/scoring code was changed for this task.
- Risks: process-local session history is intentionally lightweight. It answers immediate
  follow-ups even when JSON recent-context writes are disabled, but it is not durable across
  process restarts or multi-worker hops. Existing `recent_context` remains the primary store when available.
- Rollback plan: revert the TASK-008 PR commit.
- Production: squash-merged to main as `09027412ac3287e7ec78e6b73dd964a607c36357` (#617).
  Deployed to Render. Smoke test 2026-06-17: session job count confirmed working.

### TASK-20260617-007 — Add matching guardrails

Status: done
Owner: Codex
Branch: `codex/task-20260617-007-job-match-guardrails`
Issue/PR: #616

#### Objective
Surface advisory warnings for contradictory matching settings and risky profile inputs on
Settings and Profile pages without blocking saves. Preserve DB schema and scoring behavior.

#### Acceptance criteria
- [x] Backend guardrail evaluator warns on contradictory include/exclude keywords.
- [x] Backend guardrail evaluator warns on high `min_score` with broad criteria.
- [x] Backend guardrail evaluator warns on invalid city or excessive target roles.
- [x] Warnings returned as advisory fields; saves are not blocked.
- [x] English and Arabic warning messages supported.

#### Handoff notes
- Changed files: `src/services/matching_guardrails.py`, `src/api/routers/settings.py`,
  `src/api/routers/rico_chat.py`, `src/schemas/settings.py`, frontend Settings/Profile
  warning display, related tests.
- Production: squash-merged to main as `a8516c188baa0841d7f2ec7b942ef9215e9e2787` (#616).
  Deployed to Render. Smoke test 2026-06-17: guardrails confirmed working.

### TASK-20260617-002 — Fix cover-letter intent slot extraction

Status: done
Owner: Claude
Branch: `claude/great-ritchie-75219u`
Issue/PR: #615

#### Objective
Extract role, company, city, and language from a single cover-letter request and
generate the letter directly instead of re-asking for role/company.

#### Context
- Relevant files:
  - `src/rico_chat_api.py` (`_extract_explicit_draft_job_from_message`,
    `_cover_letter_clarification_message`, `_COVER_LETTER_TIPS_RE`, draft handler)
  - `src/cover_letter_writer.py` (Arabic generation path)
  - `src/message_generator.py` (Arabic partial-identity prompt)
  - `tests/test_cover_letter_slot_extraction.py` (new)
- Existing behavior: the Arabic message
  `اكتب لي خطاب تقديم لوظيفة ESG Manager في شركة Aldar Properties في أبوظبي`
  returned no slots (English-only regex) and the bare phrase `خطاب تقديم` was
  caught by the cover-letter *tips* gate, so Rico re-asked for role/company.

#### Constraints
- Do not rewrite routing; keep the fix minimal.
- Do not touch unrelated handlers, DB schema, or the frontend.

#### Acceptance criteria
- [x] Arabic request with role + company + city generates an Arabic letter directly.
- [x] English request with role + company + city generates an English letter directly.
- [x] Missing role or company asks only for the missing field.
- [x] Existing chat routing / cover-letter tests still pass.
- [x] Regression test for the exact Arabic Aldar ESG Manager example.

#### Handoff notes
- Changed files: `src/rico_chat_api.py`, `src/cover_letter_writer.py`,
  `src/message_generator.py`, `tests/test_cover_letter_slot_extraction.py`,
  `AI_WORKSPACE/TASKS.md`.
- Commands run: targeted `pytest` suites (cover letter, intent, document,
  agent, jotform, jwt, onboarding) — all green.
- Risks: Arabic slot regex is heuristic; unusual phrasings may still need
  clarification (safe fallback). Tightened Arabic tips regex now requires an
  interrogative/advice context.
- Rollback plan: revert the four source/test files on this branch.
- Production: squash-merged to main as `66f7364f8b6ea03326223383b5536c627204ffd2` (#615).
  Deployed to Render. Smoke test 2026-06-17: Arabic cover-letter confirmed writing directly.
  Previous failure was a deployment gap, not an active code bug.

### TASK-20260617-001 — Add AI multi-model sync workspace

Status: done
Owner: ChatGPT
Branch: `chore/ai-workspace-sync-standard`
Issue/PR: #610

#### Objective
Add a repo-native shared source of truth for AI planning, implementation handoffs, review, verification, and decision tracking.

#### Acceptance criteria
- [ ] Add `AI_WORKSPACE/` docs.
- [ ] Add handoff and evaluation templates.
- [ ] Add a context bundle script.
- [ ] Update PR template with handoff evidence fields.
- [ ] Open a focused PR.

#### Required verification
- [ ] Documentation-only change; no runtime tests required.
- [ ] Confirm changed files are limited to docs/templates/script.

#### Handoff notes
- Merged via squash into main: a76a1b6

## Backlog — next priorities

Ordered by current priority. Do not start without explicit scope and branch assignment.

1. **CV extraction quality warnings** — surface structured warnings when CV parse quality is low
   (missing sections, unrecognised format, low confidence fields). Advisory only; do not block upload.
2. **Application Pipeline V1** — end-to-end application submission flow with approval gate,
   audit log, and Telegram confirmation. Requires `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`.
3. **Pipeline relevance guard** — pre-filter pipeline job results against active profile before
   scoring to reduce false-positives reaching the user.
4. **Match score explanation** — expose per-field score breakdown in job cards so users
   understand why a job ranked high or low.
5. **Blocked link UX** — detect dead/redirected apply URLs before showing them to users;
   surface a clear "link unavailable" state instead of a broken redirect.

### Active issues
- **Issue #618** — open as backlog for Arabic intent / smoke-test observations.
  Arabic cover-letter parser confirmed fixed in production after #615 deploy.
  Do not treat as P0 unless a new reproducible failure appears after commit
  `525964d758d13b86cf0f9b2907bdde7be773d9da`.
