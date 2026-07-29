# Rico Version Control Policy

## Purpose

This document defines Rico's enforceable Git and GitHub control model. It exists
so repository history, reviews, CI evidence, merges, releases, and rollbacks are
traceable and cannot depend on conversation memory or informal agent claims.

## Ownership and update rule

- **Owner:** Rico repository owner / Release & Operations Captain.
- **Source of truth:** this document for version-control enforcement; broader
  agent and production rules remain in `AI_WORKSPACE/OPERATING_RULES.md`.
- **Update when:** branch rules, required checks, merge strategy, reviewer model,
  release tagging, or rollback policy changes.
- **Do not duplicate:** implementation details belong in the GitHub ruleset,
  `.github/`, and the existing operating documents referenced here.

## Branch model

- `main` is the only production branch.
- No direct work is performed on `main`.
- One objective, one branch, one writer, one PR.
- Branches start from a verified current `main` SHA.
- Force-push and branch deletion are prohibited on `main`.
- Feature-branch force-push is allowed only with `--force-with-lease`, explicit
  authorization, and confirmed single-writer ownership.
- Long-lived integration branches are prohibited unless a Decision Record
  defines their owner, lifetime, reconciliation plan, and deletion date.

## Pull-request lifecycle

```text
Draft
→ scope and tests complete
→ exact-head independent review
→ exact-head CI
→ Ready
→ squash merge
→ deployment verification where applicable
→ release/rollback record
```

A PR is not Ready unless all of the following describe the same head SHA:

1. PR body and changed-file list.
2. Independent review evidence.
3. Required CI results.
4. Risk, production/data impact, and rollback plan.

Any new commit invalidates review evidence and CI evidence from the previous
head. The trusted `pr-governance` check enforces the recorded review SHA.

## Required PR record

Every ready PR must contain:

- Vision → Epic → Milestone → Phase → Task traceability.
- One objective and explicit in-scope/out-of-scope boundaries.
- Acceptance criteria.
- Changed files with reasons.
- Risk level, failure modes, mitigation, and accepted debt.
- Test and smoke evidence.
- Independent reviewer, exact reviewed SHA, and verdict.
- Production and data/migration impact.
- Rollback plan.

The canonical template is `.github/pull_request_template.md`.

## Review policy

- The author may not be recorded as the independent reviewer.
- Review verdicts are `PASS`, `PASS WITH OWNER-ACCEPTED RISK`, `FAIL`, or
  `CANNOT VERIFY`.
- Only `PASS` and `PASS WITH OWNER-ACCEPTED RISK` satisfy the ready gate.
- Findings are fixed by the author; the reviewer does not silently repair the
  author's branch.
- A review must name the exact 40-character PR head SHA.
- CODEOWNERS requests review for sensitive paths.

### Approval enforcement maturity

Rico currently has one trusted GitHub owner identity. GitHub does not allow an
author to approve their own PR, so enabling a mandatory approval count before a
second trusted reviewer identity exists would deadlock delivery rather than
improve it.

Current enforceable phase:

- exact-head independent review evidence is mandatory through `pr-governance`;
- CODEOWNERS requests the repository owner on sensitive changes;
- merge authority remains with the owner;
- self-review is rejected by policy.

Target phase after adding a second trusted GitHub maintainer or review bot with a
separate identity:

- require one approval;
- dismiss stale approvals on every push;
- require CODEOWNER review for owned paths;
- require approval of the exact current head.

## Trusted required checks

GitHub rulesets match **check-run job names**, not workflow display titles. The
`main` ruleset should require these verified job names:

1. `pr-governance`
2. `trusted-ratchet`
3. `workflow-security-guards`
4. `enumeration`
5. `frontend`
6. `pytest`
7. `postgres-integration`
8. `playwright`

Rules:

- Configure required checks only after observing each exact job name on a real
  disposable pull request. A workflow title is not a substitute for a check-run
  name.
- Require branches to be up to date before merging when the risk of base drift
  is material; otherwise exact-head checks and conflict-free mergeability remain
  mandatory.
- `Log Privacy Ratchet (advisory)` remains advisory because it evaluates the
  policy copy inside the PR.
- Vercel, Render/Railway, and production smoke evidence are release gates, not a
  substitute for code-review and test gates.
- A required policy check must run from trusted base-branch code. A PR must not
  be able to weaken the policy that judges it.

## GitHub `main` ruleset target

Apply one repository ruleset targeting `refs/heads/main`:

- Require a pull request before merging.
- Block force pushes.
- Block branch deletion.
- Require conversation resolution.
- Require linear history.
- Require the checks listed above.
- Do not allow bypass except repository owner emergency use.
- Record every bypass reason in the PR and `AI_WORKSPACE/DECISIONS.md`.
- Require one approving review and CODEOWNER review only after a second trusted
  reviewer identity is operational.

The ruleset is configured in GitHub Settings and cannot be proven by repository
files alone. Its activation must be verified from GitHub settings/API evidence.

## Merge policy

- Default merge method: **squash merge**.
- Merge commits are prohibited for normal PRs.
- Rebase merge is reserved for exceptional history-preserving work and requires
  an explicit Decision Record.
- Auto-merge is disabled unless the owner authorizes it for a specific PR after
  all gates are already satisfied.
- Merge commands must include the expected head SHA where the tool supports it.
- Never merge based on a conversation summary alone.

## Release and rollback traceability

For every production-impacting merge, record:

- merged PR and merge SHA;
- deployed SHA for each affected service;
- `/version` and `/health` evidence;
- migration state and reconciliation where applicable;
- smoke result;
- monitoring window;
- rollback command or revert PR.

Use immutable tags for intentional releases:

```text
rico-vMAJOR.MINOR.PATCH
```

Tags are created only after production verification. Emergency rollbacks use a
revert PR or deployment rollback to a previously verified SHA; history is never
rewritten.

## Emergency bypass

A bypass is allowed only to protect production or user data when waiting for the
normal gate would cause greater harm.

Required record:

- incident and severity;
- exact bypassed controls;
- owner authorization;
- exact head SHA;
- focused validation;
- rollback path;
- post-incident review and follow-up issue.

An emergency bypass does not permanently weaken the ruleset or create a reusable
skip label.

## Definition of mature version control

Rico's version control is mature when:

- `main` is technically protected, not merely protected by written rules;
- every ready PR carries exact-head scope, review, CI, risk, and rollback evidence;
- sensitive paths request accountable ownership review;
- stale reviews fail automatically after a push;
- merge history is linear and reversible;
- deployments are tied to immutable SHAs and verified releases;
- bypasses are exceptional, attributable, and reviewed.
