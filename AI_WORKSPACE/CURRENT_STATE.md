# Current State

_Last updated: 2026-06-23 (job-flow stable through #735; #737 no_text + #738 size limits + #736 image reading + #739 image/document follow-up handling all merged & live; OCRSPACE_API_KEY set on Render as the reliable OCR backstop)_

## Production baseline

- **Repository main HEAD / production backend SHA:** `f202a86fcba2c66b953256e4ec0ca71744f9f91f` (#739 — image/document action requests answered from transcript; no CV-draft hijack).
- **Production deploy verification:** `Deploy Render Backend` + `Deploy to Production` both succeeded for `f202a86` (`/version` match + `/health` 200). #736 `a7e294b`, #738 `115adde`, #737 `e214178` were deploy-verified in sequence.
- **Image reading reliability:** `OCRSPACE_API_KEY` configured on Render (owner) as a dependable free OCR backstop behind the (rate-limited) free vision model — image text extraction should now be consistent.
- **Vercel:** production/root/proxy healthy by deploy verification.
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
| **#736** | Image reading (Finding 2) — job-screenshot images transcribed via free VLM (OpenRouter/HF) + OCR.space fallback, re-classified to a readable `classified` response; graceful (never blocks uploads) | `a7e294b` | ✅ merged + deploy-verified (owner key set; live smoke test pending) |

> Note: `fix/single-role-taxonomy-rejection` was an independent duplicate of the #735 fix built in another session — **abandoned** (not merged). Do not revive it.

## Attachment / Document Intelligence routing — 2026-06-23

- **Audit:** `AI_WORKSPACE/audits/attachment-document-routing-post-674-677.md` (Findings 1–5). #677 shipped native-image classification on `/command`; the audit found the residual gaps.
- **#737 (Finding 1, merged):** a screenshot/scan exported as a PDF (image-only PDF, no text layer) used to fall through `unknown@0.0` into CV extraction → misleading "poor quality" CV preview. The classifier now tags a *substantial* (`>= _MIN_DOC_BYTES`, 1 KB) text-bearing file with near-empty text (`< _MIN_TEXT_CHARS`, 25) as `no_text`; `/upload-cv` returns a clear needs-text response (`status="classified"`, `document_type="no_text"`) before the CV pipeline. Tiny stub PDFs still flow normally; native images unchanged; real text CVs unchanged. Tests: `tests/test_no_text_pdf_routing.py`.
- **#738 (upload size, merged):** documents 25 MB / images 10 MB, per-kind cap enforced from magic-byte format **before** parsing; friendly type-aware oversize message (413) replacing "exceeds 10 MB"; `/command` + `/onboarding` map 413 → localized `cmdCvTooLarge` (AR/EN); `files.py` doc cap also 25 MB. Tests: `tests/test_upload_size_limits.py`, `apps/web/__tests__/cv-upload-size-message.test.ts`.
- **Open findings (not yet scoped):** Finding 3 (no application-evidence destination), Finding 4 (`onboarding`/`upload` surfaces still don't honor `status="classified"` for non-CV docs/images — #738 only added 413 size handling there), Finding 5 (dead `CV_THRESHOLD`; stale `CLAUDE.md` `/chat` reference). Finding 2 = #736 below.

## #736 — image reading (Finding 2): MERGED + LIVE (`a7e294b`)

Merged and deploy-verified. Reads job-screenshot images → re-classifies the transcript → readable `classified` response. Backend-only, free, no OpenAI, no local OCR binaries (Render native runtime can't install Tesseract/RapidOCR). Never raises → falls back to format-only image response, so it's safe even if the model is unreachable. Owner has set an API key on Render (env-updated redeploy observed). **Remaining:** one live screenshot smoke test in `/command` by the owner (sandbox can't reach `onrender.com`) — success = Rico replies "I read your image …" with action buttons; failure = plain "Image" (then tune key/model, no breakage).

**Provider chain (env-gated, all free):**
1. Vision-language model via OpenAI-compatible chat — **OpenRouter** (`OPENROUTER_API_KEY`, default `meta-llama/llama-3.2-11b-vision-instruct:free`) preferred → HF-independent; else **HF Inference Router** (`HF_TOKEN`, `Qwen/Qwen2.5-VL-7B-Instruct`).
2. **OCR.space** fallback (`OCRSPACE_API_KEY`) — replaced the single-line `trocr` model.

**Review findings status:** ✅ stale base (rebased onto current `main`), ✅ weak `trocr` fallback (replaced with OCR.space). ⏳ remaining: **one live model-availability check on the preview** with a real key — the only blocker, and it needs the owner to set a key. (🟡 minor: ~70 s worst-case latency if VLM cold then OCR; no per-user vision cost cap beyond `LIMIT_UPLOAD`.)

**To activate (owner picks ONE free path, sets the key on Render):**
- OpenRouter (no HF dependency): `OPENROUTER_API_KEY` (+ optional `OPENROUTER_VISION_MODEL`).
- HF (no new account): enable a free HF Inference Provider on the existing `HF_TOKEN`.
- OCR-only fallback: `OCRSPACE_API_KEY` (free key).

Then one live availability check, then it can be marked ready/merged. Tests (mocked HTTP, no quota): `tests/unit/test_image_extractor.py`, `tests/unit/test_upload_image_vision.py`. Keep #736 separate from #737/#738.

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

## Recommended next command

```text
Rico mode. #736 (image reading) is LIVE on production (a7e294b) with the owner's key set. Pending: owner uploads a real job-screenshot in /command and confirms Rico reads it ("I read your image …" + action buttons). If it still shows plain "Image", tune the key/model (OPENROUTER_VISION_MODEL or enable an HF Inference Provider) — graceful, no breakage. Then attachment/document-routing audit Findings 3–5 remain open: application-evidence destination, onboarding/upload surfaces honoring status="classified", dead CV_THRESHOLD + stale CLAUDE.md /chat note.
```
