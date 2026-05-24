> **Archived document.** This file is historical and not the current source of truth.
> See [docs/PRODUCTION_READINESS.md](../PRODUCTION_READINESS.md) for current deployment status.

---

# Rico Full-System Polish Audit

This document captures the system-wide engineering pass for the `rico-ui-polish` branch.

## Scope reviewed

Rico is not only a job dashboard. The repository describes Rico as an AI-native UAE career companion that combines:

- FastAPI backend
- Rico chat/runtime layer
- CV parsing
- profile memory
- saved searches
- job recommendations
- Telegram and Jotform webhooks
- Neon/PostgreSQL persistence
- web dashboard
- safety, quality, and learning layers

The current branch therefore treats UI polish as one layer of a broader product-system tightening pass.

## Verified architecture surface

### Backend entrypoint

Canonical server entrypoint is:

```text
src.api.app:app
```

`src/rico_server.py` is now only a backward-compatibility shim. Any deployment config should prefer `src.api.app:app`.

### Main API composition

`src/api/app.py` mounts the major routers:

- auth
- user
- actions
- agent
- Rico chat
- jobs
- applications
- stats
- settings
- onboarding
- pipeline
- subscription

It also configures:

- Sentry initialization
- SlowAPI rate limiting
- CORS
- JWT cookie hydration middleware
- DB startup checks for critical auth/audit tables

### Rico chat router

`src/api/routers/rico_chat.py` currently owns a broad surface:

- authenticated chat
- public chat
- profile read/update
- saved searches
- feedback
- AI provider health
- CV upload and confirmation
- metrics
- Telegram webhook
- Jotform webhook
- GitHub webhook

This file is functionally rich but large. Long-term maintainability would improve by splitting it into smaller routers:

```text
src/api/routers/rico/chat.py
src/api/routers/rico/profile.py
src/api/routers/rico/cv.py
src/api/routers/rico/webhooks.py
src/api/routers/rico/health.py
src/api/routers/rico/feedback.py
```

### Web app

The web app lives under:

```text
apps/web
```

Relevant scripts exist:

```bash
npm run build
npm run lint
npm run test
```

The current branch already polished:

- `apps/web/app/globals.css`
- `apps/web/components/StatusCard.tsx`
- `apps/web/components/jobs/JobCard.tsx`

## Neon production schema snapshot

Reviewed against Neon project:

```text
project: robenjob
project_id: old-frog-88141983
branch: production
branch_id: br-restless-cherry-amq6wj7o
database: neondb
```

Observed tables include:

- `users`
- `action_audit_log`
- `password_reset_tokens`
- `jobs`
- `applications`
- `settings`
- `learning_signals`
- `rico_users`
- `rico_profiles`
- `rico_chat_history`
- `rico_job_recommendations`
- `rico_saved_searches`
- `rico_learning_signals`
- `rico_webhook_events`
- `rico_alerts`
- `rico_onboarding_states`

### Positive findings

- `rico_chat_history` has an index on `(user_id, created_at DESC)`, which matches chat history pagination.
- `rico_job_recommendations` has an index on `(user_id, status)`, which matches recommendation filtering.
- `rico_profiles` has a unique index on `user_id`, which matches one profile per Rico user.

### Production concern

Several Rico tables allow nullable `user_id` even though they are logically user-scoped. This may be intentional for legacy/import flows, but it should be reviewed before enforcing stricter constraints.

Recommended staged approach:

1. Audit rows where `user_id IS NULL`.
2. Backfill or archive orphaned rows.
3. Add `NOT VALID` checks where safe.
4. Validate constraints during low-traffic windows.
5. Only then consider `NOT NULL` enforcement.

No schema changes were applied in this branch.

## Engineering issues to prioritize next

### 1. Split Rico chat router

`rico_chat.py` has grown into a multi-domain router. Split it to reduce regression risk and improve testability.

Priority: high  
Risk: medium  
Impact: maintainability, onboarding, future features

### 2. Harden public identity inputs

`RicoPublicChatRequest.email` currently checks for `@`, but should use a stricter email validator or normalized utility.

Priority: high  
Risk: low  
Impact: public chat reliability and abuse resistance

### 3. Enforce admin-only health endpoint

`/api/v1/rico/admin/health/ai-provider` should use the existing `require_admin` dependency rather than only checking authentication.

Priority: high  
Risk: low  
Impact: security posture

### 4. Centralize request timing metrics

Request timing is manually recorded in many handlers. A middleware-level timing collector would reduce drift and forgotten instrumentation.

Priority: medium  
Risk: low  
Impact: observability quality

### 5. Add contract tests around web API adapters

`apps/web/lib/api.ts` validates important Rico responses using Zod. Add contract tests for:

- public chat response
- profile response
- CV upload preview
- saved searches
- job normalization
- application normalization

Priority: medium  
Risk: low  
Impact: frontend/backend contract safety

### 6. Add database health smoke query

Add a readonly operational check that verifies critical tables exist and reports non-secret readiness status.

Priority: medium  
Risk: low  
Impact: deployment confidence

## Completed in `rico-ui-polish`

### UI system primitives

Added reusable Rico visual primitives:

- `rico-card`
- `rico-chip`
- `rico-chip-accent`
- `rico-kicker`
- `rico-muted`
- `rico-divider`

### Dashboard cards

Refined dashboard cards into product-grade status cards with:

- stronger visual hierarchy
- safer badge language
- better hover/focus states
- clearer status semantics

### Job cards

Refactored `JobCard` into smaller units:

- `getCompanyIdentity`
- `getJobMeta`
- `BulletList`
- `MatchExplanationPanel`

Also improved:

- type safety for actions
- accessibility labels
- semantic article/section markup
- null handling
- match explanation layout

## Recommended validation before merge

From `apps/web`:

```bash
npm run lint
npm run test
npm run build
```

From repository root:

```bash
python scripts/test_rico_startup.py
```

Optional backend smoke:

```bash
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
```

## Merge recommendation

This branch is safe to review as a UI/system-polish branch because it does not apply database migrations or alter production data. Merge only after the web build and tests pass.
