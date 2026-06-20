# Rico Career OS Roadmap — Handoff 2026-06-20

## What is Career OS?

Career OS is Rico's evolution from a job-search assistant into a structured
career operating layer. Instead of returning only chat text, Rico will return
structured UI hints (`AgenticUIContract`) that drive richer frontend components:
job cards, action buttons, confirmation dialogs, dashboard tiles.

CAREER-OS-01 lays the foundation: schema contracts, no renderer, no behavior change.

## Completed: CAREER-OS-01 — Agentic UI Contracts

Branch: `claude/career-os-agentic-contracts-hddsld`

### What changed

| File | Change |
|---|---|
| `src/schemas/chat.py` | Added `AgenticUIActionContract`, `AgenticUIComponentContract`, `AgenticUIContract` Pydantic models. Added optional `agentic_ui` field to `RicoChatResponse`. |
| `apps/web/lib/schemas/index.ts` | Added `AgenticUIActionContractSchema`, `AgenticUIComponentContractSchema`, `AgenticUIContractSchema` Zod schemas. Added `agentic_ui` optional field to `RicoChatResponseSchema`. Added type exports. |
| `docs/architecture/agentic-ui-action-layer.md` | New architecture spec for the agentic UI action layer. |
| `tests/test_career_os_01_agentic_contracts.py` | New backward-compatibility and structural tests. |
| `AI_WORKSPACE/HANDOFFS/2026-06-20-rico-career-os-roadmap.md` | This file. |

### What was NOT changed

- No frontend renderer
- No database migration
- No new API routes
- No behavior change to any chat service
- No new environment variables

### Rollback

Revert the PR. No SQL needed. No deployed env vars to unset. The `agentic_ui`
field defaults to `None` and was never read by any production code path.

## Next Tasks

### CAREER-OS-02 — Frontend Contract Renderer (not started)

Implement a renderer in the chat UI that reads `agentic_ui` and renders
structured components when present, falling back to text when absent.

Files to touch: `apps/web/app/chat/page.tsx`, new component files.
Constraint: fallback to `message` text must remain the default.

### CAREER-OS-03 — Rico Backend Contract Emitter (not started)

Update `src/rico_chat_api.py` or `src/services/chat_service.py` to populate
`agentic_ui` on job-search responses (e.g. when `intent == "job_search"`).

Constraint: must not alter the `message` field or any existing field.
Must be behind a feature flag or intent-gated to avoid regressions.

### CAREER-OS-04 — Agent Chat Contract Unification (not started)

Align `AgentUIResponseSchema` (existing `/agent/chat` endpoint) with the new
`AgenticUIContract` shape so there is one contract across both routes.

## Risk Notes

- The existing `AgentUIResponseSchema` / `AgentUIComponentSchema` in the frontend
  is for `/api/v1/agent/chat`. The new `AgenticUIContractSchema` is for
  `/api/v1/rico/chat` and `/api/v1/rico/chat/public`. These are separate until
  CAREER-OS-04.
- `version="1"` must be incremented on breaking changes so renderers can detect
  schema incompatibilities.
