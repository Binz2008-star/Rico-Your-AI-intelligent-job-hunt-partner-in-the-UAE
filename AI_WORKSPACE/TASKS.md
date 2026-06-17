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
