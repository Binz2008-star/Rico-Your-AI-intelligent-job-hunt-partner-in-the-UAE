# Handoff — Rico Career OS Roadmap

Date: 2026-06-20
Branch: `docs/rico-career-os-roadmap`
Status: product architecture + implementation roadmap

## One mission

Now that Rico is stable, the only active product mission is to evolve it from a form/page-heavy job tool into a conversation-first, multimodal, permission-aware AI career operating system for the UAE job market.

This roadmap must reuse what already exists in the repo. Do not rebuild systems that are already stable. Extend, adapt, and harden them.

## Branch naming

Use this branch for the planning PR:

```text
docs/rico-career-os-roadmap
```

Implementation branches should be scoped and numbered:

```text
feat/career-os-01-agentic-contracts
feat/career-os-02-action-cards
feat/career-os-03-job-actions
feat/career-os-04-universal-intake
feat/career-os-05-proposed-changes
feat/career-os-06-permission-prompts
feat/career-os-07-approval-queue
feat/career-os-08-chat-first-shell
```

## What already exists and should be reused

### Backend chat surface

Existing:

- `src/api/routers/rico_chat.py`
- Authenticated endpoint: `POST /api/v1/rico/chat`
- Public endpoint: `POST /api/v1/rico/chat/public`
- Streaming endpoints for authenticated/public chat
- Shared schema: `src/schemas/chat.py::RicoChatResponse`
- Chat orchestration through `src/services/chat_service.py`

Reuse:

- Add optional `agentic_ui` to the existing `RicoChatResponse` instead of creating a separate response path.
- Preserve legacy text fields: `message`, `type`, `matches`, `options`, `next_actions`.
- Keep `extra="allow"` behavior during migration.

Do not:

- Replace `chat_service.send_message()`.
- Create a parallel chat API.
- Break public chat compatibility.

### Existing frontend schema foundation

Existing:

- `apps/web/lib/api.ts`
- `apps/web/lib/schemas/index.ts`
- `RicoChatResponseSchema` already uses `.passthrough()` and accepts many legacy fields.
- Existing agent UI schemas already exist for `/agent` surface:
  - `AgentActionSchema`
  - `AgentUIResponseSchema`
  - `AgentUIComponentSchema`

Reuse:

- Extend `RicoChatResponseSchema` with optional `agentic_ui`.
- Reuse ideas from `AgentActionSchema`, but do not force the Rico chat API to use the exact older `/agent` shape if it does not fit.
- Build action-card rendering as additive UI around current message rendering.

Do not:

- Replace all message rendering in one PR.
- Delete legacy options/next_actions rendering until agentic cards cover them.

### Existing action execution boundary

Existing:

- `src/agent/runtime.py`
- `agent_runtime.handle_action()` is the central dispatcher for job actions.
- Existing action types include apply/save/skip/not_relevant/block/draft/why/remind/trigger_pipeline.
- Runtime already has idempotency and audit logging through `src.repositories.audit_repo`.

Reuse:

- Permission prompts must eventually call into `agent_runtime.handle_action()` for job actions.
- Approval queue should store intent/payload, then execution uses runtime.
- Idempotency and audit logging should remain centralized.

Do not:

- Execute apply/save/draft directly from frontend action buttons.
- Bypass runtime for job actions.

### Existing safety model

Existing:

- `src/rico_safety.py`
- `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`
- Apply automation gating and approval behavior already exists in the stack.
- Profile mutation bugs were recently fixed to avoid silent writes.

Reuse:

- Proposed profile/settings changes must use the same ask-first pattern.
- High-impact actions must require server-side confirmation.
- Uploaded file-derived data must never silently update profile/settings.

Do not:

- Reintroduce silent `upsert_profile` from chat or file extraction.
- Trust client-side confirmation only.
- Trust request-body `user_id` for protected users.

### Existing profile and settings endpoints

Existing:

- `GET /api/v1/rico/profile`
- `PATCH /api/v1/rico/profile`
- `GET /api/v1/rico/settings/saved-searches`
- `POST /api/v1/rico/settings/saved-searches`
- `DELETE /api/v1/rico/settings/saved-searches/{id}`
- `src/api/routers/settings.py`
- `src/services/settings_service.py`

Reuse:

- Conversational profile/settings updates should produce `proposed_changes` first.
- Save after approval through existing validated endpoints/services where possible.
- Keep profile/settings pages as fallback.

Do not:

- Delete settings/profile pages early.
- Duplicate settings persistence.

### Existing upload/CV pipeline

Existing:

- `POST /api/v1/rico/upload-cv`
- `POST /api/v1/rico/confirm-cv-profile`
- Upload currently enforces 10 MB max.
- Upload currently accepts PDF only by magic bytes.
- CV parse runs through `chat_service.parse_cv()` in executor.
- CV confirmation builds profile updates after user confirmation.
- Identity docs are rejected.
- Company profile is detected/rejected as not a CV.
- Document record save exists for confirmed CVs.

Reuse:

- Keep `upload-cv` stable for existing CV onboarding.
- Build universal intake beside it or evolve it carefully with backward-compatible behavior.
- Reuse parser classification hints: `document_type`, `extraction_quality`, `extracted_chars`, warnings.
- Reuse confirm-before-save pattern from CV profile confirmation.

Do not:

- Force non-CV uploads through CV-only parsing.
- Remove PDF CV support.
- Echo identity document content.

## Current gaps

These are the gaps to close in order:

1. No canonical `agentic_ui` envelope in backend chat response.
2. Frontend chat does not render action cards as first-class UI.
3. Existing `options` / `next_actions` are not yet the polished action-card layer.
4. Upload is CV/PDF-centric, not universal career intake.
5. No attachment purpose classifier for screenshots/files.
6. No `attachment_analysis` response structure.
7. No proposed-changes card for conversational settings/profile updates.
8. Permission prompts are not yet a reusable chat UI primitive.
9. Approval queue is not yet a first-class UI/state model.
10. Sidebar/pages are still the main workflow instead of chat-first operating surface.

## Required task breakdown

### CAREER-OS-01 — Agentic response contracts

Branch: `feat/career-os-01-agentic-contracts`

Goal:
Add optional backend/frontend contracts for `agentic_ui`.

Build:

- Backend Pydantic models:
  - `RicoChatAction`
  - `RicoPermissionRequest`
  - `RicoProgressStep`
  - `RicoProposedChange`
  - `RicoAttachmentAnalysis`
  - `RicoAgenticUi`
- Optional `agentic_ui` field on `RicoChatResponse`.
- Frontend Zod schema for the same optional field.

Reuse:

- `src/schemas/chat.py`
- `apps/web/lib/schemas/index.ts`

Acceptance:

- Old responses validate unchanged.
- New `agentic_ui` serializes cleanly.
- No runtime behavior change.
- No DB migration.

### CAREER-OS-02 — Chat action-card renderer

Branch: `feat/career-os-02-action-cards`

Goal:
Render `agentic_ui.actions` in the existing chat/command surfaces.

Build:

- `ChatActionsRow`
- `ChatActionCard`
- Safe handler for action kinds:
  - `navigate`
  - `chat_continue`
  - `open_drawer` as disabled/no-op until supported
- Unknown/high-impact actions must not execute.

Reuse:

- Current chat message rendering.
- Existing frontend API types.

Acceptance:

- Existing chat UI still works without `agentic_ui`.
- Action cards render on messages that include actions.
- Mobile layout does not overlap composer/bottom nav.

### CAREER-OS-03 — First real safe actions from Rico

Branch: `feat/career-os-03-job-actions`

Goal:
Start returning safe action cards from backend for job/profile/CV responses.

Build actions for:

- Job results:
  - View jobs
  - Save search
  - Tailor CV
  - Draft cover letter
- Incomplete profile:
  - Complete profile
  - Upload CV/file
  - Review missing fields
- CV upload success:
  - Review parsed profile
  - Find matching jobs

Reuse:

- Existing `matches`, `next_actions`, `options` logic where applicable.
- Existing routes for jobs/profile/upload.

Acceptance:

- No apply execution.
- No profile/settings mutation.
- Old response remains readable if frontend ignores `agentic_ui`.

### CAREER-OS-04 — Universal career intake phase 1

Branch: `feat/career-os-04-universal-intake`

Goal:
Add non-CV upload awareness and first attachment analysis structure.

Build:

- `RicoAttachmentPurpose` enum:
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
- `attachment_analysis` response.
- Classifier service, initially heuristic and conservative.
- Preserve current PDF CV flow.
- Add a universal intake path only when safe.

Reuse:

- `src/cv_parser.py`
- `chat_service.parse_cv()`
- current upload auth/session resolution
- current CV confirmation path

Acceptance:

- CV PDF upload still works.
- Non-CV file does not get saved as profile.
- Job post/recruiter/public-comment style documents return analysis and next actions.
- Unknown documents ask a clarifying question.

### CAREER-OS-05 — Conversational proposed changes

Branch: `feat/career-os-05-proposed-changes`

Goal:
Let Rico collect settings/profile updates through chat but save only after review.

Build:

- Proposed-changes backend object.
- Proposed changes frontend card.
- Initial fields:
  - target roles
  - preferred cities
  - minimum salary
  - language preference
  - search filters

Reuse:

- existing `PATCH /api/v1/rico/profile`
- settings service/router
- role normalization validators
- matching guardrail warnings

Acceptance:

- User can say: `خلي بحثي دبي والشارقة والراتب 15000`.
- Rico shows before/after values.
- Save only happens after explicit approval.
- Cancel causes no write.

### CAREER-OS-06 — Permission prompts

Branch: `feat/career-os-06-permission-prompts`

Goal:
Make approval prompts reusable for high-impact actions.

Build:

- `PermissionPromptCard`.
- Backend permission request object returned in chat.
- Approval execution path with server-side validation.
- First high-impact action: apply approval.

Reuse:

- `agent_runtime.handle_action()`
- `src/rico_safety.py`
- existing audit/idempotency repo

Acceptance:

- Apply cannot execute without confirmation.
- Confirmation must be server-side.
- Audit log records action.

### CAREER-OS-07 — Approval queue

Branch: `feat/career-os-07-approval-queue`

Goal:
Create queue for pending high-impact actions.

Build:

- Pending action state model.
- Drawer/page for approval queue.
- Approve/reject/update status.
- Migration only if needed and reviewed separately.

Reuse:

- existing audit/action semantics.
- existing application/job lifecycle where possible.

Acceptance:

- Pending actions survive reload if persistence is implemented.
- Approve/reject modifies status correctly.
- Execution still goes through runtime.

### CAREER-OS-08 — Chat-first shell and sidebar demotion

Branch: `feat/career-os-08-chat-first-shell`

Goal:
Make Rico chat the default operating surface.

Build:

- Chat-first landing for logged-in users.
- Sidebar reduced to lightweight context/status/escape hatch.
- Profile/settings/jobs/applications remain available as fallback/deep links.
- Universal upload in the chat composer.

Acceptance:

- New user can onboard through chat.
- Existing user can update preferences through chat.
- Non-CV screenshot/file flow starts in chat.
- Mobile smoke passes.

## Claude next command

After PR #670 is merged or explicitly accepted, start only with CAREER-OS-01:

```text
Rico mode. Start CAREER-OS-01 only on branch feat/career-os-01-agentic-contracts. Read AI_WORKSPACE/START_HERE.md, CLAUDE.md, AI_WORKSPACE/OPERATING_RULES.md, docs/architecture/agentic-ui-action-layer.md, and AI_WORKSPACE/HANDOFFS/2026-06-20-rico-career-os-roadmap.md. Reuse existing RicoChatResponse in src/schemas/chat.py and frontend RicoChatResponseSchema in apps/web/lib/schemas/index.ts. Add optional agentic_ui contracts only. No frontend renderer, no DB migration, no behavior change. Add backward-compatibility tests. Return changed files, commands run, test results, risks, and rollback plan.
```

## Stop conditions

Stop and report before coding if:

- Current `main` changed these files materially.
- PR #668 workspace sync conflicts with this roadmap.
- Existing chat response schema already added `agentic_ui`.
- Existing upload flow is being changed by another open PR.
- A change would require deleting or rewriting existing stable chat/upload/action runtime paths.
