# Rico AI — Architecture Reference

This document is the canonical entry point for architecture documentation. It indexes the detailed docs in this directory.

## System Overview

Rico Hunt / Rico AI is a UAE-focused AI career companion built in three layers:

1. **Legacy pipeline** — daily job fetching, scoring, tracking, notifications (`src/run_daily.py`)
2. **Rico AI backend** — FastAPI, conversational AI, auth, CV parsing, webhooks (`src/api/`, `src/agent/`, `src/services/`)
3. **SaaS frontend** — Next.js 14 public site and authenticated dashboard (`apps/web/`)

Deployed at:
- Frontend: `https://ricohunt.com` (Vercel)
- Backend: `https://rico-job-automation-api.onrender.com` (Render)
- Database: Neon PostgreSQL

---

## Detailed Documentation

### System Diagrams
**[ARCHITECTURE_DIAGRAMS.mmd](./ARCHITECTURE_DIAGRAMS.mmd)**
Mermaid diagrams covering:
- High-level system architecture (clients → API gateway → conversational layer → agent brain → pipeline)
- Request flow through FastAPI routers
- Agent tool registry

### Deep Architecture Analysis
**[DEEP_ARCHITECTURE_ANALYSIS.md](./DEEP_ARCHITECTURE_ANALYSIS.md)**
Covers:
- Executive summary of the dual-layer pattern (legacy pipeline + agent layer)
- Component-by-component breakdown with file references and line counts
- Data flow from client surfaces through the conversational layer to the pipeline
- Scoring algorithm: signal weights, CV-fit scoring, role normalization
- Memory and learning: profile model, audit log, learning signals

### Production Architecture
**[RICO_PRODUCTION_ARCHITECTURE.md](./RICO_PRODUCTION_ARCHITECTURE.md)**
Covers:
- Backend and frontend stack with hosting details
- Core flows: onboarding, job search, auto-apply
- AI provider routing (DeepSeek → HuggingFace → keyword fallback)
- Webhook handling (Jotform DB-backed idempotency, Telegram)

### Stateful Agent Architecture
**[STATEFUL_AGENT_ARCHITECTURE.md](./STATEFUL_AGENT_ARCHITECTURE.md)**
Covers:
- Migration from stateless to stateful agent pattern
- Full request flow: identity resolution → profile load → context hydration → intent routing → safe action → learning signal
- Core components: AI provider router, identity resolver, tool registry, safety guardrails
- Agent runtime singleton and idempotency scheme (MD5 of `user_id:action:job_key`)

### Scalability Roadmap
**[PRODUCTION_ROADMAP.md](./PRODUCTION_ROADMAP.md)**
Covers:
- Current architectural weaknesses (synchronous pipeline, DB latency, no connection pooling)
- Incremental migration path to multi-tenant SaaS
- Async workers, message queue, connection pooling, horizontal scaling

### Production Readiness
**[PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md)**
Covers:
- Production URLs and Vercel project configuration
- Required environment variables for frontend and backend
- Cookie domain rules for `ricohunt.com` vs preview deployments

### Security
**[SECURITY.md](./SECURITY.md)**
Covers:
- Secret management rules (never commit credentials)
- Pre-launch checklist (rotate, update, scan)
- Webhook shared-secret validation
- Auto-apply disabled by default

### Frontend/Backend Endpoint Mapping
**[FRONTEND_BACKEND_ENDPOINT_MAPPING.md](./FRONTEND_BACKEND_ENDPOINT_MAPPING.md)**
Covers:
- Full mapping of frontend pages to backend API routes
- Proxy rewrite rules

### Development Workflow
**[DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md)**
Covers:
- Branching and PR conventions
- Rico response order (fast path → deterministic intent → cached → external search → AI fallback)
- Frontend button → backend action contract

---

## Key Architectural Rules (summary)

These rules are enforced in code and tests. Full detail in CLAUDE.md.

- **Auth:** JWT in `httpOnly` cookie. Identity always derived from JWT, never from request body.
- **Agent runtime:** Singleton at `src/agent/runtime.py`. All job actions go through `agent_runtime.handle_action()`.
- **Safety:** `src/rico_safety.py` guardrails are non-negotiable. `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` by default.
- **Jotform idempotency:** DB-backed via `db.register_webhook_event` / `db.mark_webhook_event_processed`.
- **CV parser:** Synchronous by design. Wrap in `run_in_executor` when calling from async FastAPI routes.
- **AI provider:** Controlled by `RICO_AI_PROVIDER` env var. Current production: `deepseek`. Runtime-computed fields must not be set as static env vars.
