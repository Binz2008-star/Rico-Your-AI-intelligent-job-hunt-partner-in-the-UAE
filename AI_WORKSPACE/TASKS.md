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
