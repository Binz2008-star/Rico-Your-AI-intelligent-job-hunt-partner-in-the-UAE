# Prompt Contract

Use this contract for every AI-assisted Rico task.

## Required inputs

Every task brief must include:

- goal
- branch
- files in scope
- files out of scope
- relevant architecture notes
- constraints
- acceptance criteria
- required verification
- expected output format

## Product generalization requirement

Every Rico task must treat smoke-test findings as evidence of product behavior, not as product logic.

A task brief must state the affected scope:

- one user state
- one profile state
- one language or locale
- one provider or integration
- all users

Implementation must fix the underlying product/system behavior and must not special-case one sampled state, one role list, one saved search, one session state, or one smoke-test dataset.

Required verification should use synthetic users and synthetic profile data unless the owner explicitly approves a production smoke check. Where relevant, include English, Arabic, complete-profile, no-profile/no-CV, and guest/public-session coverage.

If a proposed fix only improves one sampled state or one smoke-test dataset, the task is invalid and must stop before coding.

## Model roles

- ChatGPT: planning, decomposition, review, rewrite, prompt normalization.
- Perplexity: research, fact-checking, external comparison, architecture critique.
- Claude: implementation and long-context refactors inside a bounded task.
- Codex: isolated repo execution, parallel branches, tests, and mechanical code changes.
- Human owner: final product and release decision.

## Branch ownership

Only one model or human writes to a branch for a given task. Other tools may review, test, or critique, but should not edit the same branch unless ownership is transferred in `TASKS.md`.

## Avoid vague requests

Every request must include the current goal, current files, current constraints, and done criteria.

## Required output format

```md
## Summary
<what changed>

## Changed files
- path: reason

## Verification
- command: result

## Risks
- ...

## Rollback
<how to revert safely>

## Open questions
- ...
```

## Done criteria

A handoff is not complete until it includes:

- exact files changed
- commands run
- test results or reason tests were not applicable
- risks
- rollback plan
- no-scope-creep confirmation
- product-generalization confirmation
