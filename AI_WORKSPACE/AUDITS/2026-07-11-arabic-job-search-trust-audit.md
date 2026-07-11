# Trust Audit — Arabic Job Search & Job-Listing Grounding

**Date:** 2026-07-11
**Trigger:** Owner-provided live chat transcript (Arabic) where Rico (1) rejected
"عمل جديد" ("a new job") as an unknown role, (2) offered generic job cards
("مجموعة عقارية", "الراتب: غير محدد"), then could not act on the user's pick, and
(3) treated an invoice PDF as the active CV.
**Scope:** Read-only audit of the job-search trust path + confirmed, low-risk NLP
fixes only. No architectural changes.
**Branch / PR:** `claude/esg-manager-job-search-k7f8eh` / #983

---

## 1. What already exists (the trust infrastructure is present and wired)

The system already has comprehensive grounding/trust machinery. Confirmed by
reading the code:

| Concern | Where | Status |
| --- | --- | --- |
| Real jobs (JSearch), not invented | `src/jsearch_client.py`, `src/job_sources.py` | Present |
| Matches persisted for follow-ups (session + Neon, 60-min window) | `rico_chat_api._store_search_matches_context` (writes `recent_search_matches`, `upsert_matches`) | Present |
| Apply/save resolve from the *same* rendered list | `rico_chat_api._recent_search_matches`, `_save_job_by_ordinal` | Present |
| 5-gate link trust (untrusted origin, bad scheme, placeholder, fake sequential LinkedIn id, no provenance) | `src/services/job_link_trust.py` | Present |
| Real HTTP link verification | `src/services/link_verifier.py`, `rico_chat_api._verify_link_sync` | Present |
| Source-quality classification + safe link fallback (never raw errors, never invented URLs) | `src/services/source_quality.py`, `src/services/job_link.py`, `_apply_link_fallback_response` | Present |
| Anti-hallucination identity rules | `src/rico_identity.py` ("Never fabricates job postings, salaries, companies, or links") | Present |
| Public/no-profile short-circuit before AI can invent listings | `src/services/chat_service.py:157` → `_public_job_search_cta`; `src/rico/intent/gates.py` | Present |
| Invoice/non-CV blocked from CV pipeline | `src/api/routers/rico_chat.py` (#908 RC4, `_CV_PIPELINE_TYPES` gate) | Present |

**Conclusion:** the owner is correct — the trust system is already built. Most
transcript symptoms are explained by (a) a real Arabic-NLP gap that tipped the
flow into the ungrounded AI path, and (b) stale/pre-fix data, not by missing
infrastructure.

---

## 2. Confirmed code gaps found — and fixed in this PR

Both are the same class of bug: an Arabic job-search request failing intent
classification, which routes it away from the real (grounded) search path.

### 2.1 "جديد" (new) extracted as a job role — FIXED
`_extract_arabic_role` stripped the job noun (`عمل`/`وظيفة`/`شغل`) but left the
trailing adjective `جديد`/`جديدة` ("new"), which was then searched as a role →
"I do not recognize 'جديد' as a job role." Added `جديد`/`جديده`/`الجديد`/`الجديده`
to `_ARABIC_ROLE_LEAD_STOPWORDS`. "find me a new job" now routes to profile/CV
search. Real titles unaffected (`محاسب جديدة` → Accountant).

### 2.2 "بدي" / "عايز" / "عاوز" (colloquial "I want") unrecognized — FIXED
These common Levantine/Egyptian want-verbs were missing from
`_ARABIC_REQUEST_TERMS`, so "بدي شغل جديد" classified as `unknown`. An `unknown`
job request from a **profiled** user flows to the conversational-AI path (see
§3), which can fabricate listings. Added the three verbs; they only fire
alongside a job noun, so "بدي اسالك سؤال" stays non-search.

### 2.3 Clarification tone/locale — FIXED
The unknown-role fallback replied in blunt English even to Arabic users. It now
replies in the user's language and leads with what was understood.

---

## 3. Architectural gap — FIXED in Phase 2 (this PR)

**The anti-hallucination short-circuit previously only protected public/no-profile
sessions.** `chat_service.py` gated on `profile is None and not
ctx.can_persist_profile`. A **profiled/authenticated** user whose job-listing
request reached the conversational-AI path (`should_use_ai`) was **not** caught
by `_public_job_search_cta` and could receive AI-fabricated job cards. Because
those cards are never written to `recent_search_matches`, a later "apply to that
one" could not resolve — reproducing transcript symptoms #2 (offered → asks for
details again) and #3 (generic company, unverifiable link).

### Phase-2 decision (owner-approved 2026-07-11)

Extend the guard to **all** sessions:

1. `src/rico/intent/gates.py` — `is_explicit_job_listing_request` now defers to
   `classify_intent` for anything the anchored regexes miss, so colloquial
   Gulf/Egyptian phrasing ("أبغى شغل جديد", "بدي وظيفة", "دورلي على شغل") is
   recognised as a job-listing request. This keeps the predicate in lock-step
   with the real search router (no drift).
2. `src/services/chat_service.py` — for an **authenticated** user, an explicit
   job-listing request now forces the real search path
   (`_force_real_search = _explicit_job_listing and ctx.auth_type ==
   "authenticated"`) even when the open-ended-question gate chose AI. Public/
   no-profile users keep the deterministic sign-up/upload CTA.

Net effect: **no session can receive AI-fabricated job listings**. Authenticated
users get grounded JSearch results (persisted to `recent_search_matches`, so
follow-up apply/save resolves); public users get the CTA. **Response contract is
unchanged** — the legacy path emits the same `type/message/options/matches`
shape the command surface already consumes; no frontend files touched.

Tests: `tests/test_public_chat_no_profile_loop.py::TestAuthenticatedJobListingForcedToRealSearch`
asserts the three required Arabic phrasings (and an English conversational one)
route to legacy/real-search with the AI path never called, and that the response
dict is passed through unchanged.

---

## 4. Stale-data note (transcript account)

The invoice-as-active-CV symptom is already fixed in code (`#908 RC4`): non-CV
document types are blocked from the CV pipeline. A profile that still shows an
invoice as the active CV is **pre-fix stored data**, not current product logic.
Remedy for that account is data cleanup (re-upload a real CV) — user-agnostic;
no code change. (Per Product Generalization Rule: the smoke-test account exposed
it, but the fix is global and already in `main`.)

---

## 5. Verification

- `tests/unit/test_arabic_intent_classifier.py` — added coverage for "new job"
  and colloquial want-verbs (37 → 45+ cases).
- Regression: `test_job_search_role_extraction.py`, `test_intent_classifier.py`,
  `test_bug12_arabic_search_locale.py`, `test_arabic_context_retention.py`,
  and the clarification-path suites — **172 passed**.
- Pre-existing unrelated failure noted:
  `test_location_intent_fix.py::...test_arabic_engineer_dubai_extracts_role`
  expects raw Arabic `مهندس` but the code maps it to English `Engineer` via
  `_ARABIC_TO_ENGLISH_ROLE_MAP` — fails identically without this PR's changes;
  left untouched (out of scope, test-vs-code mismatch).

---

## 6. Theme-transition compatibility (for the parallel command-redesign session)

This backend work is foundational to the `command` i18n / redesign and is safe to
land alongside a parallel frontend theme session:

- **No frontend files touched.** The branch changes only
  `src/agent/intelligence/intent_classifier.py`, `src/rico_chat_api.py`, tests,
  and this doc — `apps/web` diff is empty. No merge conflict with the theme work.
- **Response contract preserved.** The command surface consumes `type`,
  `message`, `options`, `matches`, `apply_url`, `next_action`, `display_label`,
  `suggested_actions`. The clarification change stays `{type, message}` (no field
  added or removed) and the intent-routing changes dispatch to existing handlers
  that already emit these same fields. The new theme changes presentation, not the
  contract — it will receive the same response shape, now backed by real search
  results instead of fabricated ones.
- **Session role:** WRITER on `claude/esg-manager-job-search-k7f8eh` only; the
  theme session remains sole writer on its own branch.

## 7. Open items for owner

1. ~~Approve/deny Phase 2~~ — **DONE** (owner-approved; implemented in §3).
2. Confirm production is running code that includes the §1/§3 guards (deploy
   freshness) — use the read-only `deploy-rico` check.
3. Continuous-learning ("Rico as an entity") remains a separate roadmap
   initiative requiring a scoped plan + cost estimate before any build.
