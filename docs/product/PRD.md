# Rico Hunt — Product Requirements Document

**Version:** 1.0  
**Date:** 2026-07-29  
**Status:** Draft — consolidated from existing product, architecture, and launch documents  
**Branch:** `docs/product-prd`  

---

## 1. Overview

### 1.1 Problem

Job seekers in the UAE waste hours every day browsing disjointed job boards, tailoring CVs and cover letters manually, and losing track of applications. Most tools are either generic global job aggregators or static CV builders with no intelligence, no bilingual support, and no local market context.

### 1.2 Product Vision

Rico Hunt is a persistent, bilingual AI career co-pilot for UAE job seekers. It is not a job-board wrapper. Rico maintains a live model of the user's career profile, discovers relevant UAE jobs, prepares application materials, tracks every application, and guides the user through the full job-search lifecycle inside a single conversational interface.

### 1.3 Target Market

- Primary: professionals already in the UAE or relocating to the UAE
- Secondary: bilingual Arabic/English job seekers who need culturally and legally relevant career guidance
- Initial beachhead: HSE, ESG, engineering, operations, and managerial roles where keyword alignment and CV tailoring are high-leverage

### 1.4 Value Proposition

- **Save time:** one chat to search, prepare, and track applications
- **Improve fit:** AI-tailored CV and cover letter grounded in verified profile and job description
- **Stay organized:** application history across Rico-originated, manual, and inbox-imported sources
- **Local context:** UAE-focused advice, bilingual responses, and role/location normalization
- **Stay safe:** no application is submitted without explicit user approval; no claims are made unless persistence succeeds

---

## 2. Goals & Outcomes

### 2.1 Launch (MVP) Goal

Ship a gated, authenticated web application with:
- public landing and pricing
- signup, login, email verification
- onboarding and CV upload
- conversational job search and application drafting
- application tracking and profile management
- one paid plan at AED 79/month
- invitation workflow

### 2.2 Success Metrics (30 / 60 / 90 days)

| Metric | 30 days | 60 days | 90 days |
|---|---|---|---|
| Invited users activated | 50% | 60% | 70% |
| Users completing onboarding | 60% | 70% | 75% |
| Weekly jobs surfaced per active user | 10 | 15 | 20 |
| Application drafts accepted | 40% | 55% | 65% |
| First paid conversions | 5% | 10% | 15% |
| Support tickets per 100 sessions | <5 | <3 | <2 |

### 2.3 Outcomes for the User

1. Upload a CV once and have Rico keep the profile current.
2. Ask Rico for jobs in Arabic or English and receive ranked, relevant UAE listings.
3. Request a tailored CV and cover letter for any saved job and receive a draft that uses only verified facts.
4. Track every application in one place regardless of its source.
5. Receive proactive follow-ups and reminders for pending applications.

---

## 3. Target Personas

### 3.1 Persona A — "Relocated Professional"

- Moved to UAE recently, has 5–15 years of experience
- Needs to understand local hiring norms and role titles
- Wants fast, accurate application materials
- Prefers English

### 3.2 Persona B — "UAE-Based Switcher"

- Currently employed in UAE, looking for a better role
- Has a CV but does not keep it updated
- Wants to track multiple applications and recruiter replies
- May use Arabic or English

### 3.3 Persona C — "Recent Graduate"

- Limited work experience, needs profile building
- Unsure how to align skills with job descriptions
- Needs guidance more than automation
- Cost-sensitive, likely free-tier initially

---

## 4. Core Capabilities

### 4.1 Capability Matrix

| Capability | MVP | Post-MVP | Notes |
|---|---|---|---|
| Signup / login / email verification | ✅ | — | JWT in httpOnly cookie |
| Onboarding and CV upload | ✅ | — | PDF/DOCX/TXT; scanned PDFs fallback to OCR (post-MVP) |
| Conversational job search | ✅ | — | Chat intent + `/jobs` route |
| Job scoring and ranking | ✅ | — | Keyword + HF embeddings; reranking in Phase 3 |
| Tailored CV generation | ✅ | — | Single AI call; fact verifier in Phase 4 |
| Cover letter generation | ✅ | — | Cover letter writer with identity guard |
| Application tracking (Rico-originated) | ✅ | — | Core application flow |
| Manual application entry | ❌ | ✅ | UI form + backend endpoint |
| Inbox import (Gmail) | ❌ | ✅ | OAuth, scan, review, approved records |
| Subscription (AED 79/month) | ✅ | — | Stripe Checkout + webhooks |
| Invitations | ✅ | — | Single-use expiring tokens |
| RTL / Arabic critical path | ✅ | — | Public entry, auth, onboarding, chat |
| Mobile web | ✅ | — | No horizontal overflow, responsive layout |

### 4.2 Capability Definitions

#### 4.2.1 Upload CV

Rico directs the user to upload a CV, parses it, and stores confirmed fields automatically. It never asks for CV fields one by one when upload is available. Missing fields are surfaced as gaps to be filled, not invented.

**Acceptance criteria:**
- PDF, DOCX, and TXT files are accepted.
- Extractable text is parsed into name, skills, experience, education, certifications.
- Scanned/image PDFs that yield no text are flagged with `no_text` status, not failed silently.
- Stored profile belongs to the authenticated user only.

#### 4.2.2 Understand Profile

Rico reads the authenticated user's stored profile and uses it to personalize search, match, and application drafting. It never reads another user's profile or assumes cross-session identity.

**Acceptance criteria:**
- `user_id` is derived from JWT, not request body.
- Email and phone are not included in AI prompts unless explicitly required.
- Profile context is capped to avoid token bloat (`_PROFILE_CONTEXT_MAX_CHARS`).

#### 4.2.3 Match UAE Jobs

Rico searches verified job board data (JSearch/RapidAPI) using clean role and location aliases. It never invents job listings, companies, or apply links.

**Acceptance criteria:**
- Target roles and cities are normalized before query.
- Results are scored and ranked by relevance.
- Each result includes provenance (source, link, fetched-at timestamp).
- Geographic aliases (Dubai/DXB, Abu Dhabi/AUH) are resolved.

#### 4.2.4 Prepare CV

Rico generates a tailored CV from confirmed fields only. It does not insert placeholders, fake dates, invented responsibilities, or assumed values.

**Acceptance criteria:**
- Tailored CV is derived from source CV text and job description.
- Output preserves section structure (Summary, Experience, Education, Skills).
- No claims are added that do not appear in source data.
- If AI fails to produce parseable output, a keyword fallback returns the original CV.

#### 4.2.5 Prepare Cover Letter

Rico drafts a cover letter using job and profile context. It does not invent employer-specific claims or assert the user has submitted anything.

**Acceptance criteria:**
- Output is 3 short paragraphs, max 250 words.
- It uses verified identity data (name, location, profile line) via `CoverLetterIdentity`.
- Language matches the requested language (Arabic or English).
- Generic filler phrases are avoided.

#### 4.2.6 Track Applications

Rico writes an application record only after the DB write succeeds. It does not say "saved" or "marked as applied" if the DB write fails.

**Acceptance criteria:**
- Application record is created on `save` or `apply` action.
- Status transitions are explicit and auditable.
- Duplicate drafts for the same user/job are reused, not duplicated.
- No cross-user data leakage.

#### 4.2.7 Guide Safely

Rico explains how to do things, offers options, and asks for confirmation on high-impact actions. It does not submit applications without user approval or claim an action happened unless it did.

**Acceptance criteria:**
- High-impact actions (apply, payment, profile mutation) require explicit user confirmation.
- Approval mode (`RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS`) is respected.
- Auto-apply remains a draft + preview; external submission stays behind explicit approval and audit log.

---

## 5. User Flows

### 5.1 First-Time User Flow

1. Land on public page (`/`).
2. Sign up with email and password.
3. Verify email.
4. Enter onboarding: target role, experience, cities, salary expectations.
5. Upload CV or skip (skip triggers manual profile building).
6. Arrive at workspace dashboard.
7. Send first chat message: "Find me HSE manager jobs in Dubai".
8. Review job cards.
9. Save or prepare application for a job.
10. Tailored CV and cover letter are generated.

### 5.2 Returning User Flow

1. Log in.
2. Workspace loads with saved profile and recent applications.
3. User sends chat or uses command center.
4. Rico acknowledges profile state briefly: "I can see you're targeting [role] in [city]."
5. User requests next actions: search, track, update profile, manage subscription.
6. Workflow executes and response reflects the actual outcome.

### 5.3 Application Drafting Flow

1. User selects a job or says "prepare application for [title] at [company]".
2. Rico creates/updates application record.
3. Rico calls `tailor_application(cv_text, profile, job)`.
4. AI produces one response with two sections: tailored CV and cover letter.
5. Response is parsed and returned to user.
6. User approves, edits, or rejects the draft.
7. Approved draft is stored; rejected draft is discarded or kept for learning.

### 5.4 Subscription Flow

1. User clicks pricing or says "I want the paid plan".
2. Rico routes to Stripe Checkout (not `/command` or generic page).
3. User completes payment.
4. Stripe webhook is verified and idempotent.
5. Subscription status is updated server-side.
6. Entitlements are enforced on subsequent requests.

### 5.5 Invitation Flow

1. Owner/admin creates an invitation for a specific email.
2. Single-use, expiring token is generated and bound to the email.
3. Branded EN/AR email is sent through canonical mailer.
4. User clicks invitation link and reaches account claim/signup.
5. Token is consumed and cannot be reused.
6. Failed delivery is visible to the owner/admin.

---

## 6. Functional Requirements

### 6.1 Authentication & Identity

| Requirement | Priority | Notes |
|---|---|---|
| JWT-based auth in httpOnly cookie | P0 | `src/api/deps.py` |
| User identity derived from JWT, never request body `user_id` | P0 | Enforced in all protected routes |
| Email verification before full access | P0 | |
| Password reset with secure token | P0 | |
| Public sessions isolated from authenticated accounts | P0 | `public_` prefix in `public_identity.py` |
| Guest route boundaries correct | P0 | No `/me` 401 noise on public routes |

### 6.2 Onboarding & Profile

| Requirement | Priority | Notes |
|---|---|---|
| Collect target roles, experience, preferred cities, salary range | P0 | |
| CV upload and parse | P0 | `src/cv_parser.py` |
| Profile update via chat and `/profile` | P0 | `src/api/routers/user.py` |
| Profile data isolated per user | P0 | JWT-derived `user_id` |
| Missing fields surfaced, not invented | P0 | |

### 6.3 Job Search

| Requirement | Priority | Notes |
|---|---|---|
| Chat intent routes to job search | P0 | `src/rico_chat_api.py`, `src/rico_intent_router.py` |
| Search uses normalized roles and locations | P0 | `src/role_normalization.py` |
| Results scored and ranked | P0 | `src/scoring.py`, `src/llm_scorer.py` |
| Result cards include source, link, timestamp | P0 | |
| Save, skip, block actions in chat and UI | P0 | `src/telegram_actions.py`, `src/api/routers/rico_chat.py` |

### 6.4 Application Preparation

| Requirement | Priority | Notes |
|---|---|---|
| Single AI call generates tailored CV + cover letter | P1 | `src/rico_apply_ai.py` — implemented in `perf/rico-apply-ai-single-call` |
| Output parsed reliably; fallback on failure | P0 | `_parse_tailored_output` |
| No invented facts | P0 | Verified identity and source CV only |
| Support Arabic and English output | P0 | Language detection + instruction |

### 6.5 Application Tracking

| Requirement | Priority | Notes |
|---|---|---|
| Application record per user/job | P0 | `src/applications.py`, `src/api/routers/applications.py` |
| Status lifecycle: saved, applied, interview, offer, rejected, closed | P0 | |
| Duplicate protection | P0 | `rico_recommendations` unique index |
| Manual entry (post-MVP) | P2 | UI form + backend endpoint |
| Inbox import (post-MVP) | P2 | Gmail OAuth pipeline |

### 6.6 Chat & Conversational AI

| Requirement | Priority | Notes |
|---|---|---|
| Intent classification (deterministic + AI fallback) | P0 | `src/agent/orchestrator/intent_detector.py`, `src/rico_intent_router.py` |
| Workflow dispatch to correct tool | P0 | `src/rico_tool_registry.py` |
| Responses grounded in user data | P0 | `src/rico_chat_api.py` context building |
| Safety guard on messages | P0 | `src/rico_safety.py` |
| Fallback to templated text when AI unavailable | P0 | `src/rico_openai_agent.py` |
| Streaming chat responses | P1 | `src/rico_openai_runtime.py` |

### 6.7 Billing & Subscriptions

| Requirement | Priority | Notes |
|---|---|---|
| One paid plan: Rico Monthly at AED 79 | P0 | `AI_WORKSPACE/LAUNCH_EXECUTION_PLAN.md` |
| Stripe Checkout integration | P0 | |
| Verified webhook handling | P0 | |
| Server-side entitlement gating | P0 | `src/subscription_plans.py` |
| Cancellation and grace-state handling | P0 | |
| No activation from query params or return URL alone | P0 | |

### 6.8 Invitations

| Requirement | Priority | Notes |
|---|---|---|
| Single-use, expiring invitation token | P0 | |
| Bound to intended email and lifecycle state | P0 | |
| Branded EN/AR email | P0 | |
| Idempotent delivery | P0 | |
| Delivery failure visibility | P1 | |

---

## 7. Non-Functional Requirements

### 7.1 Performance

| Requirement | Target | Notes |
|---|---|---|
| Chat first token latency | < 1.5s | Use streaming; DeepSeek primary |
| Job search end-to-end | < 5s | Sync currently, async in Phase 3 |
| Page load (desktop, 4G) | < 3s | Next.js, Vercel |
| Mobile usability | < 5s | Responsive, no horizontal overflow |

### 7.2 Security & Privacy

| Requirement | Target | Notes |
|---|---|---|
| No PII in AI prompts except necessary | P0 | Email excluded; phone under audit |
| No cross-user data access | P0 | JWT isolation, DB user-scoped queries |
| Secrets in env only, never committed | P0 | `.env.example` |
| Webhook signature verification | P0 | Jotform, Telegram, Stripe |
| Audit log for high-impact actions | P0 | Application lifecycle, payment, admin |

### 7.3 Reliability

| Requirement | Target | Notes |
|---|---|---|
| AI provider fallback | P0 | DeepSeek → OpenAI → HuggingFace → template |
| DB write confirmed before claiming success | P0 | Fail-closed |
| Feature flags for risky features | P0 | `RICO_ENABLE_CV_OCR`, `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS` |
| `/health` and `/version` endpoints | P0 | Render + Vercel |

### 7.4 Localization

| Requirement | Target | Notes |
|---|---|---|
| Arabic and English first-class | P0 | RTL, Arabic greeting, Arabic job search |
| Arabic orthographic normalization | P0 | `intent_detector.py` |
| UI language switch | P1 | |

### 7.5 Observability

| Requirement | Target | Notes |
|---|---|---|
| Structured logging | P1 | Replace plain text logging |
| Cost tracking per AI feature | P1 | Input/output tokens and model used |
| Distributed tracing | P2 | Trace chat request end to end |
| Health and provider status | P0 | `src/health_check.py` |

---

## 8. Product Identity & Tone

Rico must behave as a **controlled AI career assistant**, not a generic chatbot.

- Serious, professional, and direct
- UAE career-focused — always contextualizes advice for the UAE market
- Bilingual: Arabic and English with equal capability
- No fake enthusiasm ("Amazing!", "That's fantastic!")
- No unsupported claims ("You're a great fit!" without match data)
- No guaranteed job promises
- Proactive — offers next actions rather than waiting
- Honest about limitations — says when AI is unavailable

The complete behavior contract is in `docs/product/rico_behavior_spec.md`.

---

## 9. Out-of-Scope for MVP

| Item | Rationale |
|---|---|
| Real external application submission | Requires browser automation, legal risk, explicit approval gate; draft + preview only for MVP |
| Gmail inbox import | OAuth pipeline and review UI not yet implemented |
| Scanned/image CV OCR | Extractable-text parsing only for MVP; OCR behind feature flag later |
| White-label / multi-tenant SaaS | Single-tenant with user isolation for launch; multi-tenant in `PRODUCTION_ROADMAP.md` |
| Advanced analytics dashboard | Basic tracking only for launch |
| Mobile native app | Mobile web responsive only |

---

## 10. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| AI hallucination in CV/cover letter | Medium | High | Single source-of-truth CV, parseable output, keyword fallback; fact verifier in Phase 4 |
| Identity cross-user data leak | Low | Critical | JWT-derived `user_id`, fail-closed queries, D1 repair before launch |
| Subscription webhook failures | Medium | High | Idempotent handler, test environment smoke, grace state |
| Provider cost overruns | Medium | Medium | Single-call CV+CL, prompt caps, HF fallback, token tracking |
| Frontend not complete for launch | Medium | High | Launch execution plan gates UI parity before billing/invitations |
| DB latency under load | Medium | Medium | Connection pooling and caching in `PRODUCTION_ROADMAP.md` |

---

## 11. Launch Gate

Rico is launch-ready only when:

- Control plane is current (`AI_WORKSPACE/PROJECT_STATUS.md`, open PRs reconciled).
- Approved interface covers the complete launch-critical journey (`LAUNCH_EXECUTION_PLAN.md` Phase 2 exit gate).
- Single AED 79 plan works through verified billing events (`LAUNCH_EXECUTION_PLAN.md` Phase 3 exit gate).
- Invitations work end to end (`LAUNCH_EXECUTION_PLAN.md` Phase 4 exit gate).
- All launch smoke checks pass (`LAUNCH_EXECUTION_PLAN.md` Phase 5).
- Known non-blocking issues are explicitly deferred with owners.
- Rollback is ready.
- Owner approves opening access.

---

## 12. References

- `docs/product/rico-product-model.md` — core premise and workflow ownership
- `docs/product/rico_behavior_spec.md` — agent behavior and privacy rules
- `docs/product/chat-routing-contract.md` — chat intent routing
- `docs/ARCHITECTURE.md` — system overview and doc index
- `docs/DEEP_ARCHITECTURE_ANALYSIS.md` — component breakdown and data flow
- `docs/PRODUCTION_ROADMAP.md` — prototype to multi-tenant SaaS migration
- `AI_WORKSPACE/LAUNCH_EXECUTION_PLAN.md` — launch sequence and exit gates
- `docs/STATEFUL_AGENT_ARCHITECTURE.md` — stateful agent request flow
