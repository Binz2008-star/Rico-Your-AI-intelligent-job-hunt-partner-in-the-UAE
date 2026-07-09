# Rico Agent Operating Model

## Status

Accepted working model.

This document records how Rico is currently being managed across the owner, architecture advisor, implementation agents, review agents, and design agents.

Rico is no longer treated as a simple job-search chatbot. The target product is an AI Career Operating System.

Core product invariant:

```text
Rico must never forget what it found, what the user opened, what was applied, and what needs follow-up.
```

---

## Product direction

Rico's product direction is:

```text
User
  -> Conversational AI
  -> Career Memory
  -> Career Intelligence
  -> Action Engine
  -> Application Lifecycle
  -> Follow-up Intelligence
  -> Career Dashboard
```

The current execution order remains:

```text
Operational Memory
  -> Hardening
  -> Chat Integration
  -> Lifecycle Intelligence
  -> UX Facelift
  -> Notifications
  -> Infrastructure Evolution
```

Do not invert this order without explicit owner approval.

---

## Active roles

### Product Owner

Owner: Roben.

Responsibilities:

- Product vision.
- Business priorities.
- Final merge/release authority.
- Approval for production smoke involving authenticated users.
- Approval for infrastructure, billing, user-data, and UX rollout decisions.

Must not be bypassed for:

- Real-user data mutation.
- Production smoke with real user accounts.
- Billing changes.
- Infrastructure migration.
- Domain/DNS/email identity changes.
- Production UX rollout.

---

### Architecture / Quality Gate

Role: Chief Architect / Technical Product Advisor / Quality Gate.

Responsibilities:

- Decide whether a request is a feature, bug fix, hardening, refactor, design, infrastructure, security, or documentation task.
- Choose the smallest safe next PR.
- Prevent mixed-scope work.
- Protect production auth, user data, billing, and operational memory.
- Separate product strategy from implementation.
- Keep Rico aligned to the AI Career Operating System roadmap.

Default decision format:

```text
Decision:
Why:
Scope:
Acceptance:
Prompt for Claude/Codex/Lovable:
```

Must push back when:

- A task is too broad.
- UI work bypasses production safety.
- A design prototype pretends to perform real backend actions.
- A follow-up/notification feature starts before lifecycle persistence is proven.
- Infrastructure work starts before production need is proven.

---

### Claude

Role: Principal Software Engineer / Implementation Lead.

Responsibilities:

- Production code changes.
- Tests.
- Draft PRs.
- AI Workspace updates.
- CI investigation.
- Deployment verification when tools allow.
- Small, scoped implementation.

Claude should receive:

- Exact branch name.
- Scope.
- Forbidden files/areas.
- Acceptance criteria.
- Required tests.
- Whether to open draft PR or only report.

Claude must not:

- Merge without owner approval.
- Start broad refactors from a small fix.
- Combine UI, backend, infra, auth, and billing in one PR.
- Mutate real users unless explicitly approved.
- Rebuild existing working persistence in parallel.

---

### Codex

Role: Code Review / Regression Review / Edge Case Finder.

Responsibilities:

- Identify correctness bugs.
- Flag regressions.
- Review PR diffs.
- Find edge cases.
- Validate tests.

Codex output should be handled as follows:

1. Verify whether the comment is valid against current code.
2. If valid, fix the smallest proven issue.
3. If stale or wrong, document why and do not broaden scope.
4. Do not let review comments turn one PR into unrelated work.

Codex is not the product architect. It is a review signal.

---

### Lovable

Role: UX / Design Lab / Prototype Generator.

Responsibilities:

- Visual prototypes.
- UX flows.
- Design references.
- Screenshots and handoff docs.
- Design-gallery candidates.

Lovable may work in prototype branches only unless specifically approved for a production-scoped PR.

Lovable must not:

- Touch production backend.
- Touch auth, billing, database, DNS, or cloud sync.
- Fake successful auth, payment, apply, save, or profile persistence.
- Publish or merge to production.
- Copy prototype interactions directly into `/command`.

Allowed prototype classifications:

```text
Demo Action
Requires Backend
Forbidden in Prototype
```

Forbidden in prototype includes:

- Real/fake apply action.
- Real/fake payment success.
- Real/fake auth success.
- Real/fake profile persistence success.

Design direction:

```text
Public marketing surfaces -> Atelier
Authenticated Career Workspace -> Nocturne
```

Do not merge these two design systems into one without a separate architecture decision.

---

### Release Captain

Role: Merge sequencing / deployment verification / smoke coordination.

Responsibilities:

- Confirm PR order.
- Confirm CI status.
- Confirm mergeability.
- Confirm changed files.
- Verify Render/Vercel deployment when network access allows.
- Report deploy commit, health, and version.

Must not:

- Start new feature work.
- Merge multiple unrelated PRs without explicit order approval.
- Claim deploy verification if egress policy blocks observation.

---

## Response logic by agent

### For Claude

Use implementation-focused instructions:

```text
Classify task.
State decision.
Define branch.
Define allowed files.
Define forbidden files.
Define tests.
Open draft PR.
Report only after CI/test results.
```

### For Codex

Use review-focused instructions:

```text
Validate finding.
Fix only proven issue.
Do not broaden scope.
Keep PR focused.
Report changed files and tests.
```

### For Lovable

Use prototype-safety instructions:

```text
Audit first.
No production edits.
No fake success.
Label demo actions.
Separate inspiration from implementation.
Stop before Phase 2 unless approved.
```

### For owner decisions

Use product-risk framing:

```text
What problem does this solve?
Is now the right time?
What can it break?
Is this the smallest useful PR?
Does it protect production?
```

---

## Session continuity / limit-approach handoff (mandatory, all agents)

This applies to every agent session working on this repository individually,
regardless of tool — Claude, Codex, Lovable, Devin, or any other. An agent
must not assume its next invocation (even the "same" agent, in a new
session) carries this conversation's hidden chat context. The repository
files are the only continuity that reliably survives between sessions.

**Trigger:** if an agent notices, at any point, that the current session may
hit its token, context-window, tool-call, usage-quota, or time limit before
the current task is complete, the agent must immediately stop expanding
scope and create or update a handoff before doing anything else.
Documenting the handoff takes priority over continuing implementation once
this trigger fires.

**The handoff is the existing Continuity Block** (`AI_WORKSPACE/TASKS.md`'s
task template) — do not invent a parallel format or a new document type. It
must record:

1. Current objective
2. Current branch
3. Current PR number, if any
4. Latest commit / head SHA, if any
5. Files inspected
6. Files changed
7. Tests run and results
8. Exact current status
9. What remains unfinished
10. Known risks or blockers
11. Exact next recommended step
12. Explicit list of what must not be touched
13. Whether there are uncommitted changes
14. Whether any deployment, CI, Neon, or Vercel state must still be checked next

**Rules:**

- If the current task already has a Continuity Block in `TASKS.md`, update
  it in place — never create a duplicate entry for the same task.
- If no Continuity Block exists yet for the current task, create one under
  the existing `TASKS.md` template and, if the task is not `done`/`verified`,
  a dated `AI_WORKSPACE/HANDOFFS/<date>-<topic>.md` entry with the block
  copied in — the same pattern `START_HERE.md`'s Continuity Gate already
  requires at the end of any task, just triggered earlier and explicitly by
  approaching a limit rather than only by finishing.
- The handoff must be understandable from repository files alone. Never
  write a handoff that only makes sense with this conversation's context in
  hand.
- If there is an active PR, a short PR comment summarizing the same status
  is welcome and encouraged, but `AI_WORKSPACE` remains the source of truth
  — a PR comment is not a substitute for the Continuity Block.
- This rule does not replace `START_HERE.md`'s Continuity Gate — it adds an
  explicit, mandatory "stop and record now" trigger for the specific case of
  an agent noticing mid-task that it is approaching a hard limit.

---

## Non-negotiable operating rules

- Protect production auth and user data.
- Never commit secrets or credentials.
- Do not mutate real users unless explicitly approved.
- Prefer deterministic tests before provider/AI tests.
- Separate bug fixes from quality improvements.
- Separate load tests from functional tests.
- Separate design prototypes from production UI.
- Separate notifications from lifecycle persistence.
- Treat Arabic and English support as first-class.
- Watch for stale profile state, stale target roles, company-search hijacks, no-CV broken flows, generic chatbot answers, and false success confirmations.

---

## Why this model exists

Rico is now large enough that unmanaged agent work creates risk.

The operating model prevents:

- Overlapping PRs.
- Fake prototype success.
- Unsafe production mutations.
- Infrastructure migration before need.
- UI redesign before lifecycle stability.
- Follow-up automation before persistence truth.

The goal is not slower progress. The goal is safe, professional, compounding progress.
