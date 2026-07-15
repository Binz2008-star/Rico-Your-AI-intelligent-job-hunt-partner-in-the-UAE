# ADR-001 — Rico Career Memory Engine

- Status: **ACCEPTED** (owner review on PR #1024, 2026-07-14 — rev 2 satisfies
  all seven required amendments; M1 may begin under its strict scope)
- Accepted head: `ef66ebfa` (rev 2 as independently reviewed and owner-accepted on #1024)
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
source of truth (DEC-20260707-001); user isolation via JWT; the Product
Generalization Rule (no per-account logic); the safety layer (no autonomous
high-impact action without approval); the honesty contract (Done / Suggested /
Needs-your-ok / Sample — Rico never claims knowledge it doesn't have); cost
rules (summarization must work on the cheap-provider chain and degrade to
keyword fallback).

## Decision

Build **one Career Memory Engine** as the substrate for all intelligence
features: an **append-only episodic event log** plus a **curated fact layer**,
fed by a single writer, read through feature-shaped views, summarized on a
schedule, and governed by an explicit trust hierarchy. Existing stores become
**sources** that feed it (then get deprecated one by one) — not parallel
memories.

**Authority boundary (owner amendment 7).** The engine is the unified
*intelligence substrate*, not the system of record for any domain. Profile,
applications, billing, and documents remain authoritative in their existing
stores; memory holds **provenance-linked observations and projections** of
them. When memory and an authoritative domain store disagree, the domain store
wins and the memory record is corrected (with history), never the reverse.

### 1. What is "memory" in Rico?

Durable, user-scoped, provenance-tagged knowledge that outlives the session and
is queryable by every feature through one API. Anything Rico "knows" must be
reconstructible from memory; anything not in memory, Rico must not claim to
know (honesty contract). Memory is **not** the chat transcript, the model
context window, per-feature caches, or the authoritative domain records —
those are inputs, projections, and referenced sources.

### 2. Memory types

| Type | Examples | Mutability |
| --- | --- | --- |
| **Identity & Goals** (who you are, what you want) | target roles, salary floor, visa/notice status, strengths, weaknesses, stated goals | current-value with full change history ("what changed since yesterday" = history diff) |
| **Episodes** (what happened) | searched, viewed, applied, rejected, interview, offer, CV uploaded, message exchanged | append-only, immutable content; lifetime governed by retention class (§4) |
| **Decisions & Reasons** (what you refused and why) | "rejected Deloitte role — commute", "won't apply below AED X" | append-only; reasons are first-class, captured at decision time in the user's own words |
| **Learnings / Insights** (what Rico concluded) | "6% response rate on Operations roles", "PMP gap recurs in rejections" | derived + versioned + **recomputable from episodes**; never authoritative over them |
| **Commitments** (what Rico promised) | "follow up on Emirates NBD application Thursday" | open → done/cancelled lifecycle; the Daily Brief and the Autonomous Agent read these |
| **Working context** (last week / since yesterday) | recency-window projections over episodes + facts history | not stored — always computed |

### 3. Identity keying (owner amendment 1)

- The **storage key is the immutable canonical account ID** (the internal user
  ID that never changes). Email is **an attribute** — retained as verified
  identity/provenance data and as a lookup index, never as the durable primary
  key (emails are mutable).
- **Public sessions** (`public:web-*`) are keyed separately and never merge
  into account memory implicitly. Merging a public session's memory into an
  authenticated account requires an **explicit, audited merge step** after
  authentication (its own episode record: who, when, what was merged).
- Existing call sites that key on email (the #982 gating invariant and
  friends) are unaffected — they address their own domains; the memory engine
  maps email → canonical ID at the write boundary.

### 4. Lifecycle, retention, and data minimization (owner amendment 2)

```
capture → normalize → store → summarize → retrieve → retention policy → forget/export
```

- **Capture**: only through the single writer (`MemoryWriter`), called from the
  existing action paths — `agent_runtime.handle_action()` (already has
  idempotency + audit), chat handlers, webhooks, pipeline runs. No router ever
  writes memory directly.
- **Normalize**: mandatory envelope (see §6 provenance) with type, version,
  retention class, and provenance fields.
- **Store**: episodes append-only; facts upsert-with-history (old value moves
  to a history row with `effective_from`/`effective_to`, never overwritten in
  place).
- **Summarize**: rolling summaries per period (weekly conversation digest) and
  per entity (one summary per application thread). Summaries are memory
  records of type `insight`, marked derived, with derivation links (§6).
- **Retention is policy-driven per record class — nothing is "forever" by
  default**:

  | Retention class | Examples | Default policy (configurable) |
  | --- | --- | --- |
  | `core_fact` | identity facts + history, decisions+reasons, commitments | retained while the account is active; exportable; deletable on request |
  | `episode` | application/search/interaction events | long-lived but bounded (default multi-year, configurable); oldest compact into digests |
  | `bulk_text` | raw chat, provider payload excerpts | short window, then digest-only |
  | `derived` | insights, summaries | recomputable — freely expirable |
  | `referenced` | billing, security, audit, documents | **never copied into memory** — stored as references (`source_uri`/`source_record_id`) to their authoritative systems |

- **Legal hold**: a per-account hold flag suspends deletion/compaction across
  all classes until released.
- **Export**: user-initiated export produces the account's memory records
  (facts + history, episodes, decisions, commitments) in a documented format.
- **Forget**: user-initiated deletion is a hard delete of the account's memory
  rows by class or in full, followed by **recomputation of every derived
  record** that referenced the deleted sources (derivation links make the
  affected set enumerable). Deletion itself is audited (§8).

### 5. What is summarized vs. kept whole?

**Kept whole under `core_fact` retention** (small, structured, load-bearing):
identity facts + history; decisions **with reasons**; commitments; structured
episode records; explicit user confirmations (safety-relevant).

**Referenced, never copied** (owner amendment 2): billing events, security and
audit records, document artifacts (My Files' hash-aware store) — memory keeps
`source_record_id`/`source_uri` pointers into the authoritative systems.

**Summarized** (bulky, low per-token value): chat transcripts beyond the
recency window (weekly digests); raw search result sets (counts + top
exemplars + the user's reactions); provider payloads.

Rule of thumb: *anything Rico might have to justify to the user is kept whole
or referenced to its authoritative source; anything Rico only needs the gist
of is summarized — and the raw source is kept until its digest is confirmed
written.*

### 6. Provenance, confidence, and traceability (owner amendment 4)

Every record carries a **mandatory** provenance block:

- `source` ∈ user_stated / verified_event / cv_extracted / inferred
- `source_record_id` and/or `source_uri` — the exact originating record
  (chat message ID, application row, webhook event, document hash)
- `captured_at` (when memory learned it) distinct from `occurred_at` (when it
  happened)
- `actor` — who caused the write (user, Rico agent, pipeline, webhook)
- `confidence` — calibrated per source tier (user_stated = 1.0;
  verified_event = 1.0; cv_extracted = the parser's calibrated score;
  inferred = the deriving job's documented score), never a free-floating guess
- **Derivation links**: every insight/summary stores the IDs of the records it
  was derived from, so any conclusion is traceable to sources and recomputable
  when they change or are deleted.

### 7. Avoiding contradictions (owner amendment 3)

- **Trust hierarchy** (highest wins): explicit user statement → verified event
  → CV-extracted → inferred. A lower tier can never overwrite a higher tier.
- **Per-fact-class resolution policies — timestamps alone never decide**:

  | Fact class | Policy |
  | --- | --- |
  | `replaceable` (e.g. notice period) | same-tier newer value supersedes; old value archived with `effective_from`/`effective_to` |
  | `set_valued` (e.g. target roles, skills) | add/remove semantics — a new value **joins** the set; removal is explicit, never implied by a new arrival |
  | `time_bound` (e.g. availability, visa status) | valid only within its `effective_from`/`effective_to` window; overlapping windows are a material conflict |
  | `verified_only` (e.g. email-verified identity attributes) | only `verified_event`-tier writes accepted; anything else is queued as unverified |

- **Material conflicts ask the user** ("Your CV says 8 years, you said 10 —
  which should I keep?") — a Needs-your-ok turn, consistent with the existing
  agentic honesty contract. Silent guessing is prohibited.
- Insights never overwrite facts or episodes; a wrong insight is fixed by
  recomputation, not by editing memory.
- Domain stores stay authoritative (Decision §authority boundary): a memory
  observation contradicting the applications table is corrected from the
  table, with the correction recorded in history.

### 8. Privacy & security boundary (owner amendment 6)

- **Excluded from memory, always**: secrets, credentials, tokens, full
  provider payloads, payment instrument data, and sensitive personal data not
  needed for career assistance. The writer enforces an exclusion filter;
  violations are dropped and logged.
- **Access control**: memory rows are per-account (canonical ID) with the same
  JWT-derived isolation as the rest of the API; no cross-user read path
  exists in `MemoryReader` by construction.
- **Encryption**: at rest via the managed Postgres encryption (Neon), in
  transit via TLS; any future field-level encryption for especially sensitive
  fact classes is an additive envelope change.
- **Audit trail**: memory writes, deletes, merges (public→account), exports,
  and privileged reads are recorded through the existing audit-log
  infrastructure (migrations 030/031 pattern) — who, what, when.

### 9. How every feature uses it

One read API (`MemoryReader`) with named views — features never query tables:

- **Chat context builder**: `context_pack(user_id, budget)` → identity facts +
  open commitments + recent episodes + relevant insights, token-budgeted
  (replaces today's ad-hoc `_build_openai_context` inputs).
- **Application Intelligence (Epic 2)**: `application_history(user_id)` →
  episodes + decisions + insights per application; the "18 Operations
  applications, 6% response, PMP gap" analysis is a derived insight computed
  over this view.
- **Daily Executive Brief (Epic 3)**: `since(user_id, last_brief_at)` →
  facts-history diff + new episodes + commitments due + new insights. The
  brief is a projection of memory, not a separate pipeline.
- **Autonomous Career Agent (Epic 4)**: subscribes to episode writes and
  commitment due-dates; every proactive action it proposes cites the memory
  records that justify it (and still passes the safety approval gate).

### 10. Evolving without breaking

- **Envelope versioning**: every record is `{type, version, retention_class,
  provenance, payload jsonb}` — new fields are additive inside payload;
  readers ignore unknown fields.
- **Additive-only migrations**, continuing the existing numbered scheme
  (042+); no destructive rename — deprecate, backfill, then drop in a later
  approved migration.
- **Views isolate storage**: features depend on `MemoryReader` view names, so
  storage can be reshaped behind them.
- **Derived layer is disposable**: insights/summaries can always be recomputed
  from episodes via derivation links.
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
  multi-PR effort; retention/legal-hold/export machinery is real scope.
- Risks: double-write drift during migration (mitigation: legacy stores become
  read-through sources first, single writer from day one, drift metrics —
  §M1); token-budget regressions in chat context (mitigation: context-pack
  size tests).

## Implementation phases (each = one small PR, after ADR approval)

1. **M1** — schema + writer + **shadow writes only**, hardened per owner
   amendment 5: idempotency keys on every write; unique constraints enforcing
   them; per-user isolation tests; **zero reader behavior change**; feature
   flag + kill switch (`RICO_MEMORY_ENGINE_ENABLED`, default off); documented
   backfill and rollback plan; metrics for write failures and legacy↔engine
   drift. Canonical-ID keying from day one.
2. **M2** — decisions & reasons capture in chat (reject/accept flows ask one
   short reason question, per the one-focused-question UX rule) + commitments.
3. **M3** — `MemoryReader` views + chat `context_pack` swap (behind the flag).
4. **M4** — summarization jobs (weekly digest, per-application summary) +
   retention-policy enforcement job.
5. **M5** — legacy source migration: `career_memory.py` JSON → episodes;
   retire `RicoMemoryStore` file paths; public→account audited merge flow.
6. **M6** — conflict-resolution UX (cross-tier ask flow) + forget/export/legal-
   hold paths end-to-end.

Owner-accepted M1 strict scope (2026-07-14): additive schema; MemoryWriter;
shadow writes only; feature flag default OFF; no MemoryReader rollout; no
chat/context behavior change; no migration of legacy readers; no user-visible
behavior change. M1 ships as a separate Draft PR and stops before merge.
