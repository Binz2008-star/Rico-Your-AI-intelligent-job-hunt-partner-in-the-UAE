# Decisions

Use this file for decisions that affect product behavior, architecture, AI workflow, release policy, or contributor workflow.

## Decision template

```md
### DEC-YYYYMMDD-001 — <title>

Status: accepted | superseded | proposed
Date: YYYY-MM-DD
Owner: <name/tool>
Related task: TASK-YYYYMMDD-001

#### Context
<why this decision is needed>

#### Decision
<what was decided>

#### Consequences
- Positive:
- Negative/trade-off:

#### Follow-up
- [ ]
```

## Accepted decisions

### DEC-20260617-001 — Use `AI_WORKSPACE/` as the shared AI source of truth

Status: accepted
Date: 2026-06-17
Owner: Roben / ChatGPT
Related task: TASK-20260617-001

#### Context
Multiple AI tools can plan, implement, review, and verify Rico work. Without a shared repo-native context, each tool can drift based on stale chat history.

#### Decision
All multi-model work must use `AI_WORKSPACE/` as the shared source of truth for project context, active tasks, handoff briefs, decisions, and verification evidence.

#### Consequences
- Positive: less context drift, clearer PR boundaries, easier review.
- Trade-off: every contributor must update the workspace files when task state changes.

#### Follow-up
- [ ] Use the handoff template for the next implementation task.
- [ ] Keep decisions short and tied to tasks.
