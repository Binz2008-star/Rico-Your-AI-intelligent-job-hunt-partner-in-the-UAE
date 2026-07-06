---
name: check-rico-pr
description: Prepare and review a Rico Hunt PR. Check branch scope, diff size, commit style, tests, build, and CI readiness per AGENTS.md and CLAUDE.md rules.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
---

# check-rico-pr

Prepare and review a Rico Hunt PR. This skill is **read-only** — it reports issues and gives a checklist, but it does not commit, push, merge, or deploy.

## PR checklist

Before creating the PR, verify each item:

### 1. Scope
- [ ] One task = one branch = one PR.
- [ ] No mixing of bug fixes, features, refactors, docs, deploys, or billing changes.
- [ ] Diff is small and focused (prefer < 150 changed lines for lightweight review).

### 2. Branch and commits
- [ ] Branch is from latest `main`.
- [ ] Commit messages explain "why", not just "what".
- [ ] No sensitive info (secrets, tokens, env values) in commits.

### 3. Tests and build
- [ ] Backend: run focused pytest tests for the changed area.
- [ ] Frontend: `cd apps/web && npm run build` passes.
- [ ] No new failing tests introduced (except known pre-existing failures).

### 4. Code review
- [ ] No pseudo-code or placeholder implementations.
- [ ] No unrelated files touched.
- [ ] Auth/safety/DB changes follow AGENTS.md rules.
- [ ] Product generalization: fix is global, not special-cased to one user.

## Commands to run

```bash
# Latest main
bash -c "git fetch origin main && git log --oneline -5"

# Diff size and files
git diff --stat main...HEAD
git diff --name-only main...HEAD

# Recent commits
git log --oneline -10
```

## If the user asks to create the PR

1. Ensure all checklist items pass.
2. Use `gh pr create` with the standard Rico body (Summary, Test plan, Generated with Devin).
3. Do not auto-merge or push without explicit approval.

## Safety constraints

- Never run `git push --force`, `git merge`, or `gh pr merge` without explicit approval.
- Never deploy from this skill.
- Never mutate Neon, Stripe, or any production service.
- If the diff is too large or mixes unrelated changes, stop and ask the user to split it.
