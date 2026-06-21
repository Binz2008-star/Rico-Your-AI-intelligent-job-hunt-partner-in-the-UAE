# Rico Agentic Vision — GitHub Intelligence Report

_Audit date: 2026-06-21 · Author: Rico AI engineering audit · Status: design-only, no runtime code changes_

> **Scope guard.** This document is a research + design deliverable. It does **not** change runtime
> behavior. Every external repository below is treated as a **reference only**. No external code is
> copied into Rico. AGPL/GPL/unknown-license code is explicitly excluded from import. Any apply
> action described here stays **user-approved** and routed through `agent_runtime.handle_action()`
> behind `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`.

---

## 1. Executive summary

Rico already has the **hard, defensible parts** of an agentic job-search system that most public
projects lack: a single action dispatcher (`src/agent/runtime.py`), a declarative tool registry
(`src/agent/registry/tool_registry.py`), MD5 idempotency keys, an audit log
(`src/repositories/audit_repo.py`), a safety guard (`src/rico_safety.py`), a subscription/entitlement
gate (`src/services/apply_service.py`), and a phased agentic-UI contract
(`docs/architecture/agentic-ui-action-layer.md`).

What the public ecosystem does **better than Rico today** falls into four buckets:

1. **Browser execution quality** — `browser-use`, `Skyvern`, and `Stagehand` have far more robust,
   self-healing, vision-assisted browser agents than Rico's two thin Playwright engines
   (`indeed_apply`, `naukrigulf_apply`).
2. **Job sourcing breadth** — `JobSpy` / `JobFunnel` aggregate many boards with dedup; Rico is
   currently JSearch/RapidAPI-centric.
3. **Resume/CV tailoring as a structured, scored loop** — `Resume-Matcher` (ATS keyword scoring)
   and multi-agent "generator → judge" patterns (`resume-tailor-agents`).
4. **Multi-agent orchestration ergonomics** — `CrewAI` / `LangGraph` / `AutoGen` show clean role
   decomposition (scout, matcher, tailor, applier, tracker) and graph-based state.

The single biggest **risk** in this ecosystem is **license contamination**: the most feature-rich
auto-apply repos (`AIHawk`, `GodsScion/Auto_job_applier_linkedIn`, `Skyvern`, `firecrawl`,
`resume-lm`) are **AGPL-3.0**. Importing any AGPL code into Rico would force Rico's entire backend
to become AGPL — unacceptable for a commercial SaaS. These are **idea references only**.

The second biggest risk is **product/ethics drift**: nearly every popular auto-apply bot is built to
**mass-submit applications without human review** (the "apply to 100 jobs overnight" pattern). That
is exactly what Rico's safety layer is designed to prevent, what UAE recruiter relationships punish,
and what would get Rico's accounts banned from LinkedIn/Indeed. Rico must **deliberately not copy**
the autonomy posture of these repos.

**Recommendation:** Keep Rico's safety + approval architecture as the differentiator, and selectively
**adapt (re-implement, not copy)** four capabilities behind the existing approval gate:
(a) a multi-source job scout, (b) an ATS-style match/tailoring scorer, (c) a "generate → critique"
resume/cover-letter loop, and (d) a hardened, optional, premium-only browser-assist boundary that
**prepares** applications but never auto-submits without an explicit per-application approval.

---

## 2. GitHub landscape (repository inspection)

Stars/activity are approximate as of June 2026 from public listings. License is the gating field;
where a license could not be verified from the source tree it is marked **VERIFY**.

### Tier A — Browser automation engines

#### A1. browser-use/browser-use
- **URL:** https://github.com/browser-use/browser-use
- **Stars/activity:** ~79k ⭐, very active.
- **Core features:** LLM-driven browser agent; connects any LLM (OpenAI/Anthropic/Gemini/local);
  DOM+vision page understanding; task loop with retries; self/cloud hosting.
- **Architecture:** Agent loop → page-state extraction → LLM action selection → Playwright execution;
  pluggable controller/registry of browser actions.
- **Useful ideas for Rico:** The *action-registry + structured page-state* pattern maps cleanly onto
  Rico's existing `tool_registry`. Their "describe the page as structured elements, let the model
  pick one action, execute, re-observe" loop is the right shape for a **prepare-application** assistant.
- **Risks:** General-purpose autonomy; no built-in approval gating; can be abused for mass submission;
  brittle on anti-bot walls; cost per task is high (many LLM calls).
- **License:** **MIT** — permissive, import-compatible *in principle*.
- **Verdict:** **Adapt (as a guarded dependency, not a copy).** If Rico ever needs a generic browser
  step, prefer depending on the published `browser-use` package behind the approval boundary over
  re-implementing — but only for **prepare/assist**, never blind auto-submit.

#### A2. Skyvern-AI/skyvern
- **URL:** https://github.com/Skyvern-AI/skyvern
- **Stars/activity:** ~22k ⭐, very active.
- **Core features:** LLM + computer-vision browser workflows; no-code workflow builder; Playwright-
  compatible SDK; form-filling on unseen pages.
- **Architecture:** Vision-grounded element detection → planner → executor; workflow graph; cloud
  anti-bot layer (closed).
- **Useful ideas for Rico:** Vision grounding for *application-form field detection* (a real pain in
  UAE portals like Bayt/Naukrigulf/company ATS). The "workflow = graph of steps with checkpoints"
  model is good for an auditable prepare pipeline.
- **Risks:** **AGPL-3.0** core; anti-bot evasion is the closed-source value, so the OSS part is the
  riskier half; heavy infra.
- **License:** **AGPL-3.0** — **do not import.**
- **Verdict:** **Ignore for code; reference for ideas** (vision form-field detection, checkpointed
  workflow). Reimplement independently if pursued.

#### A3. browserbase/stagehand
- **URL:** https://github.com/browserbase/stagehand
- **Stars/activity:** active, multi-language SDKs (TS/Python/Go/…).
- **Core features:** `act` / `extract` / `observe` primitives over Playwright; auto-caching +
  self-healing selectors; choose code vs. natural language per step.
- **Architecture:** Thin LLM layer on Playwright; caches resolved actions to avoid re-inference;
  deterministic replay when DOM is stable.
- **Useful ideas for Rico:** The **`observe → extract → act` triad** and **action caching** are the
  most production-pragmatic ideas in the whole landscape — they cut LLM cost and increase determinism,
  which matters for Rico's audit trail (deterministic replays are auditable).
- **Risks:** Best experience is coupled to Browserbase cloud; self-host is less polished.
- **License:** **MIT.**
- **Verdict:** **Adapt (idea-level).** Mirror the `observe/extract/act` separation and the
  cache-resolved-actions idea inside Rico's own prepare engine.

#### A4. vercel-labs/agent-browser
- **URL:** https://github.com/vercel-labs/agent-browser
- **Core features:** Browser automation CLI for AI agents.
- **Verdict:** **Ignore** (early/thin; nothing Rico needs that A1–A3 don't cover).

### Tier B — Auto-apply / job-application bots

#### B1. AIHawk — AIHawk-FOSS/Auto_Jobs_Applier_AI_Agent (a.k.a. feder-cr/Jobs_Applier_AI_Agent_AIHawk)
- **URL:** https://github.com/AIHawk-FOSS/Auto_Jobs_Applier_AI_Agent
- **Stars/activity:** historically the highest-profile auto-apply project (tens of thousands of stars
  across forks); many derivative repos.
- **Core features:** Automated, personalized mass application; dynamic resume generation; LLM-tailored
  answers to application questions; scrapes corporate sites / LinkedIn (in forks).
- **Architecture:** Config-driven (YAML profile) → scraper → LLM answer/resume generation →
  Selenium/Playwright submit loop.
- **Useful ideas for Rico:** The **structured-profile-as-config** idea (one canonical YAML/JSON of the
  candidate that feeds every downstream step) is good — Rico already has `rico_profiles`; this
  validates the "one profile → many tailored artifacts" model. The **question-answer library** (cache
  of answers to common application questions) is a genuinely useful, safe-to-reimplement idea.
- **Risks:** **Designed for mass auto-submit without per-application review** — the opposite of Rico's
  safety posture; ToS-violating scraping of LinkedIn in forks; can fabricate answers.
- **License:** **AGPL-3.0** (+ docs CC-BY). **Do not import.**
- **Verdict:** **Ignore for code; reference one idea** (reusable answer library, user-confirmed).

#### B2. GodsScion/Auto_job_applier_linkedIn
- **URL:** https://github.com/GodsScion/Auto_job_applier_linkedIn
- **Core features:** Selenium LinkedIn Easy-Apply automation with preference filters.
- **License:** **AGPL-3.0.** **Do not import.**
- **Verdict:** **Ignore.** Same autonomy/ToS problems as B1.

#### B3. wodsuz/EasyApplyJobsBot
- **URL:** https://github.com/wodsuz/EasyApplyJobsBot
- **Core features:** Python/Selenium auto-apply across LinkedIn/Glassdoor; auto-login; auto-fill
  additional questions.
- **Useful ideas for Rico:** Demonstrates the **"answer additional questions" sub-problem** Rico will
  hit when it prepares (not submits) UAE applications.
- **Risks:** Auto-login + credential handling (Rico must **never** store third-party credentials);
  auto-submit; ToS.
- **License:** present but **VERIFY** (varies across forks).
- **Verdict:** **Ignore for code; reference the question-handling sub-problem.**

#### B4. jckimble/LinkedIn-Easy-Apply-Bot · B5. LukasBures/linkedin-easy-apply-bot · B6. nicolomantini/LinkedIn-Easy-Apply-Bot
- **URLs:** https://github.com/jckimble/LinkedIn-Easy-Apply-Bot ·
  https://github.com/LukasBures/linkedin-easy-apply-bot ·
  https://github.com/nicolomantini/LinkedIn-Easy-Apply-Bot
- **Core features:** Single-board Easy-Apply Selenium bots; YAML form answering; session persistence.
- **License:** **MIT** (jckimble, LukasBures).
- **Verdict:** **Ignore for code** (low value vs. A-tier), but the **MIT YAML-form-answering** approach
  in LukasBures is a clean, license-safe reference for a config-driven answer map.

### Tier C — Job sourcing / scraping

#### C1. speedyapply/JobSpy (`python-jobspy`)
- **URL:** https://github.com/speedyapply/JobSpy
- **Stars/activity:** popular, active; on PyPI as `python-jobspy`.
- **Core features:** Concurrent scraping across LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter,
  **Bayt**, **Naukri** and others; pandas DataFrame output; dedup.
- **Architecture:** Per-board scraper classes behind a common interface; concurrency; normalized
  schema. **Bayt + Naukri coverage is directly UAE-relevant.**
- **Useful ideas for Rico:** The **board-agnostic normalized job schema + per-board adapter** pattern
  is exactly what Rico's `src/rico_repo_adapter.py` / jobs layer should look like if it grows beyond
  JSearch. UAE board coverage (Bayt/Naukrigulf) is the gap Rico cares about.
- **Risks:** Scraping ToS exposure; rate limits; **license not declared in `pyproject.toml`**
  (historically MIT but unconfirmed at audit time).
- **License:** **VERIFY** (confirm `LICENSE` file before any dependency or import).
- **Verdict:** **Adapt cautiously.** Prefer it as an *optional dependency* (not vendored) **only after
  license confirmation**, and only as a supplement to JSearch — never replace the licensed JSearch
  feed with raw scraping in production without a ToS/compliance review.

#### C2. PaulMcInnis/JobFunnel
- **URL:** https://github.com/PaulMcInnis/JobFunnel
- **Core features:** Scrape multiple boards → single deduped spreadsheet; YAML-configured searches;
  locale support.
- **Architecture:** `base.py` scraper ABC + per-board subclasses; dedup cache.
- **Useful ideas for Rico:** Clean **scraper ABC** design and **dedup cache** — good reference for a
  Rico `JobSource` interface.
- **License:** **MIT.**
- **Verdict:** **Adapt (idea-level)** — mirror the `JobSource` ABC + dedup pattern; don't vendor.

#### C3. firecrawl/firecrawl
- **URL:** https://github.com/firecrawl/firecrawl
- **Stars/activity:** ~130k ⭐.
- **Core features:** Web → LLM-ready markdown/JSON; handles JS, proxies, rate limits; search+scrape API.
- **Useful ideas for Rico:** Best-in-class **"page → clean structured data"** for parsing a single
  job-post URL or company page the user pastes (Rico's multimodal intake already wants this).
- **Risks:** **AGPL-3.0** core (SDKs MIT). Self-host = AGPL obligations; or use as a **hosted external
  API** (no code import, no AGPL contamination — but it's an outbound data send, governed by Rico's
  network policy and privacy rules).
- **License:** **AGPL-3.0** (core). **Do not import/self-host into Rico's repo.**
- **Verdict:** **Ignore for code.** *Optionally* consume the **hosted API** later for single-URL job
  parsing, treated like any third-party API (privacy review required; never send user PII).

### Tier D — Resume / cover-letter tailoring

#### D1. srbhr/Resume-Matcher
- **URL:** https://github.com/srbhr/Resume-Matcher
- **Stars/activity:** ~26k ⭐, active.
- **Core features:** ATS-style resume↔JD matching; match score; keyword gap suggestions; local LLM
  support.
- **Architecture:** Parse resume + JD → embedding/keyword similarity → scored gaps → suggestions.
- **Useful ideas for Rico:** This is the **single most directly adoptable idea** for Rico: an
  **explainable ATS match score + keyword-gap list** that feeds the Tailored Application Queue. Rico
  already has `rico_match_explainer.py`; a Resume-Matcher-style **keyword-coverage delta** would make
  "why this match / how to improve before applying" concrete and honest (no fabrication).
- **Risks:** None significant for idea-level adoption.
- **License:** **Apache-2.0** — **permissive and import-compatible.**
- **Verdict:** **Adapt.** Re-implement the scoring/keyword-gap concept inside Rico's matcher/tailoring
  service. Apache-2.0 means even small code references are legally safe (with attribution), but Rico
  should prefer a clean re-implementation tuned to UAE roles + Arabic/English.

#### D2. amruthpillai/reactive-resume
- **URL:** https://github.com/amruthpillai/reactive-resume
- **Core features:** Privacy-first resume builder; templates; PDF export; self-hostable.
- **License:** **MIT.**
- **Useful ideas for Rico:** **Structured resume JSON schema** and **server-side PDF rendering**
  pipeline — useful if Rico ever generates a tailored CV artifact for the queue.
- **Verdict:** **Adapt (idea-level)** for the resume-JSON → PDF rendering concept; don't vendor the app.

#### D3. Soroush-aali-bagi/resume-tailor-agents
- **URL:** https://github.com/Soroush-aali-bagi/resume-tailor-agents
- **Core features:** Multi-agent **Generator → Judge** loop that tailors a resume to a JD and scores it.
- **Useful ideas for Rico:** The **generate → critique → revise** loop is the right quality mechanism
  for Rico's cover-letter/CV tailoring (already partially present via `rico_chat_api` cover-letter
  flow). Adding an explicit **critic pass** before showing the draft in the queue raises quality and
  catches fabrication.
- **License:** **VERIFY** (small repo).
- **Verdict:** **Adapt (idea-level):** add a critic step to Rico's existing tailoring path. No code import.

#### D4. JensBender/chatgpt-cover-letter-generator · D5. DoubleGremlin181/cover-letter-llm
- **URLs:** https://github.com/JensBender/chatgpt-cover-letter-generator ·
  https://github.com/DoubleGremlin181/cover-letter-llm
- **Core features:** JD (scraped) + resume → tailored cover letter via OpenAI.
- **Verdict:** **Ignore for code** (Rico already has a cover-letter flow); confirms the
  prompt-contract shape Rico already uses.

#### D6. olyaiy/resume-lm
- **URL:** https://github.com/olyaiy/resume-lm
- **Core features:** Next.js AI resume builder; ATS scoring; AI cover letters; multi-provider
  (OpenAI/Claude/Gemini/DeepSeek/Groq); Supabase/Postgres.
- **Risks:** **AGPL-3.0.** Despite the appealing Next.js + multi-provider + DeepSeek stack (similar to
  Rico's), it **cannot be copied.**
- **License:** **AGPL-3.0.** **Do not import.**
- **Verdict:** **Ignore for code; reference** the multi-provider abstraction (Rico already has its own
  in `src/rico_openai_agent.py`).

### Tier E — Multi-agent orchestration frameworks

#### E1. crewAIInc/crewAI
- **URL:** https://github.com/crewaiinc/crewai
- **Stars/activity:** ~44k ⭐.
- **Core features:** Role/goal/backstory agents assembled into a "crew" with tasks; sequential or
  hierarchical processes; tools.
- **Useful ideas for Rico:** Clean **role decomposition** vocabulary (Scout / Matcher / Tailor /
  Applier / Tracker) maps onto Rico's planned agent roles. Good mental model; Rico does **not** need
  the dependency — its `agent_runtime` + `tool_registry` already cover dispatch.
- **License:** **MIT.**
- **Verdict:** **Adapt (idea-level).** Borrow the role taxonomy and task-decomposition vocabulary;
  keep Rico's own runtime as the executor.

#### E2. langchain-ai/langgraph
- **URL:** https://github.com/langchain-ai/langgraph
- **Core features:** Graph of nodes/edges with explicit, durable state; checkpointing; human-in-the-loop
  interrupts.
- **Useful ideas for Rico:** **Human-in-the-loop interrupts + durable checkpointed state** is precisely
  the abstraction behind an approval queue. Rico's approval gate is a hand-rolled version of LangGraph's
  `interrupt()`. Validates the design; Rico can keep its own implementation.
- **License:** **MIT** (LangSmith/cloud are paid).
- **Verdict:** **Adapt (idea-level)** — model the Tailored Application Queue as a graph with an
  interrupt node at the apply step. No hard dependency required.

#### E3. microsoft/autogen (and AG2 fork)
- **URL:** https://github.com/microsoft/autogen
- **Stars/activity:** ~55k ⭐.
- **Core features:** Conversational multi-agent collaboration; tool use; group chat patterns.
- **License:** **MIT** (docs CC-BY-4.0; community AG2 fork exists).
- **Verdict:** **Ignore (dependency); reference** group-chat critique patterns if a multi-critic
  tailoring loop is ever built.

---

## 3. Competitive feature matrix

Legend: ✅ strong · 🟡 partial · ❌ absent · 🔒 intentionally gated by safety.

| Capability | Rico today | browser-use | Skyvern | Stagehand | AIHawk | JobSpy | Resume-Matcher | CrewAI/LangGraph |
|---|---|---|---|---|---|---|---|---|
| Single action dispatcher + idempotency | ✅ | ❌ | 🟡 | ❌ | ❌ | ❌ | ❌ | 🟡 |
| Audit trail of every action | ✅ | ❌ | 🟡 | ❌ | ❌ | ❌ | ❌ | 🟡 |
| Safety guard / approval gate | ✅🔒 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 🟡 (HITL) |
| Subscription/entitlement gating | ✅ | ❌ | 🟡 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Robust browser execution | 🟡 (2 thin engines) | ✅ | ✅ | ✅ | 🟡 | ❌ | ❌ | ❌ |
| Vision-assisted form filling | ❌ | 🟡 | ✅ | 🟡 | ❌ | ❌ | ❌ | ❌ |
| Multi-board job sourcing | 🟡 (JSearch) | ❌ | ❌ | ❌ | 🟡 | ✅ (incl. Bayt/Naukri) | ❌ | ❌ |
| ATS match score + keyword gaps | 🟡 (`rico_match_explainer`) | ❌ | ❌ | ❌ | 🟡 | ❌ | ✅ | ❌ |
| Resume/cover-letter tailoring | ✅ (chat flow) | ❌ | ❌ | ❌ | ✅ | ❌ | 🟡 | ❌ |
| Generate → critique quality loop | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Approval queue (HITL) | 🟡 (designed, partial) | ❌ | 🟡 | ❌ | ❌ | ❌ | ❌ | ✅ |
| Arabic/English product UX | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| UAE market focus | ✅ | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ |
| Commercial-safe license | ✅ | ✅ MIT | ❌ AGPL | ✅ MIT | ❌ AGPL | ⚠️ VERIFY | ✅ Apache | ✅ MIT |

**Reading the matrix:** Rico's moat is the left column (dispatch, audit, safety, gating, locale, UAE
focus) — none of the popular apply bots have it. Rico's gaps are browser robustness, multi-board
sourcing, ATS scoring, and the critique loop — all adoptable as **ideas** from **permissive** repos.

---

## 4. What Rico should copy (as ideas, not code)

1. **ATS match score + keyword-gap list** (from Resume-Matcher, Apache-2.0) — explainable, honest
   "how to improve before you apply." Feeds the queue.
2. **`observe → extract → act` + action caching** (from Stagehand, MIT) — deterministic, cheaper,
   auditable browser steps for the **prepare** stage.
3. **Board-agnostic `JobSource` adapter + dedup** (from JobFunnel MIT / JobSpy) — multi-source sourcing
   incl. UAE boards (Bayt, Naukrigulf) layered on top of JSearch.
4. **Generate → critique → revise loop** (from resume-tailor-agents / AutoGen) — a critic pass before
   any draft reaches the user, catching fabrication and weak claims.
5. **Reusable answer library** (from AIHawk idea, re-implemented) — cache of the user's *own,
   user-confirmed* answers to common application questions; never auto-fabricated.
6. **Role taxonomy + HITL interrupt model** (from CrewAI/LangGraph, MIT) — name the agents and model
   the queue as a graph with an interrupt at apply.

## 5. What Rico must NOT copy

1. **Any AGPL/GPL/unknown-license code** — `AIHawk`, `GodsScion`, `Skyvern`, `firecrawl` (core),
   `resume-lm`. Ideas only; clean-room re-implementation if pursued.
2. **Mass auto-submit without per-application review** — the core behavior of every apply bot.
   Violates Rico's safety layer, UAE recruiter norms, and platform ToS.
3. **Third-party credential storage / auto-login** — Rico must never store a user's LinkedIn/Indeed
   password or session to log in on their behalf.
4. **ToS-violating scraping** of LinkedIn/Indeed behind auth — keep production sourcing on the
   licensed JSearch feed; treat scrapers as optional, compliance-reviewed supplements.
5. **Answer fabrication** — generating made-up experience/answers to pass screening questions. Already
   blocked by `rico_safety.DANGEROUS_AUTOMATION_PATTERNS`; keep it that way.
6. **Detection-evasion / anti-bot defeat** (Skyvern's closed value) — out of scope and against ToS.

---

## 6. Rico Agentic Vision v1

### 6.1 Agent roles (logical, executed by existing `agent_runtime` — not new daemons)

| Agent role | Responsibility | Backed by today | Impact class |
|---|---|---|---|
| **Scout** | Find + dedup jobs across sources (JSearch + future UAE boards) | `jobs` router, `rico_repo_adapter` | low |
| **Matcher** | Score job↔profile, produce match% + keyword gaps + "why" | `rico_match_explainer`, learning_repo | low |
| **Tailor** | Draft CV tweaks + cover letter, run critic pass | `rico_chat_api` cover-letter flow, `messaging_tools.draft_message` | low/medium |
| **Preparer** | Assemble a complete, reviewable application package (no submit) | new prepare service (future) | medium |
| **Applier** | Submit **only** after explicit approval | `apply_service.apply_to_job(approved=True)` | high 🔒 |
| **Tracker** | Record lifecycle, reminders, follow-ups | `user_job_context_repo`, follow-up reminders (#355) | low |

All roles dispatch through `agent_runtime.handle_action()`. No role bypasses idempotency, audit, or
the approval gate.

### 6.2 User flow

```text
Discover → Match → Review → Tailor → Prepare → APPROVE (human) → Apply → Track → Follow-up
                                                   ▲
                                      mandatory human-in-the-loop interrupt
```

### 6.3 Approval flow (maps to existing code)

```text
User asks to apply
  → agent_runtime.handle_action(action="apply", ...)
  → apply_service.apply_to_job(approved=False)
  → returns status="approval_required"
  → runtime attaches permission_request (build_apply_permission_dict)
  → UI renders PermissionPromptCard (agentic-ui-action-layer Phase 4)
  → user clicks Approve
  → /actions/execute (user_id from JWT) sets pre_approved=True
  → handle_action injects {"_approved": True}
  → apply_to_job(approved=True) → engine OR manual_required
  → audit_repo.log_action(...) records outcome
```

This is **already the implemented contract** — the vision keeps it intact and builds the queue on top.

### 6.4 Policy gate (order of enforcement — already in `apply_service`/`runtime`)

1. **Safety guard** (`rico_safety.check_message` / `check_action`) — blocks fabrication, privacy,
   harassment, discrimination, unapproved high-impact actions.
2. **Approval guard** (`RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`) — no submit without `approved`.
3. **Global automation flag** (`RICO_ENABLE_AUTO_APPLY`) — off ⇒ `manual_required` for everyone.
4. **Subscription entitlement** (`application_automation_enabled`) — premium gate, 402 otherwise.
5. **Idempotency** (MD5 `user_id:action:job_key`) — no double-apply.
6. **Engine routing** — only known, ToS-compatible engines.

### 6.5 Audit trail

Every action already writes to `audit_repo.log_action(...)` with `action_id`, `action_type`,
`user_email`, `job_id/title/company`, `result_status`, `result_message`, `duration_ms`,
`failure_reason`, `source`. The vision adds **queue-state transitions** (queued → approved →
submitted/failed) as audit events using the same schema (no schema change required for the events;
a small `application_queue` table is needed only for persistence — see roadmap).

### 6.6 Browser automation boundary

```text
ALLOWED  (premium, approved, per-application):
  - Open the official apply URL
  - Pre-fill fields from the user's confirmed profile
  - Surface remaining/unknown questions to the user
  - Stop at the final submit button and request approval

FORBIDDEN (always):
  - Auto-submit without per-application approval
  - Logging into third-party accounts with stored credentials
  - Defeating CAPTCHAs / anti-bot
  - Scraping behind auth in violation of ToS
  - Fabricating answers to any field
```

Implementation note: a future hardened browser-assist should re-use the `observe/extract/act` +
action-cache idea (Stagehand) and route through `apply_service` so the approval/entitlement gates
remain the only path to submit. Existing `_is_browser_unavailable` → `manual_required` fallback stays.

### 6.7 Failure handling

| Failure | Behavior |
|---|---|
| Browser unavailable | `manual_required` + apply URL (already implemented) |
| Engine error | user-safe message; raw logged server-side only (already implemented) |
| LLM provider down | provider fallback chain (DeepSeek → HF → keyword); never block the user |
| Low extraction confidence | surface confidence + ask user to confirm (multimodal intake rule) |
| Duplicate action | idempotency returns `ok=True` "already executed" (already implemented) |
| Approval timeout | item stays queued; nothing submitted; no silent expiry into submit |

### 6.8 Subscription gating

- Sourcing/matching/tailoring/preparing: available per existing plan tiers (low/medium impact).
- **Application automation (Applier role):** premium-only via
  `entitlements.application_automation_enabled`; Free/Pro get a clear upgrade prompt (already coded).
- Queue is visible to all tiers; **submit** action is the gated one.

### 6.9 Observability

- Reuse audit log as the system-of-record for agent actions.
- Add structured log keys already in use (`runtime_execute`, `runtime_apply_gated`,
  `browser_unavailable`, `engine_not_active`).
- Future: a lightweight `/pipeline/status`-style read for queue depth, approval latency, submit
  success rate, and per-source match yield. No new external observability vendor required for v1.

---

## 7. Architecture proposal (delta over current system)

```text
                         ┌─────────────────────────────────────────────┐
                         │            Rico chat / agentic UI            │
                         │  (action cards · permission prompts · queue) │
                         └───────────────┬─────────────────────────────┘
                                         │
                              agent_runtime.handle_action()   ← single boundary (unchanged)
                                         │
   ┌──────────┬───────────┬─────────────┼─────────────┬───────────────┬───────────────┐
   ▼          ▼           ▼             ▼             ▼               ▼               ▼
 Scout     Matcher      Tailor      Preparer       Applier 🔒       Tracker        Safety/Policy
(JobSource (ATS score  (gen→critic  (assemble     (apply_service   (lifecycle +    (rico_safety +
 adapters) +keyword gap) loop)       package)      approved=True)   reminders)      gates, unchanged)
   │          │           │             │             │               │
   └──────────┴───────────┴─────────────┴─────────────┴───────────────┘
                                         │
                          audit_repo.log_action()  +  application_queue (new table)
```

**New, additive pieces only** (no rewrites):
- `JobSource` adapter interface (idea from JobFunnel) — optional, additive to JSearch.
- Match-scoring/keyword-gap module (idea from Resume-Matcher) — additive to `rico_match_explainer`.
- Critic pass in tailoring (idea from resume-tailor-agents) — additive to existing draft flow.
- `application_queue` persistence + queue API/UI (Phase 5 of the existing agentic-UI plan).
- Optional premium browser-assist `prepare` engine behind `apply_service`.

---

## 8. Safety and compliance policy (binding)

1. **License firewall.** No AGPL/GPL/unknown code enters the repo. Permissive (MIT/Apache/BSD) code
   may be referenced; prefer clean re-implementation. Record license provenance in PR descriptions.
2. **Approval is non-negotiable.** `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` stays default.
   Submit happens only via the `pre_approved` path with a traceable `permission_id`.
3. **No credential custody.** Rico never stores third-party site passwords or sessions.
4. **No fabrication.** Tailoring uses only user-confirmed facts; `rico_safety` patterns stay active;
   critic pass flags unsupported claims.
5. **ToS-respecting sourcing.** Production sourcing stays on licensed JSearch; scrapers are optional,
   compliance-reviewed supplements, never auth-bypassing.
6. **Privacy.** PII redaction before logs/model calls (`rico_safety.redact_sensitive_data`); minimal
   retention for sensitive docs; no PII sent to third-party scrape/parse APIs.
7. **Locale parity.** Every new user-facing action/label ships Arabic + English.
8. **Auditability.** Every queued/approved/submitted transition is logged.
9. **Subscription honesty.** Gated features show a clear upgrade path, never a silent failure.

---

## 9. Implementation roadmap (priority-ranked feature gap map)

| # | Current Rico capability | Best external pattern | Recommended Rico implementation | Priority |
|---|---|---|---|---|
| 1 | Approval contract exists; **no persistent queue** | LangGraph HITL interrupt | Persist Tailored Application Queue (`application_queue` table + API + UI), built on existing approval contract | **P0** |
| 2 | Match "why" via `rico_match_explainer` | Resume-Matcher ATS scoring (Apache-2.0) | Add explainable match% + keyword-gap list to job detail + queue | **P0** |
| 3 | Cover-letter flow exists, no critic | resume-tailor-agents / AutoGen | Add a critic pass before drafts surface; flag unsupported claims | **P1** |
| 4 | JSearch-only sourcing | JobFunnel `JobSource` ABC / JobSpy (Bayt, Naukri) | Define `JobSource` interface + dedup; add UAE boards as optional adapters (license + ToS reviewed) | **P1** |
| 5 | 2 thin Playwright engines, no vision | Stagehand `observe/extract/act` + cache; browser-use (MIT) | Hardened **prepare-only** browser-assist behind `apply_service`, premium-gated, stop-at-submit | **P2** |
| 6 | Single canonical profile | AIHawk answer-library idea | User-confirmed reusable answer library for common application questions | **P2** |
| 7 | Resume artifacts in chat | reactive-resume JSON→PDF (MIT) | Optional tailored-CV PDF artifact attached to queue items | **P2** |

---

## 10. PR breakdown (small, safe, sequenced)

> All PRs follow `AI_WORKSPACE/OPERATING_RULES.md` and `PR_CHECKLIST.md`: one scope per branch,
> tests, no secrets, no unrelated files, rollback plan. **None of these are implemented by this
> document** — it is design-only.

**PR-0 (this document).** Add `docs/rico-agentic-vision-github-intelligence.md`. No runtime change.
Tests: none (docs only).

**PR-1 — Application Queue persistence (P0).**
- Add: migration `0NN_application_queue.sql` (status enum: queued/approved/submitted/failed/cancelled),
  `src/repositories/application_queue_repo.py`, `src/api/routers/` queue endpoints (read/approve/cancel).
- Change: `agent_runtime` emits queue transition audit events; reuse `audit_repo`.
- Tests: `tests/test_application_queue_repo.py` (CRUD, idempotency), router tests with `TestClient`,
  JWT-isolation test (no cross-user reads). No live DB.
- Rollout: ship behind a read-only feature flag first; UI in PR-1b (`ApprovalQueueDrawer.tsx`).

**PR-2 — Explainable match score + keyword gaps (P0).**
- Add: `src/services/match_scoring.py` (keyword coverage delta, Arabic/English aware), unit-tested.
- Change: job detail + queue payload include `match_score` + `keyword_gaps` (additive fields only).
- Tests: `tests/test_match_scoring.py` (deterministic scoring, locale, no fabrication).

**PR-3 — Tailoring critic pass (P1).**
- Change: cover-letter/CV draft path runs a critic step that flags unsupported claims before display.
- Tests: critic flags fabricated experience; honest drafts pass; provider-fallback safe.

**PR-4 — `JobSource` adapter interface + dedup (P1).**
- Add: `src/sources/base.py` (`JobSource` ABC), JSearch adapter wrapping current path, dedup util.
- Tests: adapter contract + dedup; **no new live network in unit tests** (mock sources).
- Note: additional UAE board adapters are **separate, later PRs** gated on license + ToS review.

**PR-5 — Prepare-only browser-assist (P2, premium).**
- Add: prepare engine using `observe/extract/act` shape; routes through `apply_service`; stops at
  submit; never stores credentials.
- Tests: prepare cannot submit without `approved=True`; entitlement gate enforced; browser-unavailable
  → `manual_required`.

**PR-6 — Reusable answer library + tailored-CV PDF (P2).**
- Add: user-confirmed answer store; optional resume-JSON → PDF artifact attached to queue items.
- Tests: answers never auto-fabricated; PDF render deterministic.

---

## 11. Test plan (cross-cutting)

- **Safety regression:** every new action path passes through `rico_safety` and the approval gate;
  add tests asserting submit is impossible without `pre_approved`/`approved=True`.
- **Idempotency:** queue + apply remain idempotent on the MD5 `user_id:action:job_key` key.
- **JWT isolation:** queue and queue-state reads derive identity from JWT, never request body.
- **Entitlement:** automation features 402 for non-premium when `RICO_ENABLE_AUTO_APPLY=true`.
- **Locale:** Arabic + English labels for every new user-facing action.
- **No live externals in unit tests:** mock JSearch, OpenAI/DeepSeek/HF, Telegram, Playwright.
- **Frontend:** `npm run build` in `apps/web`; mobile-viewport smoke for queue/approval UI.
- **Determinism for audit:** prepare/browser steps cache resolved actions so replays are auditable.

---

## 12. License compatibility appendix

| Repo | License | Import into Rico? | Use as idea? |
|---|---|---|---|
| browser-use | MIT | ✅ (as dependency, gated) | ✅ |
| Stagehand | MIT | ✅ (dependency) | ✅ |
| JobFunnel | MIT | ✅ (idea/clean-room) | ✅ |
| Resume-Matcher | Apache-2.0 | ✅ (with attribution) | ✅ |
| reactive-resume | MIT | ✅ (idea) | ✅ |
| CrewAI / LangGraph / AutoGen | MIT (docs CC-BY) | ✅ (optional dep) | ✅ |
| JobSpy / python-jobspy | **VERIFY** (LICENSE unconfirmed) | ⚠️ only after confirming | ✅ |
| resume-tailor-agents | VERIFY | ⚠️ idea only | ✅ |
| EasyApplyJobsBot (forks) | VERIFY | ❌ | 🟡 |
| **Skyvern** | **AGPL-3.0** | ❌ | ✅ (clean-room) |
| **AIHawk** + forks | **AGPL-3.0** | ❌ | 🟡 (one idea) |
| **GodsScion/Auto_job_applier_linkedIn** | **AGPL-3.0** | ❌ | ❌ |
| **firecrawl** (core) | **AGPL-3.0** | ❌ (hosted API only, later) | ✅ |
| **resume-lm** | **AGPL-3.0** | ❌ | 🟡 |

**Rule of thumb:** MIT/Apache/BSD → may depend on or reference. AGPL/GPL/unknown → **idea only**,
clean-room re-implementation, no source copied, license verified before any dependency is added.

---

## Sources

- [browser-use/browser-use](https://github.com/browser-use/browser-use)
- [Skyvern-AI/skyvern](https://github.com/Skyvern-AI/skyvern)
- [browserbase/stagehand](https://github.com/browserbase/stagehand)
- [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)
- [AIHawk-FOSS/Auto_Jobs_Applier_AI_Agent](https://github.com/AIHawk-FOSS/Auto_Jobs_Applier_AI_Agent)
- [GodsScion/Auto_job_applier_linkedIn](https://github.com/GodsScion/Auto_job_applier_linkedIn)
- [wodsuz/EasyApplyJobsBot](https://github.com/wodsuz/EasyApplyJobsBot)
- [jckimble/LinkedIn-Easy-Apply-Bot](https://github.com/jckimble/LinkedIn-Easy-Apply-Bot)
- [LukasBures/linkedin-easy-apply-bot](https://github.com/LukasBures/linkedin-easy-apply-bot)
- [nicolomantini/LinkedIn-Easy-Apply-Bot](https://github.com/nicolomantini/LinkedIn-Easy-Apply-Bot)
- [speedyapply/JobSpy](https://github.com/speedyapply/JobSpy)
- [PaulMcInnis/JobFunnel](https://github.com/PaulMcInnis/JobFunnel)
- [firecrawl/firecrawl](https://github.com/firecrawl/firecrawl)
- [srbhr/Resume-Matcher](https://github.com/srbhr/Resume-Matcher)
- [amruthpillai/reactive-resume](https://github.com/amruthpillai/reactive-resume)
- [Soroush-aali-bagi/resume-tailor-agents](https://github.com/Soroush-aali-bagi/resume-tailor-agents)
- [JensBender/chatgpt-cover-letter-generator](https://github.com/JensBender/chatgpt-cover-letter-generator)
- [DoubleGremlin181/cover-letter-llm](https://github.com/DoubleGremlin181/cover-letter-llm)
- [olyaiy/resume-lm](https://github.com/olyaiy/resume-lm)
- [crewAIInc/crewAI](https://github.com/crewaiinc/crewai)
- [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)
- [microsoft/autogen](https://github.com/microsoft/autogen)
</content>
</invoke>
