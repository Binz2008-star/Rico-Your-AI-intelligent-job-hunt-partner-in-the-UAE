# Evaluation Evidence Template

Copy this file into `AI_WORKSPACE/EVALS/YYYY-MM-DD-task-slug.md` when a task reaches review or verification.

## Task

- Task ID:
- Branch:
- PR:
- Commit SHA:

## Scope Check

- [ ] One objective only
- [ ] Changed files match the task
- [ ] No unrelated files changed
- [ ] No secrets or credentials changed

## Commands Run

```bash
# command
```

Result:

```text
# paste result summary
```

## Test Evidence

- Unit tests:
- Integration tests:
- Frontend build:
- Smoke test:
- Deployment check:

## Manual Review

- Main behavior checked:
- Edge cases checked:
- Regression areas checked:

## Risks

- Risk:
- Mitigation:

## Rollback Plan

- Revert PR:
- Config rollback:
- Data rollback:

## Final Status

`blocked | review | verified | done`
