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

### DEC-20260621-002 — Align approval TTL before wiring `/ask` to real execution

Status: accepted
Date: 2026-06-21
Owner: Roben / Claude / ChatGPT
Related task: next implementation PR

#### Context
PR #700 hardened permission binding and denial auditing. `/ask` presents a 300-second approval countdown, while the backend permission store currently uses a 900-second TTL.

#### Decision
The next foundation PR should align backend approval permission TTL to the user-facing 300-second approval window before `/ask` is wired to real backend execution.

#### Consequences
- Positive: user-facing expiry and server-side acceptance match; fewer confusing approval states.
- Trade-off: shorter approval windows may require users to re-approve more often.

#### Follow-up
- [ ] Open `feat/permission-ttl-alignment` as a backend/tests-only PR.
- [ ] Verify expired permissions fail after 300 seconds.
- [ ] Keep PR free of DB migrations, frontend changes, and new parallel approval/audit systems.

### DEC-20260621-001 — Extend existing CAREER-OS approval/audit systems instead of duplicating them

Status: accepted
Date: 2026-06-21
Owner: Roben / Claude / ChatGPT
Related task: PR #700, PR #701, PR #702

#### Context
The GitHub Intelligence report proposed new approval-token and audit-event components. Code inspection showed Rico already has production foundations: `pending_permissions`, `permission_factory`, `/actions/execute`, `audit_repo`, `action_audit_log`, and deterministic match explanation logic.

#### Decision
Rico will harden and extend the existing CAREER-OS permission/audit path before creating any new approval-token table, audit-event table, or policy-gate module. New parallel systems are rejected unless a focused audit proves the existing system cannot be safely extended.

#### Consequences
- Positive: avoids duplicate systems, reduces migration risk, and keeps production behavior reviewable.
- Trade-off: future richer operational memory may still require an additive schema decision.

#### Follow-up
- [x] PR #700: bind approval permission to `job_key` and audit denials.
- [x] PR #701: ensure `action_audit_log` writes commit and persist.
- [x] PR #702: ensure application-attempt dedup writes commit and close connections.
- [ ] Update `docs/rico-agentic-vision-github-intelligence.md` so it reflects the real foundation instead of greenfield assumptions.
- [ ] Decide later whether `action_audit_log` is enough or whether an additive append-only `agent_audit_events` stream is needed.

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
