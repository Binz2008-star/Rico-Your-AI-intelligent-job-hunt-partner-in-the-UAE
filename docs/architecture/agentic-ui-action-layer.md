# Agentic UI Action Layer — CAREER-OS-01

## Purpose

Adds an optional `agentic_ui` field to `RicoChatResponse` so Rico chat
responses can carry structured UI hints alongside the plain text `message`.
Future renderers consume these hints to display richer components (job cards,
action buttons, etc.) without breaking existing consumers that only read `message`.

## Design decision — reuse `AgentUIResponse`

The `/agent/chat` route already defined `AgentUIResponse` (+ `AgentUIComponent`,
`AgentAction`, `AgentUIType`, `ActionStyle`) in `src/schemas/agent.py` and the
matching Zod schemas in `apps/web/lib/schemas/index.ts`. Rather than introduce
parallel types, `agentic_ui` is typed as `Optional[AgentUIResponse]` on the
Python side and `AgentUIResponseSchema.optional()` on the TypeScript side.

## Contract structure

```
RicoChatResponse
└── agentic_ui: AgentUIResponse | None   (optional, default None)
    ├── message: str        (summary text for the UI block; may duplicate outer message)
    ├── ui: AgentUIComponent | None
    │   ├── type: AgentUIType   ("job_list" | "job_detail" | "stats" | "confirm" | ...)
    │   ├── title: str | None
    │   └── data: dict
    ├── actions: list[AgentAction]
    │   ├── action_id: str
    │   ├── type: str       ("apply" | "save" | "skip" | "view_detail" | ...)
    │   ├── label: str
    │   ├── style: "primary" | "secondary" | "danger"
    │   ├── job_id: str | None
    │   ├── job: dict | None
    │   └── metadata: dict
    ├── tool_used: str | None
    ├── execution_time_ms: int
    └── success: bool
```

## Source files

| Layer | File | Symbol |
|---|---|---|
| Python schema | `src/schemas/agent.py` | `AgentUIResponse` (existing) |
| Python consumer | `src/schemas/chat.py` | `RicoChatResponse.agentic_ui` (new field) |
| TypeScript schema | `apps/web/lib/schemas/index.ts` | `AgentUIResponseSchema` (existing) |
| TypeScript consumer | `apps/web/lib/schemas/index.ts` | `RicoChatResponseSchema.agentic_ui` (new field) |
| Tests | `tests/test_career_os_01_agentic_contracts.py` | backward-compat suite |

## Backward compatibility

- `agentic_ui` defaults to `None` — every existing response path is unaffected.
- `RicoChatResponse` already carries `extra="allow"` so unknown future fields pass through.
- `AgentUIResponseSchema` in TypeScript does not use `.passthrough()`, but since
  `agentic_ui` is optional, consumers that ignore it are unaffected.

## What this task does NOT include

- No frontend renderer (CAREER-OS-02+)
- No database migration
- No new API routes
- No behavior change to any existing chat service
- No new environment variables

## Rollback

Revert this PR. No migration SQL needed. No env vars to change.
The field is never read by any production code path.
