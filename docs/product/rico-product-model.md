# Rico Product Model

Rico is a career trajectory intelligence and application operations system for job seekers in the UAE market.

## Core Premise

Rico is not a job board wrapper. Rico is a persistent career co-pilot that:

- Maintains a live model of the user's career profile, target roles, and application history.
- Surfaces contextually relevant jobs via the Rico intelligence pipeline.
- Prepares the user for each application with match reasoning, CV angle, and missing facts.
- Tracks every application across three sources: Rico-originated, manually entered, and inbox-imported.
- Connects chat intent to real workflows — search, track, import, update profile, manage subscription.

## Interaction Architecture

Chat is the primary interface. Every user message is classified into an intent and routed to the correct workflow. Chat responses must reflect the outcome of that workflow, not generic acknowledgements.

```
User message
    ↓
Intent classification (rico_chat_api.py)
    ↓
Workflow dispatch
    ├── Job search → jobs router
    ├── Application tracking → applications router / Application Flow
    ├── Profile update → profile router
    ├── Subscription → /subscription or Stripe Checkout
    ├── Inbox import → email import pipeline (see application-tracking.md)
    └── General career advice → conversational response
```

## What Rico Must Never Do

| Bad behavior | Correct behavior |
|---|---|
| Tell the user to use a spreadsheet for application tracking | Explain the three tracked sources; offer connect/import/manual-add |
| Route package selection to `/command` without checkout | Route Pro/Premium to Stripe Checkout; Free activates immediately |
| Claim subscription is active before backend confirms | Fetch `/api/v1/me` or subscription endpoint; display confirmed state |
| Lose job context when user says "Prepare application — {title} at {company}" | Preserve selected job card context and generate application angle |
| Show an empty Application Flow after a "prepare application" action | Create/update the application record when user opens or marks a job |

## Workflow Ownership

| Workflow | Entry point | Backing service | Status |
|---|---|---|---|
| Job search | Chat intent, `/jobs` page | `src/api/routers/jobs.py` | Live |
| Application tracking | Chat intent, `/applications` page | `src/api/routers/applications.py` | Partially live — see known gaps |
| Manual application entry | "Add past application" chat action or form | applications router | Not yet implemented |
| Inbox import | "Connect Gmail" → OAuth → scan → review | email import pipeline | Not yet implemented |
| Profile update | Chat intent, `/profile` page | `src/api/routers/user.py` | Live |
| Subscription | `/subscription`, package click | Stripe Checkout + `/api/v1/subscriptions/*` | Routing bug — see subscription-flow.md |
| Onboarding | `/onboarding` | `src/api/routers/onboarding.py` | Live |

## Known Gaps / Next PRs

1. Subscription routing fix — package click must route to Stripe Checkout, not `/command`.
2. Job action context fix — "Prepare application" must carry job title/company into Rico response.
3. Manual application entry — UI form and backend endpoint.
4. Inbox import design/implementation — Gmail OAuth, scan, review screen, approved records in Application Flow.
5. `/me` 401 console noise on public routes — suppress or guard the call on unauthenticated pages.
