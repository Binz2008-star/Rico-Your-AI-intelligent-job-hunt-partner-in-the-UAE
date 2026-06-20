# Rico Career OS Roadmap — Handoff 2026-06-20

## What is Career OS?

Career OS is Rico's evolution from a job-search assistant into a structured
career operating layer. Instead of returning only chat text, Rico will carry
structured UI hints (`agentic_ui: AgentUIResponse`) that future frontend
renderers use to display richer components: job cards, action buttons,
confirmation dialogs, dashboard tiles.

## Completed: CAREER-OS-01 — Agentic UI Contracts

Branch: `claude/career-os-agentic-contracts-hddsld`

### What changed

| File | Change |
|---|---|
| `src/schemas/chat.py` | Import `AgentUIResponse` from `src/schemas/agent.py`; add `agentic_ui: Optional[AgentUIResponse] = None` to `RicoChatResponse` |
| `apps/web/lib/schemas/index.ts` | Add `agentic_ui: AgentUIResponseSchema.optional()` to `RicoChatResponseSchema` (reuses existing schema) |
| `docs/architecture/agentic-ui-action-layer.md` | Architecture spec |
| `tests/test_career_os_01_agentic_contracts.py` | Backward-compat tests |
| `AI_WORKSPACE/HANDOFFS/2026-06-20-rico-career-os-roadmap.md` | This file |

### Design decision

Reuses existing `AgentUIResponse` / `AgentUIResponseSchema` (already used by
`/agent/chat`). No new model classes. The shape is:
`{ message, ui: AgentUIComponent, actions: AgentAction[], success, ... }`

### What was NOT changed

- No new model classes or Zod schemas
- No frontend renderer
- No database migration
- No new API routes
- No behavior change to any chat service
- No new environment variables

### Rollback

Revert the PR. No SQL needed. No Render/Vercel env vars to change.

## Next Tasks

### CAREER-OS-02 — Frontend Renderer (not started)

Read `agentic_ui` from chat responses and render `AgentUIComponent` based on
`type` (`job_list`, `confirm`, `stats`, etc.).

Files: `apps/web/app/chat/page.tsx`, new component files under `apps/web/components/`.
Constraint: must fall back to `message` text when `agentic_ui` is absent.

### CAREER-OS-03 — Backend Emitter (not started)

Populate `agentic_ui` in `src/services/chat_service.py` or `src/rico_chat_api.py`
when `intent == "job_search"` (and other structured intents).

Constraint: must not alter `message` or other existing fields. Gate behind intent check.

### CAREER-OS-04 — Unify Agent and Rico Chat UI shapes (not started)

Both `/agent/chat` and `/rico/chat` now share `AgentUIResponse`. Validate that
the frontend renders both consistently and remove any duplicate handling.
