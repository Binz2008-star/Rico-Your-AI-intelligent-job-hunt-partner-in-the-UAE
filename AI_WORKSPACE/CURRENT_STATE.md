# Current State

_Last updated: 2026-06-24 (image-reading chain complete & live through #741; durable transcript store fixes the postgres-mode follow-up bug; pending owner re-test of the screenshot follow-up)_

## Production baseline

- **Repository main HEAD / production backend SHA:** `7e0b9ec3a3f88b834e9bc19131457a296f9ac1df` (#741 — durable uploaded-document transcript store, postgres-safe).
- **Production deploy verification:** `Deploy Render Backend` + `Deploy to Production` both succeeded for `7e0b9ec` (`/version` match + `/health` 200; clean startup ⇒ lifespan migration runner did not crash). Prior deploys verified in sequence: #739 `f202a86`, #736 `a7e294b`, #738 `115adde`, #737 `e214178`.
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
- **#721 / #722** — degraded job-card actionability (empty `alt_url`).
- **#712 / #711** — migration drift (`005 pipeline_runs`, `011` indexes missing) — still open, separate.
- Older epics/backlog (#654, #618, #531, #356, #355, #354, #353, #352, #294, #263, #213, #198, #196, #187, #179, #147, #140, #138, #127, #118, #105, #99, #96) — not urgent.

## Forward plan (prioritized, 2026-06-24)

1. **Now (owner):** re-test #741 in `/command` — upload job screenshot → buttons + typed Qs answer from the text; never "no file"; never a CV draft. Gates everything image-related.
2. **Next build (recommended): #732** — stop the unevidenced "Developer" target-role push; base guidance on actual CV signals. Owner hits this every session.
3. **Then: Finding 3** — wire read-screenshot → "Save as target job" / "Score against my CV" end-to-end (the "link A↔B without buttons" ask).
4. **Cleanup pass:** close stale PRs #722/#713, salvage #697; Finding 5 (dead `CV_THRESHOLD`, stale `CLAUDE.md` `/chat` note).
5. **Backlog:** #721 degraded cards, #712 migration drift, Finding 4 (onboarding/upload honor `classified`), older epics.

## Recommended next command

```text
Rico mode. Production is 7e0b9ec (#741, durable transcript store) — image-reading chain #736→#739→#741 is live. First confirm the owner re-test of the screenshot follow-up. Then the recommended next build is issue #732 (Rico over-commits to Developer without CV evidence): make career guidance evidence-based, no silent target_role=Developer push. Keep backend-focused, mocks-only tests, no provider/frontend scope creep. After that, Finding 3 (application-evidence destination) completes the screenshot loop.
```
