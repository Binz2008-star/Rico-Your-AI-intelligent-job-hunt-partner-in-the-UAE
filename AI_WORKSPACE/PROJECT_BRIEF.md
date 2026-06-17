# Rico AI Project Brief

## Product

Rico AI is a UAE-focused career companion. It should stay focused on job seekers, explainable opportunity matching, honest applications, and controlled user-approved actions.

## Owner

Roben Edwan is the product owner and final decision-maker for product direction, roadmap priority, release readiness, and production acceptance.

## Shared source of truth

This folder is the shared operating workspace for AI tools and human contributors.

All planning, execution, review, and verification must anchor to these files instead of chat memory:

- `AI_WORKSPACE/PROJECT_BRIEF.md`
- `AI_WORKSPACE/ARCHITECTURE.md`
- `AI_WORKSPACE/CURRENT_STATE.md`
- `AI_WORKSPACE/TASKS.md`
- `AI_WORKSPACE/DECISIONS.md`
- `AI_WORKSPACE/PROMPT_CONTRACT.md`
- `AI_WORKSPACE/HANDOFFS/`
- `AI_WORKSPACE/EVALS/`

## Operating rule

Every task must include current files, current branch, constraints, acceptance criteria, required tests, risks, and rollback notes.

## Production posture

Treat every change as production work. Prefer small, bounded PRs with one objective, explicit ownership, and verifiable evidence.
