# Rico Agentic Vision — GitHub Intelligence Report (Consolidated)

_Audit date: 2026-06-21 · Author: Rico AI engineering audit · Status: design-only, no runtime code changes_

> **Consolidation note.** This is the **single canonical version**, produced by merging two parallel
> GitHub-intelligence audits run in separate sessions:
> - **Audit A** (browser engines, scrapers, resume tooling, orchestration frameworks): browser-use,
>   Skyvern, Stagehand, JobSpy, JobFunnel, firecrawl, Resume-Matcher, reactive-resume,
>   CrewAI/LangGraph/AutoGen, LinkedIn Easy-Apply bots.
> - **Audit B** (closest-philosophy analogs + governance): santifer/career-ops,
>   microsoft/agent-governance-toolkit, Rayyan9477/AutoApply-AI, feder-cr/AIHawk,
>   GodsScion/Auto_job_applier_linkedIn.
> The two sets barely overlapped, so both are folded into one report with a unified matrix, one
> roadmap, and one license appendix. Earlier duplicate copies (incl. the PR #698 draft) are
> superseded by this file.

> **Scope guard.** This is a research + design deliverable. It does **not** change runtime behavior.
> Every external repository is a **reference only**. No external code is copied into Rico. AGPL/GPL/
> unknown-license code is excluded from import. Any apply action stays **user-approved** and routed
> through `agent_runtime.handle_action()` behind `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`.

---

## 1. Executive summary

Rico already owns the **hard, defensible parts** of an agentic job-search system that most public
projects lack: a single action dispatcher (`src/agent/runtime.py`), a declarative tool registry
(`src/agent/registry/tool_registry.py`), MD5 idempotency keys, an audit log
(`src/repositories/audit_repo.py`), a safety guard (`src/rico_safety.py`), a subscription/entitlement
gate (`src/services/apply_service.py`), and a phased agentic-UI contract
(`docs/architecture/agentic-ui-action-layer.md`).

Two findings reshape the picture versus a single-session audit:

1. **The market's most-loved project validates Rico's exact philosophy.** `santifer/career-ops`
   (~50k ⭐, **MIT**) is a Claude-Code-based job-search agent that is **draft-only and human-gated** —
   it tailors a CV per listing, evaluates fit A–F, and *never auto-submits*. Its popularity proves the
   demand is for the **safe, assistive** pattern, not the spam-apply pattern.
2. **There is now an off-the-shelf blueprint for Rico's policy gate.**
   `microsoft/agent-governance-toolkit` (~3.3k ⭐, **MIT**, opened Apr 2026) provides YAML-declarative
   policy, a `safe_tool` wrapper that evaluates policy on every call, immutable decision logging, and
   coverage of the OWASP Agentic Top 10. Rico's hand-rolled safety+approval logic can be hardened into
   a declarative `policy_gate` directly inspired by this (MIT, pattern-safe).

What the ecosystem does **better than Rico today** falls into five buckets:

1. **Browser execution quality** — `browser-use`, `Skyvern`, `Stagehand` have far more robust,
   self-healing, vision-assisted browser agents than Rico's two thin Playwright engines
   (`indeed_apply`, `naukrigulf_apply`).
2. **Job sourcing breadth** — `JobSpy` / `JobFunnel` aggregate many boards with dedup (JobSpy even
   covers **Bayt** and **Naukri** — UAE-relevant); Rico is JSearch/RapidAPI-centric.
3. **ATS scoring + per-listing tailoring** — `Resume-Matcher` (keyword gaps), `AutoApply-AI` (FAISS
   ATS scoring + HITL queue), `career-ops` (A–F fit + per-listing CV).
4. **Generate → critique quality loop** — multi-agent "generator → judge" patterns
   (`resume-tailor-agents`, AutoGen group-chat).
5. **Declarative governance** — `agent-governance-toolkit` policy-as-config.

The single biggest **risk** is **license contamination**: the most feature-rich apply repos
(`AIHawk`, `GodsScion`, `Skyvern`, `firecrawl` core, `resume-lm`) are **AGPL/GPL**. Importing any would
force Rico's backend to inherit AGPL — unacceptable for a commercial SaaS. **Ideas only, clean-room.**

The second biggest risk is **autonomy drift**: most apply bots mass-submit without human review — the
exact behavior Rico's safety layer is built to prevent, that UAE recruiter relationships punish, and
that gets accounts banned. Rico must **deliberately not copy** that posture. Notably, the most popular
project (`career-ops`) *agrees* with Rico here.

**Recommendation.** Keep Rico's safety + approval architecture as the differentiator. Then, behind the
existing approval gate, **adapt (re-implement, not copy)**: (a) a declarative policy gate + immutable
audit (from agent-governance-toolkit, MIT), (b) an ATS match/keyword-gap scorer (from Resume-Matcher,
Apache-2.0), (c) a persistent human-gated application queue (from AutoApply-AI / career-ops), (d) a
"generate → critique" tailoring loop, (e) a multi-source `JobSource` adapter, and (f) an optional
premium **prepare-only** browser boundary that never auto-submits. Rico's real moat — Arabic CV
tailoring, UAE boards, Emiratisation/visa/MOHRE awareness — is covered by **no repo on Earth**
(see §5).

---

## 2. GitHub landscape (repository inspection)

Stars/activity are approximate as of June 2026 from public listings. License is the gating field;
where a license could not be verified from the source tree it is marked **VERIFY**.

### Tier 0 — Closest philosophical analogs (study these first)

#### 0A. santifer/career-ops ⭐ closest match to Rico's philosophy
- **URL:** https://github.com/santifer/career-ops
- **Stars/activity:** ~48–55k ⭐ (sources vary), very active; 3k+ Discord community.
- **Core features:** AI job-search system built on Claude Code; 14 "skill modes"; Go dashboard; PDF
  generation; **batch processing with parallel sub-agents** (10+ offers at once); paste a job URL →
  classify role archetype → **A–F fit evaluation** (reasoning over CV vs JD, not keyword match) →
  tailored ATS-optimized CV/PDF per listing → tracked opportunity; scans portals (Greenhouse, Ashby,
  Lever, company pages) via Playwright. **Draft-only — never auto-submits.**
- **Architecture:** Skill-mode dispatch (analogous to Rico's tool registry); per-listing reasoning
  pipeline; batch fan-out via sub-agents; artifact generation (report + PDF).
- **Useful ideas for Rico:** (1) The **A–F fit evaluation as reasoning, not keyword matching** is a
  better "why this match" than pure ATS scoring — pair it with Resume-Matcher-style keyword gaps for
  an explainable, honest score. (2) **Batch parallel evaluation via sub-agents** maps onto Rico's
  Scout/Matcher roles for "evaluate my 10 saved jobs." (3) **Draft-only at 50k stars** is the market
  proof that Rico's human-gated posture is the *winning* product stance, not a limitation.
- **Risks:** Single-user CLI tool, not multi-tenant SaaS (no JWT isolation, no subscription gating —
  Rico is ahead here); Claude-Code-coupled.
- **License:** **MIT** — permissive, reference-safe (clean re-implementation preferred).
- **Verdict:** **Adapt (idea-level).** The single best philosophical reference: validates draft-only,
  donates the A–F-fit and batch-sub-agent ideas.

#### 0B. Rayyan9477/AutoApply-AI (Agentic Browser Automation for Job Search)
- **URL:** https://github.com/Rayyan9477/AutoApply-AI-Agentic-Browser-Automation-for-Job-Search
- **Core features:** Job discovery → **FAISS vector ATS scoring** (skills/keywords/experience/
  education) → LLM tailoring → Playwright submission with a **human-in-the-loop review workflow** and
  a **batch processing queue**; real-time WebSocket progress; analytics dashboard.
- **Architecture:** SQLite/Postgres + **Redis queue/cache** + FAISS indices; config knobs like
  `APPLY_MODE=batch`, `MIN_ATS_SCORE=0.75`.
- **Useful ideas for Rico:** This is the **closest architectural match to Rico's planned Tailored
  Application Queue** — HITL gate + batch queue + ATS threshold gating. The `MIN_ATS_SCORE` gate is a
  clean idea (don't queue an apply below a score the user sets). Redis is already in Rico's env
  (`RICO_REDIS_URL`).
- **Risks:** Still submits via Playwright (keep Rico's per-application approval); smaller/younger.
- **License:** **not stated → VERIFY** before any dependency.
- **Verdict:** **Adapt (idea-level):** queue + ATS-threshold gating + WebSocket progress. No code import.

### Tier A — Browser automation engines

#### A1. browser-use/browser-use
- **URL:** https://github.com/browser-use/browser-use · ~79k ⭐, very active.
- **Core:** LLM-driven browser agent; any LLM; DOM+vision page state; action loop with retries.
- **Architecture:** Agent loop → structured page-state → LLM action selection → Playwright execute →
  re-observe; pluggable action controller/registry.
- **Ideas for Rico:** Action-registry + structured page-state maps onto Rico's `tool_registry`;
  right shape for a **prepare-application** assistant.
- **Risks:** General-purpose autonomy; no approval gate; abusable for mass submit; high LLM cost.
- **License:** **MIT.** **Verdict: Adapt** (as a guarded dependency for prepare/assist only).

#### A2. Skyvern-AI/skyvern
- **URL:** https://github.com/Skyvern-AI/skyvern · ~22k ⭐.
- **Core:** LLM + computer-vision browser workflows; no-code workflow builder; Playwright-compatible.
- **Ideas for Rico:** **Vision form-field detection** for UAE portals (Bayt/Naukrigulf/company ATS);
  checkpointed workflow graph.
- **License:** **AGPL-3.0.** **Verdict: Ignore for code; reference ideas (clean-room).**

#### A3. browserbase/stagehand
- **URL:** https://github.com/browserbase/stagehand · active, multi-language SDKs.
- **Core:** `act`/`extract`/`observe` over Playwright; **auto-caching + self-healing selectors**.
- **Ideas for Rico:** The **`observe → extract → act` triad + action caching** is the most
  production-pragmatic idea in the landscape — cuts LLM cost and makes browser steps **deterministic
  and auditable** (replayable).
- **License:** **MIT.** **Verdict: Adapt (idea-level)** inside Rico's prepare engine.

#### A4. vercel-labs/agent-browser — thin CLI. **Verdict: Ignore.**

### Tier B — Auto-apply / job-application bots (caution: autonomy + license)

#### B1. feder-cr/Jobs_Applier_AI_Agent_AIHawk (AIHawk)
- **URL:** https://github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk
- **Stars/activity:** **29.6k ⭐ / 4.5k forks**; **archived by owner 2026-05-17 (read-only)**; team
  moved to a proprietary product.
- **Core:** Automated mass application; dynamic resume generation; LLM-tailored answers; scraping.
- **Ideas for Rico:** The **reusable answer library** (cache of answers to common application
  questions) is a safe idea **if re-implemented with user-confirmed answers only**.
- **Risks:** Built for **mass auto-submit without per-application review**; ToS-violating scraping in
  forks; can fabricate answers; now unmaintained.
- **License:** **AGPL-3.0** (docs CC-BY). **Verdict: Ignore for code; reference one idea.**

#### B2. GodsScion/Auto_job_applier_linkedIn
- **URL:** https://github.com/GodsScion/Auto_job_applier_linkedIn · ~2.5k ⭐.
- **Core:** Selenium LinkedIn Easy-Apply automation; preference filters; full automation.
- **License:** **GPL/AGPL-3.0.** **Verdict: Ignore.** The model of *what Rico must not become*.

#### B3. Liam-Frost/AutoApply
- **URL:** https://github.com/Liam-Frost/AutoApply
- **Core:** Personal job agent — discovery, fit scoring, tailored materials, form filling,
  **human-gated submission**, tracking. Philosophically aligned (human-gated).
- **License:** **VERIFY.** **Verdict: Reference (idea-level)** — confirms HITL submission pattern.

#### B4. wodsuz/EasyApplyJobsBot · jckimble/… · LukasBures/… · nicolomantini/…
- Single-board Selenium Easy-Apply bots; YAML form answering; session persistence.
- **Licenses:** mostly **MIT** (jckimble, LukasBures) / **VERIFY** (forks).
- **Verdict: Ignore for code.** LukasBures' MIT **YAML answer-map** is a clean license-safe reference.

### Tier C — Job sourcing / scraping

#### C1. speedyapply/JobSpy (`python-jobspy`)
- **URL:** https://github.com/speedyapply/JobSpy · popular, active.
- **Core:** Concurrent scraping across LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter, **Bayt**,
  **Naukri**; normalized schema + dedup.
- **Ideas for Rico:** Board-agnostic normalized schema + per-board adapter; **Bayt/Naukri = UAE gap**.
- **Risks:** Scraping ToS; **license not declared in `pyproject.toml`**.
- **License:** **VERIFY.** **Verdict: Adapt cautiously** as optional dependency (supplement JSearch,
  not replace it) — only after license + ToS review.

#### C2. PaulMcInnis/JobFunnel
- **URL:** https://github.com/PaulMcInnis/JobFunnel
- **Core:** Scrape → deduped spreadsheet; scraper ABC + per-board subclasses; dedup cache.
- **License:** **MIT.** **Verdict: Adapt (idea-level)** — mirror the `JobSource` ABC + dedup.

#### C3. firecrawl/firecrawl
- **URL:** https://github.com/firecrawl/firecrawl · ~130k ⭐.
- **Core:** Web → LLM-ready markdown/JSON; proxies, JS, rate limits handled.
- **Ideas for Rico:** Best "single job-post URL → clean structured data" for multimodal intake.
- **License:** **AGPL-3.0** core (SDKs MIT). **Verdict: Ignore for code;** optionally consume the
  **hosted API** later (no PII; privacy review; governed by Rico's network policy).

### Tier D — Resume / cover-letter tailoring

#### D1. srbhr/Resume-Matcher
- **URL:** https://github.com/srbhr/Resume-Matcher · ~26k ⭐.
- **Core:** ATS-style resume↔JD matching; match score; keyword-gap suggestions; local LLM.
- **Ideas for Rico:** **Most directly adoptable scoring idea** — explainable match% + keyword-gap list
  feeding the queue; complements `rico_match_explainer` and career-ops' A–F fit.
- **License:** **Apache-2.0.** **Verdict: Adapt** (clean re-implementation, UAE/Arabic-tuned).

#### D2. amruthpillai/reactive-resume
- **URL:** https://github.com/amruthpillai/reactive-resume · **MIT.**
- **Ideas for Rico:** Structured resume-JSON schema + server-side PDF rendering for queue artifacts.
- **Verdict: Adapt (idea-level).**

#### D3. Soroush-aali-bagi/resume-tailor-agents
- **URL:** https://github.com/Soroush-aali-bagi/resume-tailor-agents
- **Core:** Multi-agent **Generator → Judge** loop; scores the tailored resume.
- **Ideas for Rico:** Add an explicit **critic pass** before drafts surface (catches fabrication).
- **License:** **VERIFY.** **Verdict: Adapt (idea-level).**

#### D4–D5. chatgpt-cover-letter-generator · cover-letter-llm — **Ignore for code** (Rico has this flow).

#### D6. olyaiy/resume-lm
- **URL:** https://github.com/olyaiy/resume-lm · ~300 ⭐.
- **Core:** Next.js AI resume builder; ATS scoring; multi-provider (OpenAI/Claude/Gemini/DeepSeek).
- **License:** **AGPL-3.0.** **Verdict: Ignore for code** (Rico has its own provider layer).

### Tier E — Multi-agent orchestration frameworks

#### E1. crewAIInc/crewAI — ~44k ⭐, **MIT.** Role/goal/backstory crews. **Adapt (idea-level):** borrow
the Scout/Matcher/Tailor/Applier/Tracker role vocabulary; keep Rico's runtime as executor.

#### E2. langchain-ai/langgraph — **MIT.** Graph nodes/edges + durable state + **human-in-the-loop
interrupts**. **Adapt (idea-level):** model the queue as a graph with an `interrupt()` at apply.

#### E3. microsoft/autogen — ~55k ⭐, **MIT** (docs CC-BY). Group-chat critique patterns.
**Verdict: Reference** for a multi-critic tailoring loop.

### Tier F — Agent governance / safety (new, high-value)

#### F1. microsoft/agent-governance-toolkit ⭐ blueprint for Rico's policy gate
- **URL:** https://github.com/microsoft/agent-governance-toolkit
- **Stars/activity:** ~3.3k ⭐; open-sourced 2026-04-02; 17 releases by mid-2026.
- **Core:** Runtime governance for AI agents — **YAML-declarative policy**, a **`safe_tool` wrapper**
  that evaluates policy on every tool call, logs the decision, and raises `GovernanceDenied` if
  blocked; **zero-trust identity, execution sandboxing**; covers **OWASP Agentic Top 10 (10/10)**;
  sub-ms policy latency; framework adapters (LangChain, CrewAI, AutoGen, OpenAI Agents, ADK).
- **Ideas for Rico:** This is a **direct blueprint** for hardening Rico's safety + approval logic into
  a declarative `policy_gate`. Rico's current checks (`rico_safety`, approval guard, automation flag,
  entitlement, idempotency) are imperative and scattered across `apply_service`/`runtime`; the toolkit
  shows how to express them as **policy-as-config evaluated on every action**, with **immutable
  decision logging** — exactly what the audit trail needs.
- **Risks:** Adds a dependency/abstraction; Rico can adopt the *pattern* without the package if a
  lighter footprint is wanted.
- **License:** **MIT.** **Verdict: Adopt patterns** (optionally the package). Foundational to PR-1.

---

## 3. Competitive feature matrix

Legend: ✅ strong · 🟡 partial · ❌ absent · 🔒 intentionally gated by safety.

| Capability | Rico today | career-ops | AutoApply-AI | agent-gov-toolkit | browser-use | Skyvern | JobSpy | Resume-Matcher | CrewAI/LangGraph |
|---|---|---|---|---|---|---|---|---|---|
| Single action dispatcher + idempotency | ✅ | 🟡 | 🟡 | ❌ | ❌ | 🟡 | ❌ | ❌ | 🟡 |
| Immutable audit trail | ✅ | 🟡 | 🟡 | ✅ | ❌ | 🟡 | ❌ | ❌ | 🟡 |
| Declarative policy gate | 🟡 (imperative) | ❌ | 🟡 | ✅ | ❌ | ❌ | ❌ | ❌ | 🟡 |
| Approval / human-in-the-loop | ✅🔒 | ✅ (draft-only) | ✅ | 🟡 | ❌ | ❌ | ❌ | ❌ | ✅ |
| Subscription/entitlement gating | ✅ | ❌ | ❌ | 🟡 | ❌ | 🟡 | ❌ | ❌ | ❌ |
| Multi-tenant SaaS (JWT isolation) | ✅ | ❌ | 🟡 | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ |
| Robust browser execution | 🟡 | 🟡 | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Vision-assisted form filling | ❌ | ❌ | 🟡 | ❌ | 🟡 | ✅ | ❌ | ❌ | ❌ |
| Multi-board sourcing (UAE incl.) | 🟡 (JSearch) | 🟡 | 🟡 | ❌ | ❌ | ❌ | ✅ (Bayt/Naukri) | ❌ | ❌ |
| ATS score + keyword gaps / fit | 🟡 | ✅ (A–F) | ✅ (FAISS) | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Per-listing CV/cover tailoring | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ |
| Generate → critique loop | ❌ | 🟡 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Persistent application queue | 🟡 (designed) | 🟡 | ✅ | ❌ | ❌ | 🟡 | ❌ | ❌ | ✅ |
| Arabic/English UX | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| UAE market focus | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ |
| Commercial-safe license | ✅ | ✅ MIT | ⚠️ VERIFY | ✅ MIT | ✅ MIT | ❌ AGPL | ⚠️ VERIFY | ✅ Apache | ✅ MIT |

**Reading the matrix:** Rico's moat is the lower-left cluster (dispatch, gating, multi-tenant, locale,
UAE). Rico's gaps are declarative policy, browser robustness, ATS/fit scoring, the critique loop, and a
persistent queue — all adoptable as **ideas** from **permissive** repos (career-ops, agent-gov-toolkit,
Resume-Matcher, AutoApply-AI).

---

## 4. What Rico should copy (as ideas, not code)

1. **Declarative policy gate + immutable audit** (agent-governance-toolkit, **MIT**) — policy-as-config
   evaluated on every action; `GovernanceDenied`-style block; append-only decision log.
2. **A–F fit-by-reasoning + ATS keyword gaps** (career-ops MIT + Resume-Matcher Apache-2.0) —
   explainable, honest "why this match / how to improve before applying."
3. **Persistent human-gated queue + ATS-threshold gating** (AutoApply-AI / career-ops) —
   `MIN_ATS_SCORE`-style gate; batch evaluation; WebSocket/progress states.
4. **`observe → extract → act` + action caching** (Stagehand MIT) — deterministic, cheaper, auditable
   browser steps for the **prepare** stage.
5. **Board-agnostic `JobSource` adapter + dedup** (JobFunnel MIT / JobSpy) — multi-source incl. UAE
   boards (Bayt, Naukrigulf) layered on JSearch.
6. **Generate → critique → revise loop** (resume-tailor-agents / AutoGen) — critic pass before any
   draft reaches the user.
7. **Reusable answer library** (AIHawk idea, re-implemented) — cache of the user's *own, confirmed*
   answers to common application questions; never fabricated.
8. **Role taxonomy + HITL interrupt model** (CrewAI/LangGraph MIT) — name the agents; model the queue
   as a graph with an interrupt at apply.

## 4b. What Rico must NOT copy

1. **Any AGPL/GPL/unknown-license code** — AIHawk, GodsScion, Skyvern, firecrawl (core), resume-lm.
   Ideas only; clean-room re-implementation.
2. **Mass auto-submit without per-application review** — the core of most apply bots. (Note: the most
   popular project, career-ops, *refuses* to do this too.)
3. **Third-party credential storage / auto-login** — Rico must never store a user's LinkedIn/Indeed
   password or session.
4. **ToS-violating scraping** behind auth — keep production sourcing on licensed JSearch.
5. **Answer fabrication** — already blocked by `rico_safety.DANGEROUS_AUTOMATION_PATTERNS`.
6. **Detection-evasion / anti-bot defeat** (Skyvern's closed value) — out of scope, against ToS.

---

## 5. Rico's competitive moat (covered by no external repo)

No public project — not career-ops (50k ⭐), not AIHawk (29.6k ⭐), not any browser agent — addresses
the UAE market. This is Rico's defensible castle:

| Moat capability | Why no repo has it | Rico status |
|---|---|---|
| **Arabic ⇄ English CV tailoring** | All repos are English-only | ✅ live (cover-letter slot extraction #615) |
| **UAE job boards** (Bayt, Naukrigulf, GulfTalent, Dubizzle) | Global repos target LinkedIn/Indeed/US ATS | 🟡 JSearch; expand via `JobSource` adapters |
| **Emiratisation-aware matching** | UAE-specific labor policy | ❌ — net-new, high differentiation |
| **Visa-status filtering** (residency/sponsorship) | UAE-specific | 🟡 partial via filters; formalize |
| **MOHRE compliance guidance** | UAE Ministry of Human Resources rules | ❌ — net-new, advisory-only (no legal claims) |

**Strategic implication:** Rico should spend external-idea budget on the *generic* gaps (policy,
queue, scoring, browser-assist) and spend *original* product investment on the moat. Do not dilute the
moat by chasing the spam-apply features the AGPL bots are known for.

---

## 6. Rico Agentic Vision v1

### 6.1 Agent roles (logical; executed by existing `agent_runtime`, not new daemons)

| Role | Responsibility | Backed by today | Impact |
|---|---|---|---|
| **Scout** | Find + dedup jobs across sources (JSearch + future UAE boards) | `jobs` router, `rico_repo_adapter` | low |
| **Matcher** | A–F fit + match% + keyword gaps + "why" | `rico_match_explainer`, learning_repo | low |
| **Tailor** | Draft CV tweaks + cover letter; run critic pass | `rico_chat_api`, `messaging_tools.draft_message` | low/med |
| **Preparer** | Assemble a complete, reviewable application package (no submit) | new prepare service (future) | medium |
| **Applier** | Submit **only** after explicit approval | `apply_service.apply_to_job(approved=True)` | high 🔒 |
| **Tracker** | Lifecycle, reminders, follow-ups | `user_job_context_repo`, reminders (#355) | low |

All roles dispatch through `agent_runtime.handle_action()`. No role bypasses idempotency, audit, or the
approval gate.

### 6.2 User flow

```text
Discover → Match (A–F + ATS gaps) → Review → Tailor (+critic) → Prepare → APPROVE (human) → Apply → Track → Follow-up
                                                                              ▲
                                                          mandatory human-in-the-loop interrupt
```

### 6.3 Approval flow (maps to existing code)

```text
User asks to apply
  → agent_runtime.handle_action(action="apply", ...)
  → apply_service.apply_to_job(approved=False) → status="approval_required"
  → runtime attaches permission_request (build_apply_permission_dict)
  → UI renders PermissionPromptCard (agentic-ui-action-layer Phase 4)
  → user approves → /actions/execute (user_id from JWT) sets pre_approved=True + HMAC approval token
  → handle_action injects {"_approved": True}
  → apply_to_job(approved=True) → engine OR manual_required
  → immutable audit event recorded
```

### 6.4 Policy gate (declarative; order of enforcement)

Today these are imperative checks scattered across `apply_service`/`runtime`. The vision expresses them
as policy-as-config (agent-governance-toolkit pattern), evaluated on every action:

1. **Safety** (`rico_safety`) — fabrication, privacy, harassment, discrimination, unapproved high-impact.
2. **Approval** (`RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true`) — no submit without valid approval token.
3. **Global automation flag** (`RICO_ENABLE_AUTO_APPLY`) — off ⇒ `manual_required` for everyone.
4. **Subscription entitlement** (`application_automation_enabled`) — premium gate, 402 otherwise.
5. **Idempotency** (MD5 `user_id:action:job_key`) — no double-apply.
6. **ATS threshold** (optional, user-set `MIN_ATS_SCORE`) — don't queue weak applies.
7. **Engine allow-list** — only known, ToS-compatible engines.

### 6.5 Audit trail

Every action already writes `audit_repo.log_action(...)`. The vision adds **append-only, immutable
queue-state transitions** (queued → approved → submitted/failed) and **policy decisions** (allowed/
denied + rule) as audit events — the agent-governance-toolkit logging model. A small
`agent_audit_events` table makes audit tamper-evident and replayable.

### 6.6 Browser automation boundary

```text
ALLOWED (premium, approved, per-application):     FORBIDDEN (always):
  - Open the official apply URL                     - Auto-submit without per-application approval
  - Pre-fill from the user's confirmed profile      - Logging into third-party accounts w/ stored creds
  - Surface remaining/unknown questions             - Defeating CAPTCHAs / anti-bot
  - Stop at the final submit button, request OK     - ToS-violating scraping behind auth
                                                     - Fabricating answers to any field
```

Implementation: a future hardened browser-assist re-uses Stagehand's `observe/extract/act` + action
cache, routes through `apply_service` so approval/entitlement remain the only path to submit; existing
`_is_browser_unavailable` → `manual_required` fallback stays.

### 6.7 Failure handling

| Failure | Behavior |
|---|---|
| Browser unavailable | `manual_required` + apply URL (implemented) |
| Engine error | user-safe message; raw logged server-side only (implemented) |
| LLM provider down | fallback chain (DeepSeek → HF → keyword); never block the user |
| Low extraction confidence | surface confidence + ask user to confirm |
| Duplicate action | idempotency returns `ok=True` "already executed" (implemented) |
| Approval/token expiry (TTL) | item stays queued; nothing submitted; user re-approves |

### 6.8 Subscription gating

- Sourcing/matching/tailoring/preparing: per existing tiers (low/medium impact).
- **Application automation (Applier):** premium-only via `entitlements.application_automation_enabled`;
  Free/Pro get a clear upgrade prompt (implemented). Queue visible to all; **submit** is the gated action.

### 6.9 Observability

- Audit log as system-of-record; existing structured keys (`runtime_execute`, `runtime_apply_gated`,
  `browser_unavailable`, `engine_not_active`) plus new policy-decision keys.
- Future read endpoint: queue depth, approval latency, submit success rate, per-source match yield,
  policy-deny counts. No new external vendor for v1.

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
                          ┌──────────────┴──────────────┐
                          │   policy_gate (declarative)  │ ← NEW, agent-gov-toolkit pattern
                          └──────────────┬──────────────┘
   ┌──────────┬───────────┬─────────────┼─────────────┬───────────────┬───────────────┐
   ▼          ▼           ▼             ▼             ▼               ▼               ▼
 Scout     Matcher      Tailor      Preparer       Applier 🔒       Tracker        Safety
(JobSource (A–F + ATS   (gen→critic  (assemble     (apply_service   (lifecycle +    (rico_safety,
 adapters) keyword gap)  loop)        package)      approved=True)   reminders)      unchanged)
   └──────────┴───────────┴─────────────┴─────────────┴───────────────┘
                                         │
              audit_writer → agent_audit_events (immutable)  +  application_queue (new tables)
```

**Additive only** (no rewrites): `policy_gate` (formalizes existing checks), `agent_audit_events` +
`audit_writer`, `application_queue`, optional `JobSource` adapters, match-scoring module, critic pass,
optional premium prepare engine.

---

## 8. Safety and compliance policy (binding)

1. **License firewall.** No AGPL/GPL/unknown code in the repo. Permissive (MIT/Apache/BSD) may be
   referenced; prefer clean re-implementation. Record license provenance in PR descriptions.
2. **Approval non-negotiable.** `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` stays default; submit
   only via the `pre_approved` path with a traceable, **TTL-bounded HMAC approval token**.
3. **No credential custody.** Never store third-party site passwords/sessions.
4. **No fabrication.** Tailoring uses only user-confirmed facts; critic pass flags unsupported claims.
5. **ToS-respecting sourcing.** Production sourcing on licensed JSearch; scrapers optional + reviewed.
6. **Privacy.** PII redaction before logs/model calls; minimal retention; no PII to third-party APIs.
7. **Locale parity.** Every new user-facing action ships Arabic + English.
8. **Auditability.** Every policy decision + queue transition logged immutably.
9. **Subscription honesty.** Gated features show a clear upgrade path, never silent failure.

---

## 9. Implementation roadmap (priority-ranked feature gap map)

| # | Current Rico capability | Best external pattern | Recommended Rico implementation | Priority |
|---|---|---|---|---|
| 1 | Imperative safety/approval + `audit_repo` | **agent-governance-toolkit (MIT)** | Declarative `policy_gate` + immutable `agent_audit_events` + HMAC approval tokens | **P0** |
| 2 | Approval contract exists; no persistent queue | AutoApply-AI / career-ops / LangGraph HITL | Persist Tailored Application Queue (`application_queue` + API + UI) on the approval contract | **P0** |
| 3 | Match "why" via `rico_match_explainer` | career-ops A–F + Resume-Matcher (Apache) | Explainable match% + keyword-gap list + optional `MIN_ATS_SCORE` gate | **P0** |
| 4 | Cover-letter flow, no critic | resume-tailor-agents / AutoGen | Critic pass before drafts surface; flag unsupported claims | **P1** |
| 5 | JSearch-only sourcing | JobFunnel `JobSource` ABC / JobSpy (Bayt/Naukri) | `JobSource` interface + dedup; UAE board adapters (license + ToS reviewed) | **P1** |
| 6 | 2 thin Playwright engines | Stagehand observe/extract/act; browser-use (MIT) | Hardened **prepare-only** browser-assist behind `apply_service`, premium-gated, stop-at-submit | **P2** |
| 7 | Single canonical profile | AIHawk answer-library idea | User-confirmed reusable answer library | **P2** |
| 8 | Resume artifacts in chat | reactive-resume JSON→PDF (MIT) | Optional tailored-CV PDF attached to queue items | **P2** |
| 9 | English-first job data | (no repo) — Rico moat | UAE boards + Emiratisation/visa/MOHRE-aware matching | **P1 (moat)** |

---

## 10. PR breakdown (small, safe, sequenced)

> All PRs follow `AI_WORKSPACE/OPERATING_RULES.md` and `PR_CHECKLIST.md`: one scope per branch, tests,
> no secrets, no unrelated files, rollback plan. **None are implemented by this document** (design-only).

**PR-0 (this document).** Consolidated GitHub intelligence + Agentic Vision. No runtime change.

**PR-1 — Agent audit + declarative policy gate (P0, foundational).**
- Add: migration `0NN_agent_audit_events.sql` (append-only); `src/agent/policy_gate.py` (declarative
  evaluation of the 7 rules in §6.4); `src/agent/audit_writer.py` (immutable events);
  `src/agent/approval_token.py` (**HMAC-SHA256, TTL 5 min**).
- Change: `agent/runtime.py` + `api/routers/actions.py` route through `policy_gate` + `audit_writer`;
  `/actions/execute` validates the approval token. (Formalizes existing `rico_safety` + approval guard
  + `audit_repo` — does not weaken any current gate.)
- Tests: `tests/test_policy_gate.py` (each rule allow/deny), `tests/test_approval_token.py` (HMAC,
  TTL expiry, tamper), `tests/test_audit_writer.py` (append-only, no mutation), JWT-isolation.
- Rationale: without this layer the agentic `/ask` UI is a façade — actions need enforceable,
  auditable policy. Pattern from agent-governance-toolkit (MIT).

**PR-2 — Application Queue persistence (P0).**
- Add: migration `0NN_application_queue.sql` (status: queued/approved/submitted/failed/cancelled),
  `application_queue_repo.py`, queue endpoints (read/approve/cancel), `ApprovalQueueDrawer.tsx`.
- Change: queue transitions emit `agent_audit_events`.
- Tests: repo CRUD + idempotency; router + JWT isolation; no live DB.

**PR-3 — Explainable match score + keyword gaps + ATS threshold (P0).**
- Add: `src/services/match_scoring.py` (A–F fit + keyword coverage delta, Arabic/English aware);
  optional user `MIN_ATS_SCORE`.
- Change: job detail + queue payload include `match_score` + `fit_grade` + `keyword_gaps` (additive).
- Tests: deterministic scoring, locale, threshold gating, no fabrication.

**PR-4 — Tailoring critic pass (P1).** Critic step flags unsupported claims before display; tests for
fabrication catch + provider fallback.

**PR-5 — `JobSource` adapter + dedup (P1).** `src/sources/base.py` ABC + JSearch adapter + dedup; UAE
board adapters are later, license/ToS-gated PRs. No live network in unit tests.

**PR-6 — UAE moat: Emiratisation/visa-aware matching (P1).** Additive matching signals + advisory-only
MOHRE guidance (no legal claims); Arabic/English. Tests for filter correctness + disclaimer presence.

**PR-7 — Prepare-only browser-assist (P2, premium).** observe/extract/act engine via `apply_service`;
cannot submit without `approved=True`; entitlement enforced; browser-unavailable → `manual_required`.

**PR-8 — Answer library + tailored-CV PDF (P2).** User-confirmed answers (never fabricated);
resume-JSON → PDF artifact on queue items.

---

## 11. Test plan (cross-cutting)

- **Policy/safety regression:** every new action passes through `policy_gate`; submit impossible
  without a valid HMAC approval token / `approved=True`.
- **Idempotency:** queue + apply idempotent on MD5 `user_id:action:job_key`.
- **JWT isolation:** queue + audit reads derive identity from JWT, never request body.
- **Entitlement:** automation features 402 for non-premium when `RICO_ENABLE_AUTO_APPLY=true`.
- **Audit immutability:** `agent_audit_events` append-only; updates/deletes rejected.
- **Locale:** Arabic + English labels for every new user-facing action.
- **No live externals in unit tests:** mock JSearch, OpenAI/DeepSeek/HF, Telegram, Playwright.
- **Frontend:** `npm run build` in `apps/web`; mobile-viewport smoke for queue/approval UI.
- **Determinism for audit:** prepare/browser steps cache resolved actions so replays are auditable.

---

## 12. License compatibility appendix

| Repo | License | Import into Rico? | Use as idea? |
|---|---|---|---|
| santifer/career-ops | **MIT** | ✅ (idea/clean-room) | ✅ |
| microsoft/agent-governance-toolkit | **MIT** | ✅ (pattern or package) | ✅ |
| browser-use | MIT | ✅ (dependency, gated) | ✅ |
| Stagehand | MIT | ✅ (dependency) | ✅ |
| JobFunnel | MIT | ✅ (idea/clean-room) | ✅ |
| Resume-Matcher | Apache-2.0 | ✅ (with attribution) | ✅ |
| reactive-resume | MIT | ✅ (idea) | ✅ |
| CrewAI / LangGraph / AutoGen | MIT (docs CC-BY) | ✅ (optional dep) | ✅ |
| Rayyan9477/AutoApply-AI | **not stated → VERIFY** | ⚠️ only after confirming | ✅ |
| JobSpy / python-jobspy | **VERIFY** | ⚠️ only after confirming | ✅ |
| Liam-Frost/AutoApply · resume-tailor-agents | VERIFY | ⚠️ idea only | ✅ |
| EasyApplyJobsBot (forks) | VERIFY/MIT | ❌ | 🟡 |
| **Skyvern** | **AGPL-3.0** | ❌ | ✅ (clean-room) |
| **AIHawk** (+forks) | **AGPL-3.0** (archived) | ❌ | 🟡 (one idea) |
| **GodsScion/Auto_job_applier_linkedIn** | **GPL/AGPL-3.0** | ❌ | ❌ |
| **firecrawl** (core) | **AGPL-3.0** | ❌ (hosted API only, later) | ✅ |
| **resume-lm** | **AGPL-3.0** | ❌ | 🟡 |

**Rule of thumb:** MIT/Apache/BSD → may depend on or reference. AGPL/GPL/unknown → **idea only**,
clean-room re-implementation, license verified before any dependency is added.

---

## Sources

- [santifer/career-ops](https://github.com/santifer/career-ops)
- [microsoft/agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit)
- [Rayyan9477/AutoApply-AI](https://github.com/Rayyan9477/AutoApply-AI-Agentic-Browser-Automation-for-Job-Search)
- [Liam-Frost/AutoApply](https://github.com/Liam-Frost/AutoApply)
- [feder-cr/Jobs_Applier_AI_Agent_AIHawk](https://github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk)
- [GodsScion/Auto_job_applier_linkedIn](https://github.com/GodsScion/Auto_job_applier_linkedIn)
- [browser-use/browser-use](https://github.com/browser-use/browser-use)
- [Skyvern-AI/skyvern](https://github.com/Skyvern-AI/skyvern)
- [browserbase/stagehand](https://github.com/browserbase/stagehand)
- [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)
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
- [olyaiy/resume-lm](https://github.com/olyaiy/resume-lm)
- [crewAIInc/crewAI](https://github.com/crewaiinc/crewai)
- [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)
- [microsoft/autogen](https://github.com/microsoft/autogen)
</content>
