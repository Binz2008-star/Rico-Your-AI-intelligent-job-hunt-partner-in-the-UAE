# Handoff — Career OS after PR #673

Date: 2026-06-20
Status: Workspace sync after #673 merge and #674 issue creation

## Current main milestone

PR #673 was merged into main.

- PR: #673
- Title: `feat(career-os): Permission Engine — agentic UI bridge, TTL permission store, backend safety hardening`
- Merge commit: `ef5f70da748f5d19e11f0f617faa7adc1773f0df`
- Head SHA before merge: `59c8f4acf4114dbd833868922536c0fa3739208c`
- Vercel status on merge commit: success
- Backend deployment status: not confirmed in this handoff; verify Render before claiming production-live backend behavior.

## What #673 added

#673 completed CAREER-OS-02 + CAREER-OS-03 + CAREER-OS-04 foundation:

- Action-card rendering foundation
- `PermissionRequestCard`
- `executePermissionAction()` client helper
- `POST /api/v1/rico/actions/execute`
- `EXECUTE_ALLOWED_ACTIONS` allowlist in backend and frontend schemas
- `pending_permissions` TTL in-memory permission store
- `agentic_ui_composer` bridge from `RuntimeResult.data` to `RicoChatResponse.agentic_ui`
- `permission_factory` registering server-side permission IDs
- `agent_runtime.handle_action(pre_approved=True)` approval path
- `_approved` sentinel injected into local job copy only
- audit source pattern: `permission:{permission_id}`

## Safety invariants to preserve

Do not regress these:

- `user_id` must come from JWT/session, not request body.
- `rico_safety.py` must not be bypassed.
- `agent_runtime.handle_action()` remains the execution boundary for job actions.
- `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` remains respected on non-execute paths.
- `permission_id` must be server-pinned, TTL-limited, and one-time-use.
- Unknown/admin actions must be rejected before reaching runtime.
- `_approved` must never persist into DB job records.

## Production observation after #673

Manual mobile smoke on `ricohunt.com` showed that the CV upload surface still treats arbitrary PDFs as resumes.

Observed behavior:

1. User uploaded a random PDF that was not a CV.
2. Rico entered the CV extraction/profile-preview flow anyway.
3. Extracted fields were blank and quality was `poor`.
4. Rico still offered `Use this file` / CV-profile flow.

This is a product architecture issue: Rico still behaves like upload means CV. Career OS requires upload to mean career-intelligence intake.

## New issue created

Issue #674 was created:

`CAREER-OS-06 — Universal Document Intelligence (Architecture Direction)`

Purpose:

- Add a document classification layer before any pipeline runs.
- Prevent non-CV documents from entering the CV parser/profile-update flow.
- Route uploads by document type and confidence.
- Use `attachment_analysis` / agentic UI as the response carrier.
- Treat every uploaded file as a Workspace Object candidate.

## Required next implementation direction

The next product-code work should not be more action buttons. It should address upload routing.

Recommended next branch:

```text
feat/career-os-06-document-intelligence
```

Recommended scope for phase 1:

- Add `src/services/document_classifier.py`.
- Classify uploaded files before CV extraction.
- If `document_type != cv_resume` or confidence is below threshold, do not call CV profile preview.
- Return a chat/card response explaining detected document type and suggested safe actions.
- Keep existing CV upload flow working for actual CV PDFs.
- No DB migration in phase 1.
- Use `attachment_analysis` if possible; otherwise return backward-compatible metadata while preserving existing response shape.

## Acceptance criteria for #674 phase 1

- Uploading a valid CV still shows CV preview.
- Uploading a non-CV PDF does not show `Use this file` as a CV.
- Uploading a non-CV PDF produces document-type classification and confidence.
- Low-confidence documents ask the user what to do next.
- Identity-like documents are treated conservatively and do not echo sensitive data unnecessarily.
- Tests cover valid CV, non-CV PDF, unknown document, and low-confidence classification.

## Do not forget later Career OS layers

After document intelligence, the larger roadmap remains:

1. Universal Document Intelligence (#674)
2. Workspace Objects: CVs, Jobs, Applications, Files, Approvals, Receipts, Tasks, Timeline
3. Career Memory: explicit preferences, behavioral signals, session/task memory
4. Confidence layer: per plan, per action, per important statement when useful
5. Receipts after every high-impact action
6. Timeline and audit UI
7. Sidebar/page demotion after chat-first flows are reliable

## Recommended Claude prompt for next coding session

```text
Rico mode. Start CAREER-OS-06 only on branch feat/career-os-06-document-intelligence. Read AI_WORKSPACE/START_HERE.md, CLAUDE.md, AI_WORKSPACE/OPERATING_RULES.md, AI_WORKSPACE/HANDOFFS/2026-06-20-career-os-post-673-handoff.md, and issue #674. Implement phase 1 only: classify uploads before the CV pipeline. Do not add DB migrations. Do not change permission engine behavior. Preserve valid CV upload behavior. If document_type is not cv_resume or confidence is low, stop the CV pipeline and return a safe classification/clarification response. Add tests. Return changed files, commands run, test results, risks, rollback plan, and whether PR is draft or ready.
```
