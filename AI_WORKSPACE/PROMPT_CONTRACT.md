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

## Product Generalization Rule

Rico is a global SaaS product for all users. Smoke-test findings are evidence of product behavior; they are not product logic.

Every fix must be:

- global
- user-agnostic
- data-driven
- tested with synthetic users where possible

Do not special-case:

- one live user account
- one owner/test account
- one profile state
- one target-role list
- one saved search
- one session state
- one language path
- one provider result set
- one smoke-test dataset

For every investigation or fix, identify the affected scope:

1. one user only
2. one profile state
3. one language or locale
4. one provider or integration
5. all users

Fix the underlying product/system behavior, not one account.

If a bug is discovered through a smoke-test account, the report must state:

> The smoke-test account exposed the bug, but the fix is global.

If a proposed fix only improves one live account or one sampled dataset, stop and mark it invalid.

Use synthetic users and synthetic profile data unless the owner explicitly approves production smoke testing.

Where relevant, cover:

- complete-profile user
- no-profile / no-CV user
- guest/public session
- Arabic input
- English input
- multiple unrelated target roles, not only the role that exposed the bug

## Required output format

```md
## Summary
<what changed>

## Changed files
- path: reason

## Verification
- command: result

## Affected scope
<one user / one profile state / one language / one provider / all users>

## Product generalization
- affected scope confirmed
- fix is global and user-agnostic
- synthetic users used: yes / no / n-a
- no owner-account special-casing: confirmed

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
- affected scope
- product-generalization confirmation (fix is global and user-agnostic)
- whether synthetic users were used
- no owner-account special-casing confirmation
- risks
- rollback plan
- no-scope-creep confirmation
