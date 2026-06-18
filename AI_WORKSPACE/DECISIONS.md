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

### DEC-20260618-001 — Close PR #601 as stale/superseded; merge docs PRs #608 and #566

Status: accepted
Date: 2026-06-18
Owner: Roben / Claude
Related task: TASK-20260618-014

#### Context
Three open PRs created backlog noise. #601 was a broad multi-batch feature PR (~1.3k LOC)
touching `src/rico_chat_api.py` on a stale base, still in draft, with an unchecked test plan
and a body/title mismatch. #608 and #566 were small, clean, docs-only additions.

#### Decision
Close #601 without merging and without opening a replacement PR. Merge the two docs-only PRs
(#608 localization pattern, #566 Gmail read-only connector design) after confirming they are
clean, docs-only, and Vercel-green. Re-cut #601's deterministic fast paths later as small,
focused PRs from current `main` only if still needed.

#### Consequences
- Positive: open PR backlog is clean (0 open PRs); design docs for localization and the
  Gmail connector (#356) are now on `main`; future fast-path work starts from a current base.
- Trade-off: the fast-path content in #601 must be re-authored against current `main` if still
  wanted — its existing diff is not reused.

#### Follow-up
- [ ] Re-cut #601 fast paths as small PRs from `main` if/when prioritised.
- [ ] Consider disabling the third-party "Continuous AI" bot checks (they error on every PR).

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
