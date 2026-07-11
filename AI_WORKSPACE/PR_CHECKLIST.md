# AI Workspace PR Checklist

Paste this checklist into PRs that use the multi-model workspace.

## Summary

## Scope

One objective only.

## Workspace links

- Related task in `AI_WORKSPACE/TASKS.md`:
- Decision entry, if applicable:
- Handoff note, if applicable:
- Evaluation note, if applicable:

## Changed files

- `path` — reason

## Verification

- Unit tests:
- Frontend build:
- Local smoke:
- Manual smoke:
- Deployment check, if applicable:

## Review evidence

- Summary:
- Changed files:
- Verification:
- Risks:
- Rollback:
- Open questions:

## Scope confirmation

- One objective only:
- No unrelated files:
- No secrets or credentials:
- Rollback plan included:
- If this session was approaching a token/context/tool/usage/time limit,
  the Continuity Block in `AI_WORKSPACE/TASKS.md` was updated before
  stopping (see `AGENT_OPERATING_MODEL.md`, "Session continuity /
  limit-approach handoff"):

## Rico product gate

For changes touching Rico's behavior, intent routing, tools, attachments, or job
search (see `PR_QUALITY_GATE_RULES.md` → "Rico Product Behavior Gate" and
`RICO_EXECUTION_PRINCIPLES.md`):

- Answers exactly what was asked; no unrelated actions:
- No unwanted job search (`search_jobs` only on explicit intent / valid prior authorization):
- Respects the current attachment and current request first:
- Source of each important claim is known; inference treated as weakest:
- Document type is correct (CV / cover letter / invoice / offer / screenshot not confused):
- States uncertainty on low confidence instead of a hard label:
- Trust check — would this make the user trust Rico more, or less?
