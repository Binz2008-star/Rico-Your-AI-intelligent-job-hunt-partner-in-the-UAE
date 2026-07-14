# ADR-001 — Rico Career Memory Engine

- Status: **PROPOSED** (owner approval required before any implementation)
- Date: 2026-07-14
- Program: Rico Intelligence Phase 1 — Epic 1 (see `AI_WORKSPACE/RICO_INTELLIGENCE_PHASE1.md`)
- Deciders: Owner (Roben) — this ADR is the decision artifact; no code ships from it

## Context — what exists today (audited from the codebase)

Rico already remembers things, but in **six disconnected places**, each with its
own shape, lifetime, and identity key:

| Store | What it holds | Weakness |
| --- | --- | --- |
| `src/services/career_memory.py` | action events (applied/blocked/disliked companies) as JSON entries inside agent **settings** | memory piggybacks on a settings blob; no schema, no provenance, unbounded growth |
| `src/rico_memory.py` (`RicoMemoryStore`) | file-based profile/chat/signals/memories with token-similarity recall | effectively inert in postgres mode (the #741 class of bug); not durable on Render |
| `user_job_context` (migrations 018–022) | operational memory: matches found, interactions, lifecycle status, recently-discussed | job-scoped only; no reasons, no goals, no commitments |
| `rico_chat_history` | raw conversation transcripts | verbatim only — nothing is ever concluded from it |
| `rico_profiles` + CV artifacts (037/038) | identity: roles, years, extracted CV facts | static snapshot; no history of *change* |
| `uploaded_document_context` (032) | last uploaded document transcript, 180-min window | single-slot, short-lived |

Consequences visible in the product: Rico cannot answer "why did I reject that
job?", "what changed since yesterday?", or "what did you promise to follow up?"
— each feature re-derives context from whichever fragment it happens to know
about. Every Epic in Rico Intelligence Phase 1 (Application Intelligence, Daily
Executive Brief, Autonomous Career Agent) needs the same missing substrate.

Binding constraints inherited from the workspace: Neon Postgres is the single
source of truth (DEC-20260707-001); identity keys on the account email
(#982 invariant); user isolation via JWT; the Product Generalization Rule (no
per-account logic); the safety layer (no autonomous high-impact action without
approval); the honesty contract (Done / Suggested / Needs-your-ok / Sample —
Rico never claims knowledge it doesn't have); cost rules (summarization must
work on the cheap-provider chain and degrade to keyword fallback).

## Decision

Build **one Career Memory Engine** as the substrate for all intelligence
features: an **append-only episodic event log** plus a **curated fact layer**,
fed by a single writer, read through feature-shaped views, summarized on a
schedule, and governed by an explicit trust hierarchy. Existing stores become
**sources** that feed it (then get deprecated one by one) — not parallel
memories.

### 1. What is "memory" in Rico?

Durable, user-scoped, provenance-tagged knowledge that outlives the session and
is queryable by every feature through one API. Anything Rico "knows" must be
reconstructible from memory; anything not in memory, Rico must not claim to
know (honesty contract). Memory is **not** the chat transcript, the model
context window, or per-feature caches — those are inputs and projections.

### 2. Memory types

| Type | Examples | Mutability |
| --- | --- | --- |
| **Identity & Goals** (who you are, what you want) | target roles, salary floor, visa/notice status, strengths, weaknesses, stated goals | current-value with full change history ("what changed since yesterday" = history diff) |
| **Episodes** (what happened) | searched, viewed, applied, rejected, interview, offer, CV uploaded, message exchanged | append-only, immutable |
| **Decisions & Reasons** (what you refused and why) | "rejected Deloitte role — commute", "won't apply below AED X" | append-only; reasons are first-class, captured at decision time in the user's own words |
| **Learnings / Insights** (what Rico concluded) | "6% response rate on Operations roles", "PMP gap recurs in rejections" | derived + versioned + **recomputable from episodes**; never authoritative over them |
| **Commitments** (what Rico promised) | "follow up on Emirates NBD application Thursday" | open → done/cancelled lifecycle; the Daily Brief and the Autonomous Agent read these |
| **Working context** (last week / since yesterday) | recency-window projections over episodes + facts history | not stored — always computed |

### 3. Lifecycle

```
capture → normalize → store → summarize → retrieve → decay → forget
```

- **Capture**: only through the single writer (`MemoryWriter`), called from the
  existing action paths — `agent_runtime.handle_action()` (already has
  idempotency + audit), chat handlers, webhooks, pipeline runs. No router ever
  writes memory directly.
- **Normalize**: every record gets `{user_id (email-keyed), type, version,
  occurred_at, source, confidence, payload}`. `source` ∈ user_stated /
  verified_event / cv_extracted / inferred.
- **Store**: episodes append-only; facts upsert-with-history (old value moves
  to a history row, never overwritten in place).
- **Summarize**: rolling summaries per period (weekly conversation digest) and
  per entity (one summary per application thread). Summaries are themselves
  memory records of type `insight`, marked derived.
- **Retrieve**: feature-shaped read views (see §5) with token budgets — a
  context pack, not a table dump.
- **Decay**: retention tiers — raw chat older than N days survives only as its
  digest; episodes never decay (they are small and structured).
- **Forget**: user-initiated deletion is a hard delete of the user's memory
  rows (same isolation guarantees as the rest of the account data), plus
  recompute of any derived insight that referenced them.

### 4. What is summarized vs. kept whole?

**Kept verbatim, forever** (small, structured, load-bearing):
identity facts + their history; decisions **with reasons**; commitments;
application/episode records; billing events; explicit user confirmations
(safety-relevant). Document artifacts stay in the existing hash-aware My Files
store — memory references them, never copies them.

**Summarized** (bulky, low per-token value):
chat transcripts beyond the recency window (weekly digests); raw search result
sets (keep counts + top exemplars + the user's reactions); provider payloads.

Rule of thumb: *anything Rico might have to justify to the user is kept whole;
anything Rico only needs the gist of is summarized — and the raw source is
kept until its digest is confirmed written.*

### 5. How every feature uses it

One read API (`MemoryReader`) with named views — features never query tables:

- **Chat context builder**: `context_pack(user_id, budget)` → identity facts +
  open commitments + recent episodes + relevant insights, token-budgeted
  (replaces today's ad-hoc `_build_openai_context` inputs).
- **Application Intelligence (Epic 2)**: `application_history(user_id)` →
  episodes + decisions + insights per application; the "18 Operations
  applications, 6% response, PMP gap" analysis is a derived insight computed
  over this view.
- **Daily Executive Brief (Epic 3)**: `since(user_id, last_brief_at)` →
  facts-history diff + new episodes + commitments due + new insights. The brief
  is a projection of memory, not a separate pipeline.
- **Autonomous Career Agent (Epic 4)**: subscribes to episode writes and
  commitment due-dates; every proactive action it proposes cites the memory
  records that justify it (and still passes the safety approval gate).

### 6. Avoiding contradictions

- **Trust hierarchy** (highest wins): explicit user statement → verified event
  → CV-extracted → inferred. A lower tier can never overwrite a higher tier.
- Same-tier conflict on a fact → newest wins, old value preserved in history.
- **Cross-tier conflict → Rico asks** ("Your CV says 8 years, you said 10 —
  which should I keep?") — a Needs-your-ok turn, consistent with the existing
  agentic honesty contract. Silent guessing is prohibited.
- Insights never overwrite facts or episodes; a wrong insight is fixed by
  recomputation, not by editing memory.
- One identity key: the account email (verbatim, the #982 invariant). Public
  `public:web-*` sessions never merge into account memory implicitly.

### 7. Evolving without breaking

- **Envelope versioning**: every record is `{type, version, payload jsonb}` —
  new fields are additive inside payload; readers ignore unknown fields.
- **Additive-only migrations**, continuing the existing numbered scheme
  (042+); no destructive rename — deprecate, backfill, then drop in a later
  approved migration.
- **Views isolate storage**: features depend on `MemoryReader` view names, so
  storage can be reshaped behind them.
- **Derived layer is disposable**: insights/summaries can always be recomputed
  from episodes — schema mistakes in the derived layer are cheap.
- Legacy stores are **migrated as sources** (career_memory JSON entries →
  episodes; user_job_context stays and is wrapped by a view first, migrated
  later) — never deleted before their reader is repointed and verified.

## Consequences

- Positive: every Epic 2–4 feature reads/writes one substrate; "why", "what
  changed", and "what did you promise" become answerable; honesty contract
  becomes enforceable (memory = the only thing Rico may claim).
- Negative / cost: two new tables + a writer/reader service to maintain;
  summarization jobs add scheduled load (mitigated: cheap-provider chain +
  keyword fallback, per cost rules); migration of six legacy stores is a
  multi-PR effort.
- Risks: double-write drift during migration (mitigation: legacy stores become
  read-through sources first, single writer from day one); token-budget
  regressions in chat context (mitigation: context-pack size tests).

## Implementation phases (each = one small PR, after ADR approval)

1. **M1** — schema: `career_memory_events` (append-only envelope) +
   `career_memory_facts` (+history) migrations; `MemoryWriter` wired into
   `agent_runtime.handle_action()` only; shadow writes, zero readers.
2. **M2** — decisions & reasons capture in chat (reject/accept flows ask one
   short reason question, per the one-focused-question UX rule) + commitments.
3. **M3** — `MemoryReader` views + chat `context_pack` swap (behind a flag).
4. **M4** — summarization jobs (weekly digest, per-application summary).
5. **M5** — legacy source migration: `career_memory.py` JSON → episodes;
   retire `RicoMemoryStore` file paths.
6. **M6** — conflict-resolution UX (cross-tier ask flow) + forget/delete path.

Nothing in M1–M6 starts until the owner marks this ADR **ACCEPTED**.
