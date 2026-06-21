# Handoff — Rico Career OS Roadmap: Reconciled Status (2026-06-21)

Date: 2026-06-21
Owner: Roben / Claude
Status: status reconciliation against live code (the 2026-06-20 roadmap handoff did not track build progress)

## Why this exists

The roadmap in `2026-06-20-rico-career-os-roadmap.md` lists milestones CAREER-OS-01..08 as if
unstarted. In reality most are already implemented in `main`. This doc records the **verified**
state so future work doesn't rebuild shipped features. Each row below was confirmed by reading the
actual files (not the roadmap's hypothetical names).

## Verified milestone status

| # | Milestone | Status | Evidence (files) |
|---|---|---|---|
| 01 | Agentic response contracts | ✅ **done** | `src/schemas/chat.py` (RicoChatAction, RicoPermissionRequest, RicoProgressStep, RicoProposedChange, RicoAttachmentAnalysis, RicoAgenticUi + enums; `agentic_ui` on RicoChatResponse); `apps/web/lib/schemas/index.ts` (RicoAgenticUiSchema etc.) |
| 02 | Chat action-card renderer | ✅ **done** | `apps/web/components/ui/rico/ChatActionCard.tsx` (`ChatActionsRow`), rendered in `apps/web/app/command/page.tsx` |
| 03 | Safe job/profile/CV actions | ✅ **done** | `src/services/agentic_ui_composer.py::compose()` builds `RicoAgenticUi`; populated in `src/rico_chat_api.py` |
| 04 | Universal intake / attachment analysis | 🟡 **partial — the one real gap** | backend classifier `src/services/document_classifier.py` exists; composer passes `attachment_analysis` through **only if populated**, but no handler populates it into chat responses; **no frontend render** for `attachment_analysis` (schema exists, no card) |
| 05 | Conversational proposed-changes | ✅ **done** | backend `proposed_changes=...` (`rico_chat_api.py`); `apps/web/components/ui/rico/ProposedChangeCard.tsx` |
| 06 | Permission prompts | ✅ **done** | `src/services/permission_factory.py` (`build_apply_permission_request`); `apps/web/components/ui/rico/PermissionRequestCard.tsx`; wired via `executePermissionAction` / `handlePermissionApprove` in `command/page.tsx` |
| 07 | Approval queue | ✅ **built** | `apps/web/app/queue/page.tsx` + `components/queue/ApplicationDraftCard.tsx`; `getApplicationQueue` / `approveApplication` API |
| 08 | Chat-first shell | ✅ **done (default)** | `apps/web/app/page.tsx` `router.replace("/command")` makes chat the default surface; rico dock/island components present |

## The remaining gap (fact, not recommendation)

**CAREER-OS-04 universal intake is the only milestone not end-to-end.** To complete it:
- Backend: wire `document_classifier.classify_document()` into the upload/chat path so non-CV
  uploads emit `attachment_analysis` (purpose + summary + warnings) on the chat response's
  `agentic_ui`, without ever silently writing to profile/settings (per safety rules — file-derived
  data must be confirm-first).
- Frontend: add an attachment-analysis card under `apps/web/components/ui/rico/` and render it in
  `command/page.tsx` beside the existing permission/proposed-change cards.

Everything else in the roadmap (01–03, 05, 06, 07, 08) is shipped.

## Safety constraints that still bind any CAREER-OS work

- No high-impact action executes from the frontend alone; approvals go through
  `/api/v1/rico/actions/execute` → `agent_runtime.handle_action()`.
- Do not bypass `src/rico_safety.py`.
- File/CV-derived data must never silently update profile/settings (confirm-first).
- Extend `RicoChatResponse` / `RicoAgenticUiSchema` additively; keep legacy fields and
  `extra="allow"` / `.passthrough()`.

## Method note

This reconciliation was done by reading live files. The roadmap's hypothetical component names
(e.g. `PermissionPromptCard`) differ from the shipped names (`PermissionRequestCard`); always grep
the actual `apps/web/components/ui/rico/` directory and `src/services/` before assuming a gap.
