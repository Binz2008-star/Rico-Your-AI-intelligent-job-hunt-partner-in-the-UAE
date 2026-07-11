# Rico PR Quality Gate Rules

AI coding agents are responsible for the engineering quality gate before asking the owner.

Do not push routine review work back to the owner. Ask the owner only when a decision needs product ownership, live-system approval, commercial approval, unclear scope, or explicit merge authorization.

## Required agent review after every branch or PR

After implementing any branch or PR, the agent must perform this review directly:

1. Inspect changed files and the full diff.
2. Confirm there are no unrelated changes.
3. Confirm auth, safety, and user-data boundaries are preserved.
4. Confirm public or unauthenticated sessions cannot access authenticated-only actions.
5. Confirm no private project values or personal data were added.
6. Confirm tests were updated for the changed behavior.
7. Run the smallest relevant deterministic tests.
8. Check GitHub Actions or CI status after PR creation.
9. Check Codex/GitHub review comments.
10. Classify all review comments:
    - P0/P1: must fix before merge.
    - P2: fix unless clearly proven false positive.
    - P3/nit: optional, but document the decision.
11. Only after all blockers are resolved, recommend one of:
    - Keep draft
    - Mark ready for review
    - Merge approved
    - Request changes

## What not to ask the owner to do

Agents must not ask the owner to do routine engineering review steps such as:

- inspect the diff
- confirm changed files
- check CI
- check Codex comments
- decide whether a P1/P2 review comment is valid
- verify that tests passed

## When asking the owner is allowed

Agents may ask the owner only for:

- permission to merge
- permission to change live data
- product decisions with business tradeoffs
- unclear scope
- confirmation when a fix changes user-facing behavior

## User trigger phrases

If the owner says `review it`, `check it`, `is it ready`, or `what next`, the agent must perform the review using available repo, GitHub, CI, and deploy information.

Do not respond with a checklist for the owner to perform. Execute the checklist and return the result.

## Rico Product Behavior Gate

The review above is the engineering gate. For any change that touches Rico's conversational behavior, intent routing, tool selection, attachments/documents, profile/memory use, or job search, a **Rico PR is not complete until this product gate also passes**, in addition to the engineering gate above. It verifies the change against `RICO_EXECUTION_PRINCIPLES.md` (the product constitution).

### Intent discipline

- Does Rico answer exactly what the user asked, and avoid unrelated actions?
- Does it avoid triggering a job search the user did not ask for?

### Context priority

- Does the response respect the current attachment and the current request first (per "Attachment and Conversation Context Order")?
- Does it avoid injecting profile/memory context that is not relevant?

### Source truth

- Does Rico know where each important claim came from (per "Source Provenance")?
- Does it avoid guessing, and treat inference as the weakest source?

### Tool safety

- Is intent/context reasoned about before a tool is invoked (per "Tool Safety")?
- Is `search_jobs` invoked only on explicit search intent or a valid, clearly-scoped prior authorization?

### Document safety

- Are document types kept distinct — a CV, cover letter, invoice, bank letter, rejection email, offer, or screenshot must not be confused for one another?

### Low-confidence behavior

- On low confidence, does Rico state uncertainty rather than assert a hard label from a weak classification?

### Regression coverage

- Does the PR add or update tests for intended behavior, wrong-context prevention, no unwanted tool calls, Arabic/English (or mixed) behavior where relevant, and attachment handling where relevant?

### Trust check

- Before marking the PR complete, ask: **would this change make the user trust Rico more, or less?** If less, the PR is not complete.

## Required PR quality-gate report

Every PR quality-gate report must include:

```text
Decision: <Keep draft / Ready for review / Merge approved / Changes required>
Why: <short reason>

Scope:
- Changed files: <list>
- Unrelated files: <yes/no>
- Forbidden areas touched: <yes/no>

Security/Auth:
- Authenticated-only actions protected: <yes/no/n-a>
- Public/session users blocked from private mutations: <yes/no/n-a>
- User data isolation preserved: <yes/no/n-a>

Tests:
- Commands run: <commands or not run>
- Results: <pass/fail/partial>
- Known unrelated failures: <details or none>

Review:
- GitHub Actions status: <status>
- Codex comments status: <status>
- Blocking comments: <yes/no>

Final Status:
- Branch: <branch>
- Commit SHA: <sha>
- Pushed: <yes/no>
- PR URL: <url or none>
- Draft or ready: <draft/ready/n-a>
- Merge recommendation: <recommendation>
```
