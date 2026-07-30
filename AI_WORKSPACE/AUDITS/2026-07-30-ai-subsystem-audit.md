# AI Subsystem Audit — 2026-07-30

Read-only audit of the Rico AI subsystem, covering the phases that follow
Phase 1 (`#1464`) in the **AI Response Reliability & Performance** epic.

**Nothing in this document is authorization to implement.** Each finding names
the smallest safe PR that would close it; each PR needs its own explicit
approval, its own branch, and its own governance check.

## Document contract

- **Why it exists:** one evidence-backed map of what is actually wrong in the AI
  subsystem, so phase order is chosen from defects rather than intuition.
- **Evidence class:** static code reading plus locally executed probes against
  `main` @ `ccde2c4`. **No production read, no live provider call, no Neon
  access.** Where a number is measured, the measurement is stated; where a cost
  is inferred, it is labelled inferred.
- **Source of truth:** `PROJECT_STATUS.md` + live `main` outrank this file.
- **Supersedes:** nothing. Additive.

## Verified state at audit time

| Item | Value |
|---|---|
| `main` | `ccde2c483c76b782214f3bb117c4c07310121c4d` |
| Phase 1 PR | `#1464` Draft, head `de29b67`, CI green, 0 regressions |
| Competing PR | `#1462` Draft, same objective, same base — **must be closed after the gap-port** |
| Backend suite on `main` | 25 failed / 9624 passed (pre-existing, DB-dependent + 2 duplicate task IDs) |

---

## F-1 — The grounding contract does not survive the provider cascade

**Severity: HIGH. Production impact: the Phase 1 fix silently does not apply on the HuggingFace leg.**

`RICO_AI_PROVIDER=deepseek` in production, and the documented chain is
`DeepSeek → HuggingFace → keyword fallback`. When DeepSeek fails, `respond()`
calls `_call_hf_free` (`src/rico_openai_agent.py:303`), which builds its **own**
three-line system prompt (`:319-323`, the literal at `:320`) and never calls `get_rico_system_prompt()`.

None of these reach the model on the HF leg:
- safety rule 9 (identity integrity)
- safety rule 10 (the `_untrusted` class rule — added in Phase 1)
- the evidence contract (verified fact / market context / missing evidence)
- the `uploaded_documents` / `content_available` semantics

Meanwhile `_skip` (`:332-333`) excludes `uploaded_documents` but **not**
`career_context` and **not** `verified_cv_evidence` — so the filename still
reaches the model, now with *no rule at all* telling it the field is untrusted.
The exact production defect is reproducible on this leg after Phase 1 merges.

- **Smallest safe PR:** make `_call_hf_free` compose its system prompt from
  `get_rico_system_prompt()` (+ the HF-specific brevity instruction), and add
  `career_context`/`verified_cv_evidence` handling consistent with the primary
  leg. No routing change, no cascade change.
- **Dependencies:** Phase 1 merged (rules must exist to be shared).
- **Tests:** assert the HF system prompt contains rules 9/10 and the evidence
  contract; assert no unguarded filename reaches the HF prompt builder.
- **Rollback:** revert; HF returns to its current prompt.
- **Docs:** `CLAUDE.md` → AI Provider Routing (prompt parity is a cascade
  invariant, not a per-provider detail).

## F-2 — Raw filenames still interpolated into `prompt_override` prose

**Severity: MEDIUM-HIGH. Production impact: the same inference channel, on a different path.**

Two builders put a bare filename into the **user message** the model reads:

- `src/rico_chat_api.py:14953` (at `de29b67`) — `f"[Transcribed text of the {label} the user just uploaded — file '{doc.get('filename')}']"`
- `src/rico_chat_api.py:15434` (at `de29b67`) — `f"[Job description — '{filename}']"`

Both flow through `prompt_override` → `_answer_with_ai_fallback`. Phase 1's rule
10 governs *context fields* whose name ends `_untrusted`; a filename embedded in
the user message is outside it.

- **Smallest safe PR:** drop the filename from both strings (use the document
  *type* label, which is what the model actually needs to disambiguate), or pass
  it as a labelled untrusted line.
- **Dependencies:** none.
- **Tests:** extend the Phase 1 value-side guard to cover both builders.
- **Rollback:** revert. **Docs:** none beyond the task ledger.

## F-3 — A 25-second HuggingFace classifier sits on the pre-stream critical path

**Severity: HIGH. Production impact: the reported ~25s response time.**

`should_stream_ai` → `IntentRouter.route` (`src/rico_intent_router.py:480`).
`_keyword_classify` returns `(None, 0.0)` for any message that is not a job
*action* command — which is exactly the open-ended/advice class. `route()` then
requires confidence ≥ 0.80, so it falls through to `_hf_classify` (`:363`), a
**synchronous** `requests.post` to `facebook/bart-large-mnli` with:

```
_REQUEST_TIMEOUT = 25    # src/rico_hf_client.py:28
```

On a cold or unresponsive serverless model the request burns the full 25s, is
swallowed by `except Exception`, and returns `"unknown"` — a discarded value,
paid for before a single token can stream. The constant matches the reported
latency exactly. The same call is on the buffered `/chat` path
(`chat_service.py:253`).

- **Smallest safe PR (two independent slices, in order):**
  1. Reduce `_REQUEST_TIMEOUT` to ~3s via validated config. Pure config, instantly revertable.
  2. Skip `_hf_classify` when the gates already prove the request is AI-bound, so
     routing OUTCOMES are unchanged and only the transport decision short-circuits.
- **Dependencies:** none. Slice 1 is independently shippable.
- **Tests:** assert no HTTP call for an open-ended question; assert routing
  outcomes are byte-identical across a corpus of messages before/after.
- **Rollback:** revert; env var restores the old timeout without a deploy.
- **Docs:** `CLAUDE.md` → required env vars (new timeout knob).

## F-4 — No `temperature` on any provider call site

**Severity: MEDIUM. Production impact: non-deterministic analytical answers.**

Neither `_call_deepseek_chat` (`rico_openai_runtime.py:946`),
`_call_openai_responses` (`:923`), nor either streaming branch (`:1187`, `:1200`)
passes `temperature`. DeepSeek's API default is ~1.0. For an extractive task
grounded in `verified_cv_evidence`, that is the wrong default.

- **Smallest safe PR:** measured baseline first, then `temperature=0.2` with a
  bounded, validated env override, applied consistently to all four sites.
- **Dependencies:** Phase 1 (grounding must exist before tuning determinism on it).
- **Tests:** assert the effective parameter reaching every supported call path.
- **Rollback:** env override to the previous value; revert the default.
- **Docs:** `CLAUDE.md` → AI Provider Routing.

## F-5 — Connection pooling disabled: every read is a fresh Neon connection

**Severity: HIGH (latency), but BLOCKED. Production impact: ~10-12 handshakes per chat turn.**

`src/rico_db.py:318` documents pooling as deliberately disabled after an
`AttributeError` outage, and states the safe fix requires routing **all**
consumers through one acquire/release path. A chat turn currently performs
roughly 10-12 sequential reads, each opening a new TCP+TLS connection.

**Do not attempt before:** full DB-consumer audit · pooling-disable incident
review · Neon connection-limit review · acquire/release path analysis · load
tests · canary plan · rollback proof. This stays blocked.

## F-6 — Duplicate per-turn reads

**Severity: MEDIUM. Production impact: avoidable latency, amplified by F-5.**

- `list_user_documents` is read twice per turn: once via
  `resolve_career_context` → `get_cv_candidates_strict`, once via
  `_collect_uploaded_documents`.
- Phase 1 adds a `get_user_bundle` round-trip through `_cv_context`; net-zero on
  the buffered path (`_get_blocked_questions` would fill the memo anyway) but
  **+1 synchronous read per streamed turn**. Declared debt in `TASK-20260730-001`.

- **Smallest safe PR:** pass the already-resolved document list from
  `resolve_career_context` into `_collect_uploaded_documents`; share one
  bundle read per turn. Behaviour-preserving.
- **Tests:** assert exactly one `list_user_documents` and one `get_user_bundle`
  per `_build_openai_context` (the Phase 1 resolver-call test is the pattern).
- **Rollback:** revert. **Docs:** task ledger only.

## F-7 — No request-scoped tracing

**Severity: MEDIUM. Production impact: every latency question needs a code read.**

There is no `operation_id` threaded through request → routing → context build →
provider → persistence → stream. Per-attempt provider telemetry exists
(`_record_reasoning_outcome`, `stream_frames`, `first_frame_ms`) but is not
correlated with a request, so "why was this turn slow" cannot be answered from
logs. This audit had to be produced by reading code and running probes — that is
the cost being paid repeatedly.

- **Smallest safe PR:** thread an existing `operation_id` through and emit stage
  timings + TTFT. **No PII, no prompts, no CV content, no filenames, no tokens,
  no cookies** — `src/log_privacy.py` (`user_ref`, `safe_exc`) is the existing
  contract to follow.
- **Dependencies:** best done before F-3/F-6 so the wins are measurable.
- **Tests:** assert no PII in emitted records; assert stage coverage.
- **Rollback:** revert. **Docs:** a runbook entry.

## F-8 — Interactive job search can block a user turn for ~55s per provider

**Severity: MEDIUM-HIGH. Production impact: the disconnect/timeout class.**

`src/jsearch_client.py` retries 429/5xx three times with 1s/2s/4s backoff
(`:46-47`) at a 12s timeout (`:48`). Worst case for **one** provider is
4 × 12s + 7s ≈ **55s**; the orchestrator runs several providers. The retry
budget is not differentiated between an interactive chat turn and a batch
pipeline run — the same constants serve both.

The backoff *is* interruptible and ownership-aware (`_wait_or_cancelled`), and
the operation store already models ownership, so the machinery for a shorter
interactive budget exists.

- **Smallest safe PR:** an explicit interactive retry budget (distinct from the
  batch budget), plus partial-result delivery and a stream heartbeat.
- **Dependencies:** F-7 (tracing) to prove where the time actually goes.
- **Do NOT claim** Vercel or the browser timed out without direct evidence —
  the disconnect layer has not been established. Establish it first.
- **Tests:** assert the interactive budget is bounded; assert persisted results
  match what the user was shown.
- **Rollback:** env-tunable constants.

## F-9 — `rico_chat_api.py` is 23,802 lines and one class with 318 methods

**Severity: MEDIUM (systemic). Production impact: every AI change is high-blast-radius.**

`RicoChatAPI` (`:2236`) holds 318 methods in a single class. Every phase in this
epic touches it. This is the reason each fix needs a full-suite comparison to
prove it changed nothing else.

- **Approach (owner-mandated): no rewrite.** Characterization tests first, then
  incremental extraction of cohesive seams — the context builder and the
  evidence/document projection are the natural first seam, and Phase 1 already
  added characterization coverage for it.
- **Smallest safe PR:** extract ONE seam behind the existing method names, with
  characterization tests written *before* the move and unchanged after.
- **Dependencies:** each extraction should follow the phase that stabilises that
  seam, never precede it.
- **Rollback:** revert; the seam is behaviour-preserving by construction.

---

## Recommended order

Ordered by (production impact × evidence strength) ÷ risk, not by phase number.

| # | Finding | Why here |
|---|---|---|
| 1 | **F-1** cascade prompt parity | Phase 1 is incomplete without it — the fix has a hole on a live fallback path |
| 2 | **F-3** slice 1 (timeout) | Largest measured latency win, pure config, instantly revertable |
| 3 | **F-2** prompt_override filenames | Same defect class as Phase 1, tiny diff |
| 4 | **F-7** tracing | Makes F-3 slice 2, F-6 and F-8 measurable instead of argued |
| 5 | **F-3** slice 2 (skip classifier) | Needs F-7 to prove routing outcomes unchanged |
| 6 | **F-6** duplicate reads | Cheap, compounds with F-5 |
| 7 | **F-4** temperature policy | Needs a measured baseline, which F-7 provides |
| 8 | **F-8** interactive search budget | Needs F-7 evidence; disconnect layer unproven |
| 9 | **F-9** decomposition | Continuous, one seam at a time, after each seam stabilises |
| — | **F-5** pooling | **BLOCKED** — do not attempt until every listed gate is satisfied |

## Standing constraints

- One objective per PR. No unrelated production changes combined.
- Before each phase: verify live GitHub, current `main`, and open competing PRs.
  Phase 1 was cut without that check and duplicated `#1462`. Do not repeat it.
- No merge, deploy, migration, env, Neon, Railway, or Vercel change without
  explicit approval.
- Do not rewrite `rico_chat_api.py`.
- Every fix must be global and user-agnostic; synthetic fixtures only.
