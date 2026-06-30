# Current State

_Last updated: 2026-06-30 — **PR #781 merged** (fix: question-form application routing + sidebar nav/count/plan fixes). Production HEAD: `e4979eb`. Previous: `0e0a6aa` (dashboard), `6863409` (PR #780 — Chat-OS action cards for application\_status + prepare\_application), `f0e0cea` (PR #776 — No Dead UI Rule). Chat routing and sidebar nav are now correct. Forward focus: remaining smoke-test bugs from the 2026-06-30 QA session._

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

## PR #780 + #781 — Chat-OS agentic UI + smoke-test fixes (2026-06-30)

### PR #780 — action cards for `application_status` and `prepare_application`
Merged at `6863409`. Added `_application_status_actions()` and `_prepare_application_actions()` factories to `agentic_ui_composer.py` and registered them in `_RESPONSE_TYPE_ACTIONS`. Tests: 6 new unit tests in `test_agentic_ui_composer.py`.

| Response type | Action cards |
|---|---|
| `application_status` | View Application Flow (navigate /flow) · Add application (chat_continue) |
| `prepare_application` | View Application Flow (navigate /flow) · Find similar jobs (chat_continue) |

### PR #781 — question-form routing + sidebar nav/count/plan fixes
Merged at `e4979eb`. Squash commit on `main`.

| Fix | What | Files |
|---|---|---|
| Chat routing | Extended `_APPLICATIONS_LIST_RE` to match question-form phrases ("what are my applications?", "how many applications do I have?", etc.) — previously fell to AI path with no action cards | `src/rico_chat_api.py` |
| Composer mapping | Added `"application_list": _application_status_actions` to `_RESPONSE_TYPE_ACTIONS` so both question-form and tracker-card responses get action cards | `src/services/agentic_ui_composer.py` |
| BUG-1 (sidebar count) | `useSidebarStatus.ts` now uses `stats.total` from backend rather than summing only `applied+interview+offer+saved+rejected` — previously missed `opened`, `opened_external`, `prepared`, `follow_up_due`, `decision_made` | `apps/web/hooks/useSidebarStatus.ts` |
| BUG-4 (sidebar nav) | Removed `chatPrompt` from all nav items — sidebar links now always navigate to real pages, never inject `/command?q=…` URLs | `apps/web/components/layout/app-nav.ts` |
| BUG-5 (plan label) | "Pro Plan" → "My Plan" nav label + `navMyPlan` translation key (EN + AR) — eliminates "Pro Plan / PREMIUM" badge contradiction | `apps/web/components/layout/app-nav.ts`, `AppSidebar.tsx`, `translations.ts` |

## Production baseline

- **Repository main HEAD:** `e4979eb` (PR #781 — chat routing + sidebar fixes). Merge train: `0e0a6aa` (dashboard), `6863409` (PR #780 — Chat-OS action cards), `f0e0cea` (PR #776 — No Dead UI Rule + route cleanup), `744dbec` (PR #775 — P2-A), `78c22857` (PR #770 — Chat-as-interface milestone), `4ad2e29` (PR #767 — P0 mutation trust guard).
- **Last deploy-verified SHA:** `4ad2e29` — `deploy-render.yml` run #28301440105 succeeded. ✅ (PRs #770, #775, #776, #780, #781 are frontend-only or backend-lightweight; Render deploy auto-triggered for backend changes but not yet re-verified in-session.)
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
| **BUG-09** | #791 | `merged` | ✅ merged | Sidebar widgets disappear on `/upload` page — `sidebarProps` was not passed; fixed by threading `onLogout` + `sidebarProps` through the page component |
| **BUG-10** | #792 | `merged` | ✅ merged | Data quality: years experience displayed as `30.0`; salary displayed without comma (`AED 18000/month`). Fixed `_target_role_search_response` (int rounding) and `_format_pref_changes` (comma-format). Tests: `test_bug10_data_quality_display.py` |
| **BUG-11** | #793 | `merged` | ✅ merged | Name casing inconsistency — CV names extracted verbatim (ALL CAPS on UAE CVs). `CVParser._extract_name` now returns `line.title()`. Tests: `test_bug11_name_casing.py` |
| **BUG-12** | — | — | ⏸ not started | Search results body ignores Arabic locale. |
| **BUG-13** | — | — | ⏸ not started | Profile/role drift across multiple uploaded CVs — wrong role shown after re-upload. |
| **BUG-14** | — | — | ⏸ not started | No save idempotency on pipeline: second "save this job" shows success but increments counter. |
| **BUG-15** | #794 | open | 🔄 PR open | Internal API name leaked to user-facing UI ("JSearch API" visible in responses). Fixed in `apps/web/lib/translations.ts`. |
| **BUG-16** | #794 | open | 🔄 PR open | "Waking up" banner overlaps chat content (CSS z-index). Fixed in `apps/web/app/command/page.tsx` (pt-12/pt-14). |
| **BUG-17 (pipeline reset)** | — | `61b783b` | ✅ pushed | "Clear them we must start over" misclassified as job role search. Fixed: "clear"/"reset" added to `_NON_ROLE_STARTERS`; `_PIPELINE_RESET_RE` + `_PIPELINE_RESET_IMPLICIT_RE` added; 2-turn Archive/Delete/Cancel confirmation flow. Tests: `test_bug17_pipeline_reset.py` 13/13. |
| **BUG-18** | — | — | ⏸ not started | `?q=` query-string navigation mutates / resets chat thread. |
| **BUG-19** | — | — | ⏸ not started | Job-confirmation screenshots not classified as application evidence → "Unrecognized Document"; save falls back to wrong recent-context job. |

> ✅ **QA Cycle 1 is CLOSED.** BUG-01 through BUG-05, BUG-08, BUG-09, BUG-10, and P0 #764 are all confirmed deployed and smoke-tested at `4ad2e29`. BUG-06 and BUG-07 remain blocked until the owner supplies original QA report descriptions.

## PR #756 — Migration drift runbook (docs-only)

- **Status:** ✅ Merged at `2ef4107` (2026-06-27). Content: 606-line `docs/runbooks/production-drift-005-011.md`.
- **Rollback execution (owner-only):** after G1–G6 signed off, owner applies migrations 011 (Step A) then 005 (Step B) via Neon console.

## Chat-as-Interface milestone — PR #770 (2026-06-28)

Merged at `78c22857`. Squash commit: `feat(chat-as-interface): P2-B delete-saved-jobs + PR-A agentic UI schema + PR-C live action cards`.

| Sub-feature | What shipped |
|---|---|
| **P2-B** | 2-turn delete-saved-jobs confirmation (`_handle_pending_delete_saved_jobs`, memory TTL, `delete_saved_jobs_confirm` → `delete_saved_jobs_done`) |
| **PR-A** | `RicoAgenticUi` Pydantic schema (`src/schemas/chat.py`) — actions, permission_request, proposed_changes, attachment_analysis, progress |
| **PR-C** | `compose(result, response_dict)` in `src/services/agentic_ui_composer.py` — emits type-based action cards on every real chat response |
| **MagicMock fix** | `isinstance(ctx, dict)` guard in `_handle_pending_delete_saved_jobs` — fixes 10 previously-failing tests |
| **Tests** | 38 `test_agentic_ui_composer.py` + 41 `test_attachment_analysis_factory.py` + 2 conversation-state fixes |

Action cards now emitted by type:

| Response type | Actions |
|---|---|
| `job_matches` | View all jobs (navigate /flow) + Save search (chat_continue) + Refine search (chat_continue) |
| `delete_saved_jobs_confirm` | Yes, delete all (high impact, requires_confirmation) + No, keep them |
| `delete_saved_jobs_done` | Find new jobs (chat_continue) |
| `profile_update` / `profile_summary` / `cv_first_profile` | View my profile (navigate /profile) |
| `application_status_update` | Track applications (navigate /applications) |
| `save_job` | View saved jobs (navigate /flow) |
| `application_list` / `application_status` | View Application Flow (navigate /flow) + Add application (chat_continue) — **added PR #780/#781** |
| `prepare_application` | View Application Flow (navigate /flow) + Find similar jobs (chat_continue) — **added PR #780** |

---

## Route architecture — post-PR #776

**No Dead UI Rule** adopted (DEC-20260628-001 in `AI_WORKSPACE/DECISIONS.md`, enforced in `OPERATING_RULES.md`):
a route must be active+reachable, redirect-only with no real page code, or removed.

| Route | State | Notes |
|---|---|---|
| `/command` | ✅ active | Primary chat surface |
| `/flow` | ✅ active | Application flow page |
| `/login`, `/signup`, `/forgot-password` | ✅ active | Auth surfaces |
| `/chat` | ✅ redirect-only | `next.config.js` → `/command`; stub deleted (Phase A) |
| `/orchestrate` | ✅ redirect-only | `next.config.js` → `/command`; stub deleted (Phase A) |
| `/pipeline` | ✅ redirect removed | No page ever existed; redirect had no purpose |
| `/dashboard` | ⚠️ Phase B | Redirect + 48-line page. Needs product decision: live or strip. |
| `/onboarding` | ⚠️ Phase B | Redirect + 466-line page. Needs product decision: live or strip. |
| `/jobs` | ⚠️ Phase B | Redirect + 336-line page. Needs product decision: live or strip. |
| `/signals` | ⚠️ Phase B | Redirect + 576-line page. Needs product decision: live or strip. |
| `/archive` | ⚠️ Phase B | Redirect + 162-line page. Needs product decision: live or strip. |
| `/saved-searches` | ⚠️ Phase B | Redirect + 102-line page. Needs product decision: live or strip. |

Phase B routes are blocked until each gets an explicit product decision.

## Career Operating System — forward plan

Per owner direction (2026-06-28), the next development focus is Career OS / Mission Control, introduced in one PR per phase:

1. **Current Mission** — what is Rico working on right now for the user
2. **Mission Feed** — live updates from the job search pipeline
3. **Daily Actions** — surfaced tasks Rico recommends each day
4. **Career Timeline** — application history and progress
5. **AI Workspace** — Rico's reasoning and plan visible to the user

Do not open more than one PR per phase. Do not revive Phase B routes until product decision is made.

## 2026-06-30 Smoke-test bug backlog (new — from owner production testing session)

These are separate from the QA Cycle 1 BUG-01/19 list above.

| ID | Status | Description |
|---|---|---|
| **BUG-1** | ✅ fixed (PR #781) | Sidebar pipeline count disagreed with /flow and chat — sidebar was summing subset of statuses, missing opened/prepared/follow_up_due/decision_made |
| **BUG-2** | ✅ fixed (PR #786, `c8aabd7`) | Self-cancelling keyword filters: `exclude_keywords` was read from a process-global env var instead of per-user settings, and `include_keywords` was never read in scoring at all — fixed in `src/scoring.py` to honor per-user include/exclude keywords (exclude still wins on overlap, by design) |
| **BUG-3** | ✅ fixed (PR #787, `83e961e2`) | Duplicate board entry: same job appears twice on /flow kanban board |
| **BUG-4** | ✅ fixed (PR #781) | Sidebar nav links injected `/command?q=…` URLs instead of navigating to real pages |
| **BUG-5** | ✅ fixed (PR #781) | "Pro Plan / PREMIUM" label contradiction in sidebar |
| **BUG-6** | ✅ fixed (PR #788, `cc1eed1`) | Status taxonomy mismatch: list view vs kanban board use different status labels — `apps/web/lib/applicationStatus.ts` is now the single source of truth for status list + stage grouping, consumed by list view, board view, StatusBadge, and the chat pipeline summary |
| **BUG-7** | ⏸ open | Session hydration: user appears logged-out on first load until hard refresh |
| **BUG-8** | ⏸ open | (details in session history) |
| **BUG-9** | ⏸ open | Sidebar widgets disappear on /upload page |
| **BUG-10** | ⏸ open | Data quality: 30.0 years experience displayed, salary inconsistency |
| **BUG-11** | ⏸ open | Name casing inconsistency in profile |

## Recommended next command

```text
Rico mode. PR #780/#781 (BUG-1/4/5), #786 (BUG-2 keyword conflict), #787 (BUG-3 duplicate board entry), and #788 (BUG-6 status taxonomy) are all merged and deployed. Open bugs from 2026-06-30 smoke test: BUG-7 (session hydration), BUG-9 (sidebar /upload), BUG-10 (data quality: experience/salary display), BUG-11 (name casing inconsistency). Fix in priority order. One PR per bug group. Do NOT touch /dashboard, /onboarding, /jobs, /signals, /archive, /saved-searches until Phase B product decision. Do NOT run migrations without owner G1–G6 sign-off.
```
