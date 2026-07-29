# Rico Product Accountability System

> **Status:** Active accountability contract.  
> **Owner:** Rico owner, with the acting CTO/session responsible for evidence-backed updates.  
> **Machine-readable source:** `AI_WORKSPACE/product_accountability_scorecard.json`.  
> **Policy checker:** `scripts/check_product_accountability_scorecard.py`.

## Purpose

Rico already has strong delivery controls: tasks, pull requests, exact-head CI,
reviews, deployment evidence and production smokes. This document adds the
missing second half: a single, honest product scorecard that answers whether
Rico is becoming more useful, more reliable and commercially stronger.

The complete accountability chain is:

```text
Vision
→ metric
→ accountable owner
→ instrumented source
→ dated evidence
→ current value
→ target
→ next action
→ implementation PR
→ production proof
→ measurable user outcome
```

A merged PR is delivery evidence. It is not automatically a product outcome.
A deployment badge is release evidence. It is not automatically a passing
journey. An absent measurement is `not_instrumented`; it is never reported as
zero.

## Source-of-truth order

1. Live production data and exact query/report evidence.
2. Exact deployed SHA plus production-smoke evidence.
3. GitHub exact-head PR, review and CI evidence.
4. `product_accountability_scorecard.json`.
5. This explanatory document.
6. Historical reports and handoffs.

When two sources disagree, the higher source wins and the scorecard must be
corrected. Do not preserve a convenient number merely because it appeared in a
previous report.

## North-star metric

Rico's binding north-star metric is:

> **Verified career actions completed per weekly active user.**

A verified career action is a successful, user-visible career operation with an
authoritative persisted or execution result. Candidate actions include:

- verified opportunity opened;
- job saved;
- application prepared;
- application marked submitted;
- tailored CV generated and approved;
- cover letter approved;
- follow-up completed;
- interview preparation completed.

The taxonomy is not considered fully instrumented until every included action
has:

- one canonical server-side success point;
- an idempotency rule;
- a privacy-safe actor;
- a stable event name and bounded properties;
- a documented inclusion/exclusion rule;
- reconciliation against the authoritative product record where one exists.

## Metric categories

The scorecard must always contain at least one metric for each category:

| Category | Question answered |
| --- | --- |
| Delivery | Are roadmap commitments closing with exact-head evidence? |
| Reliability | Do trust-critical production journeys actually pass? |
| Activation | Do new users reach first value quickly? |
| Engagement | Are users completing verified career actions? |
| Search quality | Do searches produce trusted, useful opportunities and actions? |
| Applications | Are users preparing, approving and submitting applications? |
| Outcomes | Are applications producing replies, interviews, offers and hires? |
| Retention | Do activated users return and continue receiving value? |
| AI quality | Is Rico truthful, grounded and correct when acting? |
| Business | Do activated users pay, remain paid and generate sustainable margin? |

## Metric status contract

Each metric has exactly one status:

- `verified` — a current numeric value exists with dated evidence.
- `partial` — useful evidence exists, but the full metric cannot yet be computed honestly.
- `not_instrumented` — the source events or joins do not yet exist.
- `blocked` — measurement is designed but an external dependency prevents collection.
- `not_applicable` — deliberately excluded for the current product phase.

Truth rules:

1. `not_instrumented` and `blocked` metrics must use `value: null`.
2. Missing evidence must never be converted to `0`.
3. `verified` requires a numeric value and `verified_at`.
4. Every non-verified metric must name its blocker and next action.
5. Every metric must name an owner, cadence, source and evidence.
6. Values derived from synthetic accounts must be labelled test evidence and
   must not be mixed into real-user product metrics.
7. A numerator without a defined denominator is not a percentage.
8. A report covering only one surface must not be described as product-wide.
9. Founder or owner manual activity must be identified when it affects the metric.
10. Personally identifiable information must not be placed in the scorecard.

## Current verified instrumentation boundary

The analytics foundation supports a privacy-safe, allowlisted event store, but
the current server-side wiring is deliberately narrow:

- `search_performed`;
- `job_action` with the approved action values `apply`, `save`, `skip`, `block`
  and `not_relevant`.

The event repository reserves additional event names, but a reserved allowlist
entry is not proof that the event is emitted in production. Therefore:

- the north-star metric is currently `partial`;
- activation, retention, outcomes and business conversion are currently
  `not_instrumented`;
- search usefulness is currently `partial` because search and action events do
  not share a canonical correlation identifier;
- the scorecard must not invent current product values.

## Update cadence

### After every material PR

Update the scorecard when a PR changes:

- metric definitions;
- instrumentation;
- source tables;
- event emitters;
- billing attribution;
- application states;
- production-smoke inventory;
- the roadmap evidence model.

A code change that only makes a future metric possible should normally change
its status from `not_instrumented` to `partial`, not directly to `verified`.

### Weekly

The owner or acting CTO must:

1. Re-read the machine-readable scorecard.
2. Re-run its checker.
3. Refresh `as_of`.
4. Replace blockers that were resolved.
5. Add dated evidence for any verified value.
6. Review failed user journeys, not only aggregate numbers.
7. Choose one next accountability action.

The scheduled GitHub workflow applies an eight-day freshness gate. A stale
failure is an accountability alert, not permission to change the date without
new evidence.

### Monthly

Review:

- paid conversion;
- cancellations and reasons;
- AI cost per paying customer;
- gross margin by plan when available;
- support load;
- product reliability as acquisition changes.

## Scale gates

These are internal management gates from Rico's accepted strategy:

| Gate | Required evidence |
| --- | --- |
| Product proof | 100 users complete a verified career action |
| Revenue proof | 50 paying customers |
| Retention proof | At least 25% of activated users return in week two |
| Repeatability | Three consecutive months of net paid growth |
| Scale readiness | Support load, AI costs and failure rates remain controlled as acquisition doubles |

A later gate cannot compensate for an earlier unproven gate.

## Enforcement

The workflow `.github/workflows/product-accountability-scorecard.yml`:

- validates the scorecard on relevant pull requests and pushes;
- runs positive and negative policy self-tests;
- runs weekly and fails when the scorecard is more than eight days old;
- uses no production credential and performs no production query;
- cannot manufacture values.

The checker rejects:

- missing categories;
- duplicate metric IDs;
- unknown statuses or cadences;
- fake zero values for unmeasured metrics;
- a north-star ID that does not resolve;
- verified claims without a numeric value and date;
- stale scorecards when freshness enforcement is requested.

## Completion definition

Rico's accountability system is structurally complete when:

- delivery governance is enforced on `main`;
- this scorecard is merged and its workflow is green;
- the scorecard is updated weekly;
- each metric has an accountable owner and one next action;
- unknown values remain visibly unknown.

Rico's product measurement is fully operational only when the north star,
activation, retention, outcomes and business metrics become independently
reproducible from production evidence. The structure may be complete before all
measurements are instrumented; the scorecard must make that distinction
explicit.
