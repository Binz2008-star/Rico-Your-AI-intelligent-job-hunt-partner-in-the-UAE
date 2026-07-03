# Trace: TC-2 chat job-search path + TC-8 interview-prep dispatch (2026-07-03)

- Method: **measure-first** — static trace of the live code path plus a runnable
  characterization harness (`tests/test_tc2_ordering_characterization.py`). No
  core hot-path code was changed. Pure-Python, no DB / provider / network calls.
- Trigger: 2026-07-03 live QA (TC-2 relevance, TC-8 interview-prep misfire).
- Rule honored: **no regex or weight tweak in a retrieval/scoring hot path
  without an end-to-end trace.** This note is that trace.

## TL;DR

- **The scorer is not the TC-2 bug**, and neither is the chat ranker. Both rank
  relevant ESG/Compliance jobs far above irrelevant ones when they are given the
  confirmed targets and a candidate set that contains relevant jobs.
- **TC-2 is upstream / post-retrieval:** the visible failure reproduces only when
  (A) the target roles used to build the query / score fit are **stale** (still
  Operations/Admin, not the confirmed ESG/Compliance), or (B) the provider
  **candidate set contains no relevant jobs** (a query-generation problem). Both
  are measured below.
- **TC-8 is a dispatch/handler problem, not classification.** The active
  `_handle_interview_prep` ignores the message entirely (no company, no role
  parse, no tracked-application lookup) and emits a static template keyed off
  `profile.target_roles[0]`. There is also a **duplicate-method shadow** bug: a
  richer handler is defined earlier and is unreachable.

---

## 1. Full trace: user message → top-5 render (chat job search)

Entry: `POST /api/v1/rico/chat/public` → `src/services/chat_service.py`
→ `src/rico_chat_api.py::RicoChatAPI`.

```
classify_intent(message)                         src/agent/intelligence/intent_classifier.py
  -> job_search_profile_match | job_search_explicit   (dispatch in rico_chat_api.py ~L8030)

# Query builder (role resolution)
profile_match:  _effective_target_roles(profile.target_roles)      rico_chat_api.py:8042
                _resolve_profile_search_role(profile, ...)         rico_chat_api.py:8069  -> _pm_role
explicit:       normalize_role(role)                               rico_chat_api.py:5215  -> normalized_role
                search_role = normalized_role or role              rico_chat_api.py:5227

# Provider fetch (candidate set)
_search_jsearch_meta(search_role, location)                        rico_chat_api.py:5074
  -> job_providers.search_jobs(role, location)                     rico_chat_api.py:5088
     (cache -> Jooble -> Adzuna -> JSearch -> degraded)
  -> fetch.items = all_matches                                     rico_chat_api.py:5247

# Filters
applied-dedup / non-national / employment-type / title+company dedup   rico_chat_api.py:5310-5367

# Profile-fit ranking  (THE chat-path ranker)
rank_by_profile_fit(all_matches, target_roles, skills, deal_breakers)   src/llm_scorer.py:296
  sets job["profile_fit_score"] (0-100); returns sorted desc            llm_scorer.py:369-371
  ^ wrapped in try/except: pass                                         rico_chat_api.py:5372-5390

# Quality re-sort  (fit is only a coarse band here)
all_matches.sort(key=_quality_key)                                 rico_chat_api.py:5445
  fit_band = max(0, 5 - profile_fit_score // 20)   # 20-pt buckets  rico_chat_api.py:5429
  + source-quality rank + company penalty + LEARNED-PREFERENCE bonus   rico_chat_api.py:5422-5443

# Render
top_matches = all_matches[:5] -> _format_match -> {"type":"job_matches"}  rico_chat_api.py:5449
```

### Wiring gap worth noting

`src/scoring.py::score_jobs_for_user` — the function the earlier characterization
validated — is wired **only** into the `/jobs` REST API
(`src/services/jobs_service.py:124-127`). It is **not** called anywhere in the
chat path. The chat path ranks with `rank_by_profile_fit`
(`src/llm_scorer.py`). So the two surfaces use two different relevance engines;
validating one says nothing about the other. Pinned by
`test_chat_ranker_is_rank_by_profile_fit_not_score_jobs_for_user`.

---

## 2. Proof: is the target role respected after confirmation?

Measured with `rank_by_profile_fit` (the real chat ranker), ESG/Compliance
profile, realistic mixed candidate set. See
`tests/test_tc2_ordering_characterization.py`.

**Correct when targets match (ranker is not the bug):**

| Job | profile_fit_score |
|---|---|
| ESG Manager | 76 |
| Compliance Officer | 40 |
| ServiceNow Developer | 0 |
| Field Service Engineer | 0 |
| HR Administrator | 0 |
| Operations Manager | 0 |

**Failure mode A — stale Operations target (reproduces TC-2):** if the profile
still carries Operations/Admin (the in-session ESG switch did not propagate), the
ranker faithfully floats the wrong jobs:

| Job | profile_fit_score |
|---|---|
| Operations Manager | 66 |
| HR Administrator | 16 |
| ESG Manager | 0 |

**Failure mode B — wrong candidate set:** if the query was built from the stale
role, the provider returns no ESG jobs at all; every candidate scores `fit=0`,
`rank_by_profile_fit` imposes no order, and the final top-5 is decided by the
downstream `_quality_key` (source quality + **learned Operations preference**),
which can resurface previously-preferred Operations/Admin roles.

**Conclusion:** target-role respect depends entirely on whether the confirmed
ESG/Compliance target reaches (a) `search_role` (the provider query) and (b) the
`profile.target_roles` passed to `rank_by_profile_fit`. The next live test must
verify **propagation/persistence** of an in-session target change into the very
next search turn — that is the open question this static trace cannot settle.

### Open item for the live/full-app environment

- Confirm whether an in-session "switch my target to ESG/Compliance" is persisted
  to the profile row that the *next* chat turn loads, or whether the turn reuses a
  stale in-memory/cached profile (overlaps TC-4). Instrument by logging
  `search_role` and the `target_roles` handed to `rank_by_profile_fit` at
  `rico_chat_api.py:5383`, then diff against the confirmed target.
- Confirm the provider candidate set actually contains ESG/Compliance postings
  for `search_role` (log `fetch.provider` + returned titles at `rico_chat_api.py:5247`).

---

## 3. Proof: Richemont interview-prep — exact tracked role or generic?

**Neither.** The active handler does a static template, not a lookup.

- `RicoChatAPI._handle_interview_prep` is **defined twice**
  (`rico_chat_api.py:14532` and `:16133`). Python keeps the **last** definition,
  so **16133 shadows 14532** — the earlier, richer handler is dead code.
- The live handler (16133) computes `target_role = profile.target_roles[0]` (or
  `current_role`) and **ignores the message text entirely** — it never parses
  "Richemont", never extracts the role from the sentence, and never looks up a
  **tracked application** for that company/role. It returns a fixed guide.
- So "prepare me for an interview for <role> at Richemont" yields a generic guide
  headed with whatever `target_roles[0]` happens to be (e.g. Operations Manager),
  regardless of the company or the tracked role.

This matches the live symptom being a **dispatch/handler** problem, not intent
classification — consistent with the note in PR #832 that TC-8 already classifies
as `interview_prep` on `main`.

### TC-8 fix shape (for a later, verified change — not done here)

1. Resolve the duplicate `_handle_interview_prep` (keep one; the richer 14532 or a
   merge of both).
2. Parse company + role from the message ("... for <role> at <company>").
3. Look up the tracked application for that company/role and tailor the prep to it
   (JD, stage, notes) before falling back to `target_roles[0]`.

---

## Evidence artifacts

- `tests/test_tc2_ordering_characterization.py` — 4 passing characterization tests
  pinning the chat ranker's current behavior + the two TC-2 failure modes + the
  score_jobs_for_user wiring pin.
- This note.

## Status

`review` — trace + characterization landed as evidence. No hot-path code changed.
Next steps (target-propagation live check; TC-8 handler consolidation) require the
full app / live-test environment and are tracked in TASK-20260703-040 and -038.
