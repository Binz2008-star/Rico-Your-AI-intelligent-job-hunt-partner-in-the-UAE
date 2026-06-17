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

Status: in_progress
Owner: Codex
Branch: `codex/task-20260617-008-session-job-history`
Issue/PR: (pending)

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

### TASK-20260617-002 — Fix cover-letter intent slot extraction

Status: review
Owner: Claude
Branch: `claude/great-ritchie-75219u`
Issue/PR: (pending)

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
