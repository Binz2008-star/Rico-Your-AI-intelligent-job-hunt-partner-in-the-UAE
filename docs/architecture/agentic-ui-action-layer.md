# Agentic UI Action Layer — CAREER-OS-01

## Purpose

This document specifies the `AgenticUIContract` schema that Rico chat responses may optionally carry to hint at richer UI rendering beyond plain text.

The contract is **opt-in and additive**: every existing response path that omits `agentic_ui` continues to work unchanged. Renderers that do not know about the field ignore it. This allows progressive adoption without forcing a coordinated frontend/backend cutover.

## Motivation

Rico currently returns chat responses as text (`message`) plus lightweight arrays (`matches`, `options`, `next_actions`). For Career OS — a richer job-search operating surface — the frontend needs to render structured components: job cards, action button bars, confirmation dialogs, profile summaries. The `AgenticUIContract` provides a version-stamped envelope for these hints.

## Contract Structure

```
RicoChatResponse
└── agentic_ui: AgenticUIContract | None  (optional)
    ├── version: str  ("1")
    ├── primary_action: AgenticUIActionContract | None
    └── components: AgenticUIComponentContract[]
        ├── component: str  (e.g. "job_card", "job_list", "text_block", "action_bar")
        ├── title: str | None
        ├── data: dict  (component-specific payload)
        └── actions: AgenticUIActionContract[]
            ├── action_id: str
            ├── type: str  (e.g. "apply", "save", "skip", "navigate", "send_message")
            ├── label: str
            ├── style: "primary" | "secondary" | "danger"
            ├── job_id: str | None
            ├── href: str | None
            └── payload: dict
```

## Source Files

| Layer | File |
|---|---|
| Python schema | `src/schemas/chat.py` — `AgenticUIActionContract`, `AgenticUIComponentContract`, `AgenticUIContract` |
| TypeScript schema | `apps/web/lib/schemas/index.ts` — `AgenticUIActionContractSchema`, `AgenticUIComponentContractSchema`, `AgenticUIContractSchema` |
| Backward-compat tests | `tests/test_career_os_01_agentic_contracts.py` |

## Versioning

`version` is a string field (currently `"1"`) on `AgenticUIContract`. Future schema changes that would break existing renderers must increment this value. Renderers should check `version` before attempting to read `components` or `primary_action`.

## Known Component Types (v1)

| component | data shape | description |
|---|---|---|
| `text_block` | `{ text: str }` | fallback plain-text block |
| `job_card` | `{ job: JobDict }` | single job summary card |
| `job_list` | `{ jobs: JobDict[] }` | list of job cards |
| `profile_card` | `{ profile: ProfileDict }` | user profile summary |
| `action_bar` | `{}` | row of action buttons (see actions[]) |
| `confirmation_dialog` | `{ prompt: str }` | confirm / cancel dialog |
| `stats_summary` | `{ stats: StatsDict }` | dashboard stats tile |
| `onboarding_step` | `{ step: int, total: int }` | onboarding progress indicator |

## Known Action Types (v1)

| type | notes |
|---|---|
| `send_message` | sends a preset message back to Rico chat |
| `apply` | triggers apply flow for `job_id` |
| `save` | saves job `job_id` |
| `skip` | skips job `job_id` |
| `navigate` | client-side router push to `href` |
| `confirm` | confirms a pending high-impact action |
| `cancel` | cancels a pending high-impact action |

## Backward Compatibility Rules

1. All three new Pydantic models carry `model_config = ConfigDict(extra="allow")` — unknown fields from future versions pass through without validation errors.
2. `agentic_ui` defaults to `None` on `RicoChatResponse` — no existing code path is affected.
3. The TypeScript `AgenticUIContractSchema` and all sub-schemas use `.passthrough()` for the same reason.
4. The frontend `RicoChatResponseSchema` adds `agentic_ui` as `.optional()` — existing call sites that destructure the response without `agentic_ui` continue to work.

## What This Task Does NOT Include

- No frontend renderer (CAREER-OS-02+)
- No database migration
- No new API routes
- No change to existing chat service behavior
- No rollout env var required

## Rollback

Revert this PR. No migration SQL needed. No deployed env var to unset. The field was never read by any production code path.
