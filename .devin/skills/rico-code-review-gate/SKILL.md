---
name: rico-code-review-gate
description: Review Rico Hunt PRs and diffs for correctness, scope, safety, and production readiness. Distinguishes verified facts from assumptions.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
  - mcp1
---

# rico-code-review-gate

## Purpose
Inspect a PR or diff for correctness, scope, safety, and production readiness. Report findings as `verified`, `assumption`, or `suggestion` and never mix them. `AI_WORKSPACE` is the source of truth; GitHub state is live data, not the source of truth.

## When to use
- Before a PR is marked ready.
- Before the owner is asked to merge.
- When the user asks "review this", "is this safe", or "what did I miss".

## Inputs required
- PR number, branch, or diff.
- Objective and acceptance criteria.
- Changed files list.

## Allowed actions
- Read the diff and the changed files.
- Read `AGENTS.md`, `CLAUDE.md`, and relevant tests.
- Run focused tests and build/lint if the branch is local.
- Use `mcp1` to fetch PR/review comments from GitHub.
- Categorize findings as `verified`, `assumption`, or `suggestion`.
- Request clarification on ambiguous scope.

## Forbidden actions
- Merge, approve, or close the PR.
- Modify the branch under review.
- Run production smoke or external API calls.
- Treat a guess as a verified fact.
- Expand scope or ask for unrelated changes.

## Required output format
```markdown
### Code review gate for <PR/branch>

- **Scope:** ...
- **Verified facts:** ...
- **Assumptions needing confirmation:** ...
- **Critical risks:** ...
- **Must-fix:** ...
- **Should-fix:** ...
- **Test results:** ...
- **Recommendation:** approve / revise / block / cannot-review
- **Stop conditions:** ...
```

## Stop conditions
- Critical auth, safety, or data issue found.
- Secrets or credentials in the diff.
- Diff includes unrelated changes.
- CI is not green.
- The PR is still a draft and the user asks for merge readiness.

## Example prompt
"Rico code review gate for PR #970: review the diff, run focused tests, and flag any auth or scope issues."
