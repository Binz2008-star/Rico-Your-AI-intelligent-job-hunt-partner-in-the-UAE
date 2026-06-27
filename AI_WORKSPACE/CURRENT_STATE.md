# Current State

_Last updated: 2026-06-27 — **QA Cycle 1 CLOSED.** P0 #764 (mutation trust guard) deployed and verified. BUG-01 through BUG-05, BUG-08, BUG-09, BUG-10 all deploy-verified at `4ad2e29`. BUG-06/BUG-07 blocked (no owner description). Next: P2 user-experience and agent capability improvements._

## QA Cycle 1 — CLOSED 2026-06-27

| Bug | PR | SHA | Deployed | Tests |
|---|---|---:|---|---|
| BUG-01 | #757 | `325aa0e` | ✅ | frontend (sidebar cache) |
| BUG-02 | #759 | `3a9221a` | ✅ | preference sanitization |
| BUG-03 | #760 | `b6a1196` | ✅ | `test_bug03_source_url_fallback.py` 18/18 |
| BUG-04 | #761 | `4918f55` | ✅ | frontend (`/pipeline` → `/flow`) |
| BUG-05 | #762 | `007246b` | ✅ | `test_bug05_confirmation_loop.py` 7/7 |
| BUG-06 | — | — | 🚫 blocked | no description |
| BUG-07 | — | — | 🚫 blocked | no description |
| BUG-08 | #763 | `62ff5ad` | ✅ | `test_bug08_city_declaration.py` 14/14 |
| BUG-09 | — | `46a7ba7` | ✅ | `test_bug09_keyword_filter_bleed.py` 7/7 |
| BUG-10 | — | `b776abf` | ✅ | frontend (double-send `sendingRef`) |
| P0 #764 | #767 | `71466d2` | ✅ | `test_p0_mutation_trust_guard.py` 42/42 |

Regression suite: **104/104 PASS**. 45 pre-existing environment failures (cryptography version, mock log-format, webhook secrets) — none caused by any BUG or P0 change.

## Production baseline

- **Repository main HEAD:** `4ad2e29566c10b389069fc68faacd9f5c1c5c010` (PR #767 — P0 mutation trust guard). Full merge train in production: P0 `71466d2`, BUG-10 `b776abf`, BUG-09 `46a7ba7`, BUG-08 `62ff5ad`, BUG-05 `007246b`, BUG-04 `4918f55`, BUG-03 `b6a1196`, BUG-02 `3a9221a`, BUG-01 `325aa0e`, #755 `504c755`.
- **Last deploy-verified SHA:** `4ad2e29` — `deploy-render.yml` run #28301440105 succeeded (gated on `/version.commit` match + `/health` 200). ✅
- **Production deploy verification history:** `4ad2e29` (run #28301440105), `6113123` (run #80), `0d28a08` (#747), `7e0b9ec` (#741), `f202a86` (#739), `a7e294b` (#736), `115adde` (#738), `e214178` (#737).
- **Pending owner-side smoke:** authenticated save→count flow and #741 screenshot follow-up require `ricohunt.com` login — sandbox cannot reach authenticated production.
- **Migration 032 (`uploaded_document_context`):** auto-applied on startup via the app.py lifespan runner (idempotent `CREATE TABLE/INDEX IF NOT EXISTS`), targeting the exact branch the production `DATABASE_URL` uses. Direct confirmation of the `migration_ok` log line / table existence needs Render-log or Neon access (unavailable in-session) — the owner re-test is the end-to-end proof.
- **Image reading reliability:** `OCRSPACE_API_KEY` set on Render as a dependable free OCR backstop behind the (rate-limited) free vision model (OpenRouter/HF).
- **Render logs:** direct Render MCP log scan unavailable in-session; no error signals from `/health` or deploy workflows.

## Job-flow stabilization — 2026-06-22 complete

Rico's job-search flow was stabilized through a focused merge train. Each PR stayed in one bug category, used mocked tests/fixtures, avoided provider quota burn, and excluded #712 DB migration work, billing changes, landing-page changes, and provider scraping.

| PR | Category | Merge SHA | Deploy | Tests / notes |
|---|---|---:|---|---|
| **#727** | P0 — job-card apply-link integrity + canonical `src/services/job_link.py` | `e1d87fc` | ✅ verified | `test_job_card_apply_link_integrity.py`; no more missing required `link` error |
| **#724** | P1 — low-cost provider cascade (cache → internal → Jooble → Adzuna → JSearch → degraded CTA) | `5fe9171` | ✅ verified | `test_job_providers.py`, `test_provider_degraded_ux.py` |
| **#723** | P1 — multi-role parsing (`extract_role_list`, `job_search_multi_role`) | `713ea75` | ✅ verified | `test_multi_role_search_*.py` |
| **#728** | P0 follow-up — route ordinal apply-link requests past job-detail gate | `c77781a` | ✅ verified | `test_ordinal_apply_link_routing.py` |
| **#729** | PR B — save the Nth job to pipeline from recent search context | `963e40b` | ✅ verified | `test_save_ordinal_to_pipeline.py` |
| **#730** | PR D — role parsing edge cases: `only`, jobs-for-A-and-B, CV exclusions, category mapping / not coding | `38fbf5d` | ✅ verified | `test_role_parsing_edge_cases.py` |

## Key production behaviors now live

- `src/services/job_link.py` is the **only canonical apply-link resolver**. Do not reintroduce `src/rico_link_resolver.py`.
- Job cards and chat apply-link commands share canonical `usable_link` / `link_unavailable` fields.
- `apply_job` no longer throws `Job payload is missing required 'link' field`; missing trusted links produce safe fallback CTAs.
- Ordinal apply-link commands work for first/second/last job references from recent search context.
- Save-to-pipeline works for ordinal references such as "save the second job".
- Provider cascade is live: cache(24h) → internal → Jooble → Adzuna → JSearch → degraded fallback CTA.
- `/health` exposes `job_providers` configured/degraded state only; no secret values.
- Role parsing now handles:
  - `Technical Product Owner only` → `Technical Product Owner`
  - `jobs for HSE Manager and QHSE Manager` → both roles
  - CV-based search with `do not search …` exclusions
  - `product and technical management jobs, not coding jobs` → allowed management roles + coding exclusions

## Provider env

Set in Render by the owner; presence only is observable via `/health`:

- `JOOBLE_API_KEY`
- `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` (Adzuna opt-in; both required)
- `RAPIDAPI_KEY` (JSearch)

No provider keys are hardcoded, committed, or logged.

## Production Tests 1–9 status

| Test | Bug | Status |
|---|---|---|
| T2 | `Technical Product Owner only` qualifier | ✅ fixed live (#730) |
| T3 | `HSE Manager and QHSE Manager` jobs-for-A-and-B order | ✅ fixed live (#730) |
| T4 | 3-role comma list as one role | ✅ fixed live (#723) |
| T5 | CV-based search + `do not search …` exclusions | ✅ fixed live (#730) |
| T6 | category mapping `product/technical management` + `not coding` | ✅ fixed live (#730) |
| T8 | `save the second job to pipeline` not wired to recent context | ✅ fixed live (#729) |
| T9 | open apply link → missing-link error | ✅ fixed live (#727 + #728) |
| T1 | strongest CV profile ignored; stale `target_role` | ✅ fixed live (#731 PR C) |
| T7 | silent role substitution + auth/CV context loss + weak location | ✅ fixed live (#731 PR C) |

## Merge train after #730 (all live on `main`)

| PR | What | Merge SHA | Status |
|---|---|---:|---|
| **#731** | PR C — profile-context role selection (T1 & T7): no silent stale/ambiguous search; ambiguity by role-family not raw count; raw role text preserved | `9a9070c` | ✅ merged + deployed |
| **#733** | Investigation/test-only — production-equivalent live-path tests for T2–T6 role parsing | `ab170e2` | ✅ merged |
| **#734** | Career-memory identity resolution fix | `5944d72` | ✅ merged |
| **#735** | Single-role parsing accepts explicit titles like "Technical Product Owner" (live recheck found single-role rejected what multi-role accepted) | `96f415a` | ✅ merged + deployed |
| **#737** | Attachment/document routing — keep no-text/image-only PDFs out of the CV pipeline (#674 residual, Finding 1) | `e214178` | ✅ merged + deploy-verified |
| **#738** | Upload size limits — 25 MB docs / 10 MB images, per-kind cap enforced before parsing, friendly type-aware AR/EN oversize messages (fixes the misleading "under 10 MB" CV rejection) | `115adde` | ✅ merged + deploy-verified |
| **#736** | Image reading (Finding 2) — job-screenshot images transcribed via free VLM (OpenRouter/HF) + OCR.space fallback, re-classified to a readable `classified` response; graceful (never blocks uploads) | `a7e294b` | ✅ merged + deploy-verified |
| **#739** | Image/document action follow-up — buttons (Describe/Extract/Summarize) answer from the stored transcript via an early interceptor (no CV-draft hijack); transcript injected into AI context for typed questions | `f202a86` | ✅ merged + deploy-verified |
| **#741** | Durable transcript store (`uploaded_document_context` table + repo) — fixes the postgres-mode bug where the OCR transcript was saved only to the no-op `RicoMemoryStore`; follow-ups now read durably; migration 032 auto-applies on startup | `7e0b9ec` | ✅ merged + deploy-verified (owner re-test pending) |
| **#747** | Phase-0 job-link trust gate (`src/services/job_link_trust.py`) — View & Apply may only surface a source-backed, non-fake, non-LLM apply URL; rejects recent_context/LLM/sequential-LinkedIn/placeholder URLs; `apply_to_job` restored with safe action errors | `0d28a08` | ✅ merged + deploy-verified |
| **#749** | Pipeline save/count correctness — chat ordinal "save the Nth job" now persists to the user-scoped counted store (`rico_job_recommendations`), idempotent on a trusted save identity; untrusted recent_context jobs save as leads with no claimed apply link; user-safe save errors (`src/services/job_save.py`) | `6113123` | ✅ merged + deploy-verified (owner-side authenticated smoke pending) |
| **#755** | Link quality (#721) — `employer_url` + `apply_is_direct` surfaced from JSearch `employer_website` / `job_apply_is_direct`; `apply_is_direct=True` upgrades unknown domains to `live_verified`; aggregator/login/rate-limited never overridden; `employer_url` returned as separate field, never in apply_link/alt_link/usable_link; company-site fallback CTA uses real URL when available (label "Company website" vs "Search company site") | `504c755` | ✅ merged + deploy-verified |

> Note: `fix/single-role-taxonomy-rejection` was an independent duplicate of the #735 fix built in another session — **abandoned** (not merged). Do not revive it.

## Attachment / Document Intelligence routing — 2026-06-23

- **Audit:** `AI_WORKSPACE/audits/attachment-document-routing-post-674-677.md` (Findings 1–5). #677 shipped native-image classification on `/command`; the audit found the residual gaps.
- **#737 (Finding 1, merged):** a screenshot/scan exported as a PDF (image-only PDF, no text layer) used to fall through `unknown@0.0` into CV extraction → misleading "poor quality" CV preview. The classifier now tags a *substantial* (`>= _MIN_DOC_BYTES`, 1 KB) text-bearing file with near-empty text (`< _MIN_TEXT_CHARS`, 25) as `no_text`; `/upload-cv` returns a clear needs-text response (`status="classified"`, `document_type="no_text"`) before the CV pipeline. Tiny stub PDFs still flow normally; native images unchanged; real text CVs unchanged. Tests: `tests/test_no_text_pdf_routing.py`.
- **#738 (upload size, merged):** documents 25 MB / images 10 MB, per-kind cap enforced from magic-byte format **before** parsing; friendly type-aware oversize message (413) replacing "exceeds 10 MB"; `/command` + `/onboarding` map 413 → localized `cmdCvTooLarge` (AR/EN); `files.py` doc cap also 25 MB. Tests: `tests/test_upload_size_limits.py`, `apps/web/__tests__/cv-upload-size-message.test.ts`.
- **Open findings (NEXT work):** **Finding 3** — no application-evidence destination (read screenshot → "Save as target job" / "Score against my CV" not wired end-to-end; this is the owner's "link A↔B without buttons" ask). **Finding 4** — `onboarding`/`upload` surfaces still don't honor `status="classified"` for non-CV docs/images (#738 only added 413 size handling). **Finding 5** — dead `CV_THRESHOLD`; stale `CLAUDE.md` `/chat` reference (trivial cleanup).

## Image-reading chain (Finding 2) — COMPLETE & LIVE

`#736 → #739 → #741`, all merged + deploy-verified. Flow: upload image → free VLM (OpenRouter/HF) or **OCR.space** fallback transcribes it → re-classify transcript → readable `classified` response. Follow-up buttons (Describe/Extract/Summarize) and typed questions ("what do you think of this job?") answer from the transcript; **never** a CV-draft hijack; honest "no readable document" when nothing was read.

- **Durability (#741):** the transcript is persisted in the durable `uploaded_document_context` table (migration 032, auto-applied on startup) — fixes the prod bug where it was saved only to the `RICO_MEMORY_BACKEND=postgres`-disabled `RicoMemoryStore`. Read path: `_get_last_uploaded_document` (ephemeral fast-path → durable DB), used by `_handle_uploaded_document_followup` and `_build_openai_context`. Keyed by resolved `user_id` (email / `public:web-*`), one row per user, 180-min freshness window.
- **Provider env (owner-set on Render):** `OCRSPACE_API_KEY` set (reliable OCR backstop); optional `OPENROUTER_API_KEY` / `OPENROUTER_VISION_MODEL` or a free HF Inference Provider on `HF_TOKEN`.
- **Pending:** owner re-test in `/command` (upload job screenshot → buttons + typed Qs answer from the text). Sandbox can't reach `onrender.com` / Neon, so the re-test is the end-to-end proof of migration 032 + the durable store.
- **Tests:** `tests/test_uploaded_document_durable_context.py`, `tests/test_uploaded_image_ai_context.py`, `tests/unit/test_image_extractor.py`, `tests/unit/test_upload_image_vision.py`.

## Standing guardrails for this work-stream

- No auth rewrite, no billing changes, no DB migration, no #712 work, no landing-page work, no provider scraping, no repeated real provider searches.
- Use mocks/fixtures only in tests; no live OpenAI/HF/JSearch/Telegram/Jotform calls in unit tests.
- Keep `src/services/job_link.py` as the only canonical apply-link resolver; do not reintroduce `src/rico_link_resolver.py`.

## Superseded / duplicate PRs

- **#726** — closed as superseded by #727 + #728 + #729. Do not rebase or salvage it.
- **#722** — degraded job-card fallback CTAs; overlaps #724/#727. Close or rebase only if a new focused gap is proven.

## Important older context still relevant

- **#712 DB migration drift:** still separate; do not mix with job-flow work.
- **System Quality Audit PR #717:** draft/CI-green status was documented earlier; do not merge without separate review.
- **Migration `030_action_audit_log_hardening.sql`:** applied + verified in production Neon on 2026-06-21.
- **Migration `021_user_job_context_alt_url.sql`:** applied; issue #710 closed.
- **Issue #711 drift:** `005 pipeline_runs` and `011 idx_rico_recommendations_user_job_unique` remain not applied unless separately approved.
- **Canonical handoffs:** `AI_WORKSPACE/HANDOFFS/2026-06-22-job-flow-stabilization-complete.md` (job-flow train through #730), `AI_WORKSPACE/HANDOFFS/2026-06-23-attachment-document-routing.md` (document routing #737 + #736 review).

## Open PRs — triage (6, all stale / pre-session 2026-06-20..22)

| PR | What | Recommendation |
|---|---|---|
| **#722** | degraded job-card fallback CTAs | **Close** — overlaps merged #724/#727 |
| **#713** | CI read-only `verify_710` audit job (Draft) | **Close** — #710 verified/closed; diagnostic obsolete |
| **#698** | docs: agentic vision (Draft, docs only) | keep as reference or close; no runtime code |
| **#697** | reject "تمام" as a city value | **Salvage** — real small bug; rebase + ship |
| **#691** | frontend onboarding checklist + help icon | review; needs rebase + `npm run build` |
| **#688** | frontend `/ask` agentic UX (mock data) | review/park; bigger, mock-only |

## Open issues — highlights (29 total)

- **#732 — Rico over-commits to "Developer" without evidence.** HIGH value, owner-facing: profiles show `Target Roles: Developer` despite the real profile (Technical Product Owner / Operations Manager). Career guidance should be CV-evidence-based.
- **#732 — Rico over-commits to "Developer" without evidence** (see above).
- **#712 / #711** — migration drift (`005 pipeline_runs`, `011` indexes missing) — still open, separate.
- Older epics/backlog (#654, #618, #531, #356, #355, #354, #353, #352, #294, #263, #213, #198, #196, #187, #179, #147, #140, #138, #127, #118, #105, #99, #96) — not urgent.

## Phase-0 trust + save/count — COMPLETE & LIVE (2026-06-25)

- **#747 (trust gate, live):** `resolve_trusted_apply_url` is the only sanctioned apply-URL resolver. Untrusted origins (`recent_context`, `llm`, `chat`, `search_match`, …) are rejected at Gate 0; placeholder/sequential-LinkedIn/bad-scheme URLs rejected; a trusted provenance marker (`persisted_job_id` / `source_job_id` / `provider`+`source_backed`) is required. `apply_to_job` no longer errors on missing links — safe action messages instead.
- **#749 (save/count, live):** the chat ordinal save persists to the counted `rico_job_recommendations` (so the application/pipeline count actually increments), idempotent on a trusted save identity (`source_job_id`/`persisted_job_id`, else a `title|company` hash — never the bare `job_id`). A recent_context job is still saved, as a **lead**, with no apply URL persisted and no verified-link claim. Save failures return user-safe messages. No `pipeline_runs` (migration 005 / #711) dependency. Helper: `src/services/job_save.py`; tests: `tests/test_pipeline_save_count_correctness.py`.
- **Pending:** owner-side authenticated smoke on `ricohunt.com` — search a role, "save the second job to my pipeline" → count +1, repeat → count unchanged. Sandbox cannot reach authenticated production.

## Rico Website Hard QA — BUG-01 through BUG-08 (2026-06-27)

Fixing bugs from the "Rico Website Hard QA Report". Each PR is one bug category, focused diff only. No SQL, no schema migrations, no provider API calls in tests.

| BUG | PR | Merge SHA | Status | Description |
|---|---|---:|---|---|
| **BUG-01** | #757 | `325aa0e` | ✅ merged | Bust sidebar cache after chat save; correct `/flow` destination in save copy |
| **BUG-02** | #758 | `3a9221a` | ✅ merged | Sanitize `preferred_cities` at profile read/write boundary; strip corrupted AI-response values stored as city names |
| **BUG-03** | #760 | `b6a1196` | ✅ merged | Sidebar nav routing (href not chatPrompt), icon rendering, pipeline counter |
| **BUG-04** | #761 | `4918f55` | ✅ merged | Redirect `/pipeline` → `/flow` (old route returned 404) |
| **BUG-05** | #762 | `007246b` | ✅ merged | "Yes, search {role}" quick-reply button caused infinite confirmation loop; interceptor added before role classification in `_handle_active_user_inner` |
| **BUG-06** | — | — | 🚫 blocked — no description | Description not found in repo, GitHub issues, or any workspace doc. Owner must supply original QA report entry. |
| **BUG-07** | — | — | 🚫 blocked — no description | Description not found in repo, GitHub issues, or any workspace doc. Owner must supply original QA report entry. |
| **BUG-08** | #763 | `62ff5ad` | ✅ merged | "My favorite city is Dubai" silently ignored (3 stacked bugs: intent regex, router regex, `preferred_city` vs `preferred_cities`). |
| **BUG-09** | — | — | 🔄 in progress | Contradictory keyword filters: excluded keywords bleed across sessions / are not cleared when user removes them. |
| **BUG-10** | — | — | ⏸ not started | Rapid double-send drops a message (race condition in frontend submit guard). |
| **BUG-11** | — | — | ⏸ not started | Duplicate quick-reply buttons rendered on some responses. |
| **BUG-12** | — | — | ⏸ not started | Search results body ignores Arabic locale. |
| **BUG-13** | — | — | ⏸ not started | Profile/role drift across multiple uploaded CVs — wrong role shown after re-upload. |
| **BUG-14** | — | — | ⏸ not started | No save idempotency on pipeline: second "save this job" shows success but increments counter. |
| **BUG-15** | — | — | ⏸ not started | Internal API name leaked to user-facing UI ("JSearch API" visible in responses). |
| **BUG-16** | — | — | ⏸ not started | "Waking up" banner overlaps chat content (CSS z-index). |
| **BUG-17** | — | — | ⏸ not started | Sidebar widgets disappear on `/queue` and `/upload` pages. |
| **BUG-18** | — | — | ⏸ not started | `?q=` query-string navigation mutates / resets chat thread. |
| **BUG-19** | — | — | ⏸ not started | Job-confirmation screenshots not classified as application evidence → "Unrecognized Document"; save falls back to wrong recent-context job. Two sub-bugs: (A) no application-confirmation image classifier, (B) job-extraction on save ignores uploaded image context. |

> ✅ **QA Cycle 1 is CLOSED.** BUG-01 through BUG-05, BUG-08, BUG-09, BUG-10, and P0 #764 are all confirmed deployed and smoke-tested at `4ad2e29`. BUG-06 and BUG-07 remain blocked until the owner supplies original QA report descriptions.

## PR #756 — Migration drift runbook (docs-only)

- **Status:** ✅ Merged at `2ef4107` (2026-06-27). Content: 606-line `docs/runbooks/production-drift-005-011.md`.
- **Rollback execution (owner-only):** after G1–G6 signed off, owner applies migrations 011 (Step A) then 005 (Step B) via Neon console.

## Forward plan — P2 User Experience and Agent Capabilities (2026-06-27)

QA Cycle 1 is complete. The focus shifts from bug-patching to meaningful user-facing improvements.

1. **P2-A — Attachment and image understanding (end-to-end):**
   Finding 3 (link screenshot → "Save as target job" / "Score against my CV") and Finding 4 (onboarding `classified` surface for non-CV docs). Infrastructure is in place (#736→#739→#741); wiring the action buttons end-to-end is the gap.

2. **P2-B — Direct chat mutations (delete, update, follow-up):**
   Users want to delete saved jobs, update application status, and set reminders through chat. Today these are intercepted with a redirect. The long-term fix is a real backend tool for each mutation, gated by `agent_runtime.handle_action()`, so Rico can actually execute them instead of redirecting.

3. **P2-C — Agent Runtime improvements:**
   - Improve `handle_action("remind")` reliability (currently stub-level).
   - Add `handle_action("delete_saved_job")` and `handle_action("update_application_status")` as real tools.
   - Idempotency keys and audit logging already in place — the tool implementations are missing.

4. **P2-D — Memory and session continuity:**
   Rico loses context on page reload and across sessions for public users. Durable `uploaded_document_context` is solved (#741). Next: persist role preferences and search context durably per-user so Rico doesn't ask for the same info twice.

5. **P2-E — Hallucination reduction:**
   Issue #732 (Rico over-commits "Developer" without CV evidence) is still open. Extend the role-evidence guard to all profile fields — Rico must not claim a role, city, or seniority level without a grounded source (CV or explicit user statement).

6. **P2-F — QA Cycle 2 (BUG-11 through BUG-19):**
   Secondary bug queue. Start after P2-A and P2-B are underway. BUG-19 (job-confirmation screenshot classifier) naturally pairs with P2-A.

7. **Blocked / owner-only:**
   - BUG-06, BUG-07: await owner QA report descriptions.
   - Migration drift #712 (migrations 005 and 011): runbook ready, G1–G6 sign-off required before any Neon SQL.

## Recommended next command

```text
Rico mode. QA Cycle 1 closed. Production at 4ad2e29 — all verified. Next: P2 user-experience track. Recommended start: P2-B (direct chat mutations — give Rico real delete/update/remind tools via agent_runtime) OR P2-E (Issue #732 role-evidence guard). Do NOT start BUG-11 through BUG-19 before P2-A or P2-B has a branch. Do NOT run migrations without owner G1–G6 sign-off.
```
