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
