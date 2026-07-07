# Rico Production Hardening Audit — 2026-07-08

## Status

Decision: **Approved for implementation as an audit gate**

Implementation mode: **docs-only audit/control artifact first**

Runtime changes: **none in this PR**

This audit exists to stabilize Rico production quality before additional feature work, redesign work, or large architectural changes.

Infrastructure migration is **not** the objective of this audit. Render remains the current production backend unless a separate future decision explicitly approves migration.

---

## Core product invariant

Rico must never forget what it found, what the user opened, what was applied, and what needs follow-up.

That means Rico must preserve operational memory across:

```text
chat turns → browser refreshes → new sessions → backend restarts → deploys
```

The core user lifecycle is:

```text
search job → preserve job context → open apply link → save/track → mark applied → follow up
```

A Rico response must not claim success unless the relevant state was actually persisted or safely recoverable.

---

## Why this exists

Rico is no longer just a job-search chat surface. It is becoming an AI career operations system. Before adding more capability, production behavior must be proven across the operational lifecycle.

The current architectural priority is production reliability and memory correctness, not new features.

---

## Non-negotiable rules

- Render stays as the production backend for now.
- Do not start infrastructure migration work from this audit.
- Do not redesign `/command` during this audit.
- Do not combine unrelated fixes in one PR.
- Do not change auth, billing, provider routing, CV parsing, or database schema unless the specific audit finding requires it.
- Do not mutate real users during smoke tests.
- Use a safe smoke account/session only.
- Do not print passwords, tokens, cookies, or session values.
- Every finding must become a small, scoped PR.

---

## Audit phases

### Phase 1 — Product flow smoke

Required checks:

- [ ] Public homepage loads.
- [ ] `/command` loads.
- [ ] Login works with safe smoke account.
- [ ] `/proxy/api/v1/me` returns authenticated user shape after login.
- [ ] CV upload route loads.
- [ ] Profile route loads.
- [ ] Settings route loads.
- [ ] Subscription route loads.
- [ ] Applications/flow route loads.
- [ ] Public chat still works.
- [ ] Authenticated chat still works.
- [ ] Mobile `/command` composer remains visible.
- [ ] No public route shows misleading logged-in state.

Acceptance:

```text
All user-visible routes load without blocking errors.
Authenticated smoke proves session, profile, jobs, and chat paths.
```

---

### Phase 2 — Job context and apply-link lifecycle

Required checks:

- [ ] English job search returns structured matches.
- [ ] Arabic job search returns structured matches.
- [ ] Mixed-language job search routes correctly.
- [ ] Job results persist to Neon-backed `user_job_context`.
- [ ] Apply/source/alt links are preserved.
- [ ] `open apply link` works from fresh chat context.
- [ ] `open apply link` works after new browser session or backend restart.
- [ ] Source URL fallback is clear when no direct apply link exists.
- [ ] Rico never tells the user to manually search when a persisted source/apply link exists.
- [ ] Link unavailable state gives safe fallback CTAs.

Acceptance:

```text
Search → open apply link → new session → open apply link still succeeds.
```

---

### Phase 3 — Application lifecycle

Required checks:

- [ ] Save job creates/updates one user-scoped record.
- [ ] Open apply link marks job as `opened_external` when lifecycle write succeeds.
- [ ] Prepare application attaches to the same job/application.
- [ ] Mark applied updates the same record.
- [ ] Manual Arabic applied-status phrases update status correctly.
- [ ] Manual English applied-status phrases update status correctly.
- [ ] Rico confirms success only after persistence succeeds.
- [ ] Rico does not point applied-status users to `/queue`.
- [ ] `/applications` or `/flow` reflects the updated state.
- [ ] Duplicate prevention works by user/title/company/source identity.

Acceptance:

```text
found → saved/opened → prepared → applied is visible and persistent for the same job.
```

---

### Phase 4 — Follow-up readiness

Required checks:

- [ ] Applied jobs have enough persisted data for later follow-up.
- [ ] `applied_at` or equivalent timestamp exists when status becomes applied.
- [ ] Opened-but-not-applied jobs can be listed.
- [ ] Applied-with-no-response jobs can be listed later without re-searching.
- [ ] Follow-up candidates are user-scoped.
- [ ] Rico can explain why a job needs follow-up.
- [ ] No notification or email is sent automatically unless a separate approved workflow exists.

Acceptance:

```text
Rico can identify what needs follow-up from persisted state without relying on chat memory only.
```

---

### Phase 5 — AI routing and memory quality

Required checks:

- [ ] Role extraction does not fall back to generic Engineer/Manager when a real role exists.
- [ ] Saved target role is used only when appropriate.
- [ ] Current-role comparison searches do not become profile-reading intents.
- [ ] Applied/saved/lifecycle list requests do not become fresh searches.
- [ ] Company search does not hijack role search.
- [ ] No-CV flows produce useful guidance, not broken generic answers.
- [ ] Arabic and English confirmations preserve pending intent.
- [ ] Short replies such as `تمام`, `yes`, `ok`, `apply`, and `save it` resolve from context correctly.

Acceptance:

```text
Intent routing preserves the user task across follow-up turns and does not silently switch task class.
```

---

### Phase 6 — Frontend stability

Required checks:

- [ ] `/command` does not flash unauthenticated CTAs for logged-in users.
- [ ] Mobile keyboard does not hide composer.
- [ ] Safe-area handling works on iPhone-sized viewport.
- [ ] Navigation links are present and consistent.
- [ ] Empty states are useful.
- [ ] Loading states do not look broken.
- [ ] Error states are actionable.
- [ ] Arabic text remains readable.
- [ ] No accidental light-mode/theme regression.

Acceptance:

```text
Core surfaces are stable on desktop and mobile without visual regressions that block task completion.
```

---

### Phase 7 — Backend/API reliability

Required checks:

- [ ] Health endpoint returns healthy state.
- [ ] Version metadata reflects real environment/deploy data or clearly says unavailable.
- [ ] Proxy target does not fall back to localhost in production.
- [ ] Repository functions fail safely.
- [ ] SQL composition avoids unsafe dynamic identifiers.
- [ ] Migrations are ordered and drift check passes.
- [ ] DB writes are user-scoped.
- [ ] API responses keep stable shapes.
- [ ] No route returns success while persistence failed.

Acceptance:

```text
Backend failures are safe, observable, and do not create false user confirmations.
```

---

### Phase 8 — Security and privacy

Required checks:

- [ ] Authenticated routes reject anonymous access correctly.
- [ ] Public routes do not leak private data.
- [ ] User IDs are not confused with `public:web` for authenticated users.
- [ ] No credentials or tokens are logged.
- [ ] Prompt/provider labels are not leaked to users.
- [ ] Rate limits protect chat and expensive endpoints.
- [ ] Upload security tests pass.
- [ ] Admin diagnostics are not public.

Acceptance:

```text
No obvious data isolation, auth, or secret-leak regression exists in current production behavior.
```

---

### Phase 9 — Infrastructure readiness, not migration

Required checks:

- [ ] API/worker responsibilities are separated or explicitly documented.
- [ ] Background jobs are not dependent on request lifecycle.
- [ ] Monitoring/logging exists for API and worker.
- [ ] Production smoke suite is repeatable.
- [ ] Render rollback/redeploy path is documented.
- [ ] Vercel backend URL handling is safe.
- [ ] Neon remains the source of truth.

Acceptance:

```text
The current Render-based production system is observable, recoverable, and stable enough to operate.
```

---

## Finding template

Every audit finding must be recorded like this:

```text
ID:
Severity: P0 / P1 / P2 / P3
Category:
Problem:
Impact:
Evidence:
Smallest safe fix:
Files allowed:
Files forbidden:
Acceptance criteria:
Required tests:
Rollback note:
```

---

## Severity definitions

### P0 — Production blocker

Breaks login, chat, apply-link lifecycle, data isolation, payments, or user trust.

### P1 — High priority

Core workflow works but is unreliable, confusing, or hard to debug.

### P2 — Medium priority

Important quality issue, but not blocking current production use.

### P3 — Low priority

Polish, cleanup, documentation, or deferred UX improvement.

---

## Initial recommended PR sequence after audit

Do not start these until the relevant audit finding is proven.

```text
PR 1 — Fix any P0 production smoke failures
PR 2 — Fix apply-link/session persistence regressions if found
PR 3 — Fix application lifecycle false-confirmation issues if found
PR 4 — Fix follow-up readiness gaps if found
PR 5 — Fix AI routing/context recovery issues
PR 6 — Add/repair repeatable smoke tooling
PR 7 — Add monitoring/logging improvements
PR 8 — Worker/cron separation only if audit proves it is needed now
```

---

## Current decision

Proceed with production hardening audit centered on Rico operational memory.

Do not start infrastructure migration, visual redesign, or new agent features until the audit report classifies current production risks and the P0/P1 fixes are complete.
