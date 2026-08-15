# Handoff — 2026-08-15 rico_chat_api monolith split (Increment 1: intent cluster)

## Objective
Split `src/rico_chat_api.py` (24,305 lines) into `src/chat/*` modules. One task,
one branch/PR (blocked — see Git below). Logic-preserving move only.

## Workspace / Git state (CRITICAL)
- Working checkout: `X:\rico\Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE-worktree-main`
  is a **standalone copy**, NOT a registered git worktree. Its `.git` is a broken
  146-byte pointer to `X:/Rico-.../.git/worktrees/...` (path does not exist).
  `git status/branch/log` all fail in this folder. There is **no VCS rollback** here.
- Real repo: `X:\rico\Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE` on branch
  `obs/job-search-operation-stage-timing` @ `0150c0fa` with uncommitted local changes
  (deleted `.claude/skills/*`, untracked `plans/`, `AI_WORKSPACE/HANDOFFS/2026-08-04-...`).
  Only `pr1488-correction-v3` is a registered worktree. **Do NOT touch the
  `greeting-response` worktree.**
- `PROJECT_STATUS.md` snapshot (2026-07-30) records `main=16e99a67`; live GitHub main/open
  PRs could NOT be verified (no working git in the checkout). Report before any push/PR.

## What was done (Increment 1 — module-level intent cluster only, additive)
- Backup: `C:\Users\loyal\AppData\Local\Temp\opencode\rico_chat_api.py.bak` (1,331,064 bytes).
- Created `src/chat/__init__.py` + `src/chat/intent_router.py` (262 lines) via verbatim
  line-range extraction (no transcription): city-scan regexes, manual-track abbrev regex +
  `_manual_track_field`, gates `_gate_is_application_data_request`/`_gate_is_file_list_question`,
  acknowledgement cluster (`_ACKNOWLEDGEMENT_REPLIES`, `_DEFAULT_ACK_REPLY`,
  `_GRATITUDE_ONLY_REPLIES`, `_ACK_TRAILING_PUNCT`, `_acknowledgement_key`,
  `_is_gratitude_only`, `_acknowledgement_reply`), multi-city cluster (`_MULTI_CITY_SCAN_*`,
  `_UAE_CITY_CANON`, `_requested_cities_from_text`, `_canonical_requested_cities`,
  `_location_matches_requested_cities`).
- `src/rico_chat_api.py` 24,305 → 24,092 lines: removed 244 lines, added 5 marker comments
  (`# moved to src.chat.intent_router`) + re-export import block (line 94). **Zero class-method
  changes.** All names re-exported so existing callers/tests/harness patch targets resolve.

## Verification (all green)
- Import + 17-name re-export identity (`src.rico_chat_api.X is src.chat.intent_router.X`) OK.
- Behavior parity spot-checks OK; `py_compile` OK.
- Tests (env: fake DSNs, `RICO_ENV=test`): `test_acknowledgement_intent.py` 28 passed,
  `test_1262_conversational.py` 44 passed, `test_tc7_structured_tracking_text.py` 44 passed,
  `test_application_lifecycle.py` 21 passed. Total 137 passed.
- `tests/test_ai_grounding_contract.py` HANGS in this environment (pre-existing, unrelated):
  `_build_openai_context` makes a real `psycopg2` connect (refused localhost:5432) + slow
  spacy import. Excluded from gate. Also `tests/test_rico_chat_api.py` does not exist
  (task's original run command was invalid).

## Remaining (next increments — NOT started, needs owner decision)
1. Intent-predicate class methods (~40: `_is_affirmative`, `_looks_like_*`, `_is_live_job_search_request`, ...)
   → `src/chat/intent_router.py` as a mixin (`class RicoChatIntentRouter`), `RicoChatAPI(RicoChatIntentRouter)`.
2. Context building (~60: `_build_openai_context`, CV/documents, `_resolve_profile`, ...) → `src/chat/context_builder.py`.
3. Response formatting + provider cascade + ~70 advice-topic handlers (~150) → `src/chat/response_formatter.py`.
4. Thin orchestrator ≤300 lines — only after 1–3 green and owner approves (requires re-pointing
   ~15 test files' `patch("src.rico_chat_api.<name>")` targets to the new modules).
- RISK: every moved method resolves bare-name globals in ITS module; any test patching a
  `src.rico_chat_api.<name>` used by a moved method must be re-pointed. The module-level
  re-export pattern (used here) does NOT fix class-method patch targets.

## Stop conditions
- No push/PR/merge/deploy without fixing git and owner approval.
- Do not run the full `tests/` suite locally (many env-dependent hangs).
- Restore path: copy `.bak` back over `src/rico_chat_api.py`.
