# Handoff — Agentic UI Implementation Brief

Date: 2026-06-20
Branch: `docs/agentic-ui-architecture`
PR: #670
Status: architecture/scoping handoff for Claude implementation

## Mission

Build Rico into a conversation-first, multimodal, permission-aware AI career entity for the UAE job market.

Do not treat this as a generic UI polish task. The product goal is to move Rico from a form/page-heavy job tool into an agentic career workspace where the chat can understand user intent, files, screenshots, and job context, then propose safe next actions.

## Read first

1. `AI_WORKSPACE/START_HERE.md`
2. `CLAUDE.md`
3. `AI_WORKSPACE/OPERATING_RULES.md`
4. `docs/architecture/agentic-ui-action-layer.md`
5. Current PR #670 discussion and diff

If current repo state differs from this handoff, use live `main`, PR metadata, and `CURRENT_STATE.md` as source of truth. Report conflicts before coding.

## Non-negotiable principles

- No high-impact action may execute from the frontend alone.
- Do not bypass `agent_runtime.handle_action()` for job actions.
- Do not bypass `src/rico_safety.py`.
- Preserve `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` behavior.
- Do not silently mutate profile/settings from chat or uploaded files.
- Every profile/settings/file-derived mutation must show proposed changes and require approval.
- Existing text-only chat responses must remain backward-compatible.
- Keep old pages as fallback until chat-first replacements are verified.
- Do not assume every upload is a CV.

## Target architecture summary

Rico responses should support an optional `agentic_ui` envelope:

```json
{
  "message": "I found a job post in your screenshot.",
  "type": "document_analysis",
  "agentic_ui": {
    "actions": [],
    "permission_request": null,
    "progress": [],
    "proposed_changes": [],
    "attachment_analysis": []
  }
}
```

The old `message` and `type` fields continue working for all existing clients.

## Implementation sequence

Implement in small PRs. Do not combine these phases into one broad change.

### PR-A — Backend contracts only

Branch suggestion: `feat/agentic-ui-contracts`

Objective:
Add typed backend response contracts for agentic UI without changing runtime behavior.

Scope:

- Add schema models for:
  - `RicoChatAction`
  - `RicoPermissionRequest`
  - `RicoProgressStep`
  - `RicoProposedChange`
  - `RicoAttachmentAnalysis`
  - `RicoAgenticUi`
- Add optional `agentic_ui` to relevant chat response schema or response assembly layer.
- Add tests confirming old response shape still works when `agentic_ui` is absent.
- Add tests confirming `agentic_ui` serializes with empty arrays/nulls when present.

Likely files:

- `src/schemas/*` or the closest existing schema module
- `src/rico_chat_api.py`
- `src/services/chat_service.py`
- `src/api/routers/rico_chat.py`
- relevant tests under `tests/`

Acceptance:

- Existing chat tests pass.
- New schema tests pass.
- No frontend changes.
- No DB migration.
- No production behavior change except optional extra response field when explicitly used.

Verification:

```bash
python -m pytest tests/ -q --tb=short
```

If full suite is too noisy, run targeted schema/chat tests and clearly state what was not run.

### PR-B — Frontend action card renderer

Branch suggestion: `feat/chat-action-cards`

Objective:
Render `agentic_ui.actions` in chat messages without changing backend logic.

Scope:

- Extend frontend API types for `agentic_ui`.
- Add components:
  - `ChatActionCard.tsx`
  - `ChatActionsRow.tsx`
  - minimal renderer integration in chat/command surface
- Handle action kinds safely:
  - `navigate`
  - `chat_continue`
  - `open_drawer` as no-op/fallback if drawer not implemented yet
- High-impact actions must not execute in this PR.

Likely files:

- `apps/web/lib/api.ts`
- `apps/web/app/chat/page.tsx`
- `apps/web/app/command/page.tsx`
- `apps/web/components/*`
- translation/i18n file if labels are generated frontend-side

Acceptance:

- Existing messages render unchanged.
- Messages with actions render polished buttons/cards.
- Mobile layout does not overlap composer/bottom nav.
- Unknown action kinds are ignored safely or rendered disabled.

Verification:

```bash
cd apps/web
npm run build
npm run lint
```

### PR-C — First real actions on job/profile responses

Branch suggestion: `feat/agentic-job-actions`

Objective:
Start returning safe action cards from backend for high-value chat responses.

Initial actions:

- Job results:
  - `View jobs`
  - `Save search`
  - `Tailor CV`
  - `Draft cover letter`
- Incomplete profile:
  - `Complete profile`
  - `Upload CV/file`
  - `Review missing fields`
- CV/upload success:
  - `Review parsed profile`
  - `Find matching jobs`

Constraints:

- No apply execution.
- No profile mutation.
- No settings mutation.
- No DB migration.

Acceptance:

- Job search response includes action cards.
- Profile incomplete response includes action cards.
- Old text response still readable if frontend ignores `agentic_ui`.

### PR-D — Universal multimodal intake Phase 1

Branch suggestion: `feat/universal-career-intake`

Objective:
Stop treating uploads as CV-only. Add purpose classification and response cards for non-CV uploads.

Scope:

- Add attachment purpose enum:
  - `cv_resume`
  - `job_post`
  - `recruiter_message`
  - `application_form`
  - `certificate`
  - `offer_letter`
  - `contract_or_legalish`
  - `company_profile`
  - `public_comment`
  - `unknown_document`
- Add `attachment_analysis` response support.
- Reuse current PDF/DOCX/text extraction where available.
- Add image/screenshot handling only if existing dependencies/support make it safe; otherwise return structured `needs_ocr` warning and prepare the interface.
- Add action cards after analysis:
  - `Save opportunity`
  - `Compare to my CV`
  - `Draft reply`
  - `Find similar jobs`

Constraints:

- Do not save extracted fields without user approval.
- Do not fabricate form answers.
- Do not claim legal advice for contracts/offers.
- Low-confidence extraction must be visible.

Acceptance:

- CV upload still works.
- Non-CV upload does not get forced into CV parser path.
- Unknown document asks clarifying question.
- Recruiter/job/public-comment document produces relevant next actions.

### PR-E — Proposed changes card for profile/settings

Branch suggestion: `feat/conversational-settings-review`

Objective:
Allow users to update profile/search settings through Rico conversation with a before-save review card.

Scope:

- Extract low-risk profile/settings changes from chat.
- Return `proposed_changes`.
- Render `ProposedChangesCard`.
- Save only after explicit approval.

Start with:

- cities
- target roles
- minimum salary
- language preference
- search filters

Constraints:

- No silent writes.
- Server-side validation required.
- Existing `/profile` and `/settings` remain fallback views.

### PR-F — Permission prompts and approval queue

Branch suggestion: `feat/permission-prompts-queue`

Objective:
Add real high-impact action approval flow.

Scope:

- Render `PermissionPromptCard`.
- Add backend confirmation endpoint or adapt existing action endpoint.
- Persist pending actions only if needed; if migration is needed, propose it in a separate PR first.
- First high-impact flow: apply approval.

Constraints:

- Server-side confirmation required.
- User identity from JWT/session only.
- No request-body `user_id` trust.
- Audit log required.

## Claude execution prompt

Use this prompt to start implementation after PR #670 is merged or accepted:

```text
Rico mode. Implement the Agentic UI plan from docs/architecture/agentic-ui-action-layer.md. Start with PR-A only: backend contracts for optional agentic_ui response support. Read AI_WORKSPACE/START_HERE.md, CLAUDE.md, AI_WORKSPACE/OPERATING_RULES.md, and this handoff. Keep the PR small. No frontend changes, no DB migration, no runtime behavior change beyond optional response schema support. Add tests for serialization/backward compatibility. Return changed files, commands run, test results, risks, and rollback plan.
```

## Product voice guidance

Rico should speak like a specialized career assistant, not a generic bot.

Good:

```text
I found a job post in your screenshot. I can extract the role, compare it to your profile, and draft a recruiter reply. Nothing will be saved or sent unless you approve.
```

Avoid:

```text
Here is the OCR result.
```

Good:

```text
I can update your search preferences to Dubai and Sharjah with a minimum salary of AED 15,000. Review before saving.
```

Avoid:

```text
Settings updated.
```

## Initial demo target

The first visible demo should be:

1. User searches for jobs or uploads a job screenshot.
2. Rico identifies the context.
3. Rico displays polished action cards.
4. User clicks a safe next step.
5. Any sensitive action shows approval, not execution.

## Rollback

Each implementation PR must be independently revertible.

- Contract PR: remove schema fields/imports.
- Frontend action cards: remove renderer and keep plain message rendering.
- Upload classification: route all uploads back to existing CV behavior only if necessary.
- Proposed changes: disable save action and keep cards read-only.
- Permission prompts: disable approve endpoint and keep queue read-only.
