# Handoff — Attachment / Document Intelligence routing (2026-06-23)

## Task

Stop screenshots / application-evidence uploads from being mis-handled as CVs, and decide the
follow-up vision work. Delivered the routing-safety fix (#737, merged + live) and reviewed the
HF vision extension (#736, not merged).

## Context

- Repository: Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE
- Production main HEAD: `e214178` (#737), deploy-verified.
- Audit: `AI_WORKSPACE/AUDITS/attachment-document-routing-post-674-677.md` (Findings 1–5).
- Origin: issue #674 (CAREER-OS-06 Universal Document Intelligence) + #677 (classify half shipped).
- Relevant files: `src/services/document_classifier.py`, `src/api/routers/rico_chat.py`
  (`/upload-cv`), `src/services/image_extractor.py` (#736 only).

## What shipped — #737 (merged, `e214178`)

- **Bug (Finding 1):** a screenshot/scan exported as a PDF (image-only PDF, no text layer) scored
  `unknown@0.0` and was routed into CV extraction → misleading "extraction quality: poor" CV
  preview. Native images were already handled by #677; the image-as-PDF case was the residual.
- **Fix:** classifier tags a *substantial* text-bearing file (`len(data) >= _MIN_DOC_BYTES`, 1 KB)
  with near-empty extracted text (`< _MIN_TEXT_CHARS`, 25) as `no_text`. `/upload-cv` returns a
  needs-text response (`status="classified"`, `document_type="no_text"`) before the CV pipeline.
  The byte-size gate keeps tiny stub PDFs (route/security test fixtures) flowing normally.
- **Unchanged:** real text CVs → `preview_ready`; native images → `classified`/`image`;
  cover letters → unchanged. No OCR, no HF, no frontend, no auth/billing.
- **Tests:** `tests/test_no_text_pdf_routing.py` (classifier + router, mocks only).

## What was reviewed — #736 (NOT merged)

`feat/vision-image-extraction` (`40266cd`, Draft) — read job-screenshot images via a Hugging Face
vision model (`HF_VISION_MODEL`, default `Qwen/Qwen2.5-VL-7B-Instruct`) with a serverless OCR
fallback (`HF_OCR_MODEL`). HF only, no OpenAI. Implements audit Finding 2.

Verdict: well-tested, correctly scoped (backend-only), safe-by-design (never blocks uploads, never
logs token or transcript content, timeout 35s, 6 MB cap, max_tokens 800). **Blocking findings
before any merge:**

1. 🔴 Stale base — green CI ran on `96f415a` (pre-#737); both PRs edit the `/upload-cv`
   image/classification region. Rebase onto `e214178` and re-run.
2. 🟠 Default OCR fallback `microsoft/trocr-base-printed` is single-line — unsuitable for multi-line
   screenshots. Replace or disable by default.
3. 🟠 Confirm `Qwen/Qwen2.5-VL-7B-Instruct` is enabled on the production `HF_TOKEN` via one live
   availability call on the preview before merge (feature silently degrades if absent).
4. 🟡 ~70s worst-case latency (2× 35s HF calls); no hard per-user vision cost cap (only
   `LIMIT_UPLOAD`).

## Constraints (respected)

- Out of scope: OCR/HF (for #737), frontend, auth, billing, job search, application lifecycle,
  `src/services/image_extractor.py` (for #737), PR #736.
- #737 and #736 kept strictly separate.
- Tests mocks-only; no live HF/provider calls.

## Acceptance Criteria

- [x] Image-only PDF (empty text layer) → not CV.
- [x] Empty/no-text PDF → no CV preview.
- [x] `unknown`/near-empty → classified needs-text response.
- [x] Real text CV PDF → `preview_ready`.
- [x] Native image unchanged.
- [x] No OCR / HF / frontend / auth / billing in #737.
- [x] CI green; deploy-verified at `/version == e214178`, `/health == 200`.

## Verification

```bash
pytest tests/test_no_text_pdf_routing.py
pytest tests/test_rico_routes.py tests/test_upload_document_intelligence.py \
       src/tests/test_document_classifier.py tests/unit/test_upload_cv_unknown_doc_type.py \
       tests/unit/test_p1_cv_pipeline_safety.py::test_cv_upload_runs_parser_in_executor
# Deploy: GitHub Actions "Deploy Render Backend" → /version e214178, /health 200
```

## Risks / Rollback

- #737 risk: a scanned image-only *CV* (no text layer) now returns needs-text instead of a (poor)
  CV preview — intended; user is told to upload a text-based version. Rollback = revert `e214178`.
- `_MIN_DOC_BYTES = 1024` / `_MIN_TEXT_CHARS = 25` are the only tuning knobs.

## Reviewer Notes

- Scope respected: yes (#737 4 files within allowed set; #736 not touched).
- Follow-up tasks: audit Findings 3–5 (application-evidence destination, onboarding/upload surfaces
  honoring `status="classified"`, dead `CV_THRESHOLD` + stale `CLAUDE.md` `/chat` note) remain
  unscheduled.

---

## Update — 2026-06-23 (later)

### #738 — upload size limits (merged + deploy-verified, `115adde`)
New production bug: valid CV PDFs (images/design) rejected with the misleading "Could not process your
CV … under 10 MB". Fix: per-kind caps from the magic-byte format **before** parsing — documents 25 MB,
images 10 MB, hard cap retained; coarse pre-read guard; 413 with a friendly type-aware message (never
CV-blaming / never "retry"). Frontend: new `cmdCvTooLarge` (AR + EN), de-sized `cmdCvUploadErr`,
onboarding hint 25 MB, and `/command` + `/onboarding` map 413 → localized message. `files.py` doc cap
also 25 MB. Files: `src/api/routers/rico_chat.py`, `files.py`, `apps/web/lib/translations.ts`,
`apps/web/app/command/page.tsx`, `apps/web/app/onboarding/page.tsx`, `tests/test_upload_size_limits.py`,
`apps/web/__tests__/cv-upload-size-message.test.ts`. Deploy verified (`/version == 115adde`, `/health`
200).

### #736 — image reading reworked (Draft, parked, `b70389b`)
Decision taken to close it on free infra: VLM via OpenAI-compatible chat is now provider-agnostic —
**OpenRouter** (`OPENROUTER_API_KEY`, free `:free` models) preferred → HF-independent, else **HF**
(`HF_TOKEN`, Qwen2.5-VL); the weak single-line `trocr` fallback was **replaced with OCR.space**
(`OCRSPACE_API_KEY`). Rebased onto current `main`; 16 mocked tests pass; never blocks uploads. Two of
three review findings now resolved in code (stale base, weak fallback). **Only blocker: one live
model-availability check on the preview with a real key — owner must set ONE free key on Render
(OPENROUTER_API_KEY / enable a free HF Inference Provider / OCRSPACE_API_KEY).** Then verify + mark
ready + merge. Keep separate from #737/#738; no live probes until a key is set.
