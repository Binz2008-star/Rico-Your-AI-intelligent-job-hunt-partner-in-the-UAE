# Audit — Attachment / Document Routing (post #674 / #677)

**Date:** 2026-06-23
**Author:** Rico AI agent session (branch `fix/no-text-pdf-avoid-cv-pipeline`)
**Status:** Audit + scoped routing-safety fix (Finding 1 only)
**Separate from:** PR #736 (`feat/vision-image-extraction` — HF vision / native screenshot OCR). This
session does **not** touch `src/services/image_extractor.py`, HF vision logic, `HF_TOKEN`,
`HF_VISION_MODEL`, the frontend, auth, billing, job search, or application lifecycle.

---

## Context

Issue #674 (CAREER-OS-06 — Universal Document Intelligence) required that every uploaded file be
classified **before** any pipeline runs, so Rico never assumes an upload is a CV. The target document
table explicitly listed **"Screenshot / Image → OCR + classify."**

PR #677 (`feat/career-os-06-document-intelligence`, merged 2026-06-20) shipped the **classify** half.

---

## What #677 shipped (confirmed live)

- New byte/content classifier: `src/services/document_classifier.py`
  (`classify_document()` → `ClassificationResult`).
- A classification gate in `POST /api/v1/rico/upload-cv`
  (`src/api/routers/rico_chat.py`, ~lines 1271–1342) that runs before CV extraction.
- **Native image files** (PNG/JPEG/WebP/GIF/BMP, detected by magic bytes) → `status="classified"`,
  returned immediately and **never** enter the CV pipeline (`rico_chat.py:1292-1295`).
- The live chat surface `/command` (`apps/web/app/chat/page.tsx` redirects to `/command`) renders the
  classified response with suggested-action buttons (`apps/web/app/command/page.tsx:1135-1155`).

So for a **native image** uploaded on `/command`, the original "treated as CV" symptom is genuinely
fixed.

---

## Findings

### Finding 1 — PRIMARY (this session's fix): screenshot-as-PDF / image-only PDF still enters the CV pipeline
The most common way users "show evidence" is a screenshot **exported / saved as a PDF** (an image-only
PDF with no text layer). Reproduced:

```
input: image-only PDF  →  format=pdf, doc_type=unknown, confidence=0.0
unknown ∈ {cv, cover_letter, unknown}  →  TRUE  →  enters CV extraction → "quality poor" → CV preview
```

- `_CV_PIPELINE_TYPES = {"cv","cover_letter","unknown"}` (`rico_chat.py:1317`) routes `unknown` into
  CV extraction.
- An image-only / no-text PDF yields no extractable text (`document_classifier._extract_pdf` reads the
  PDF text layer only — **no OCR**) → every signal scores 0 → `unknown@0.0`
  (`document_classifier.py:380-383`).
- Net: this is **issue #674's exact reproduction, still live** for the image-PDF case.

### Finding 2 — Classified images are not ingested / read (the "OCR" half of #674 was never built)
Even when a native image is correctly classified, its content is dropped:
- `last_uploaded_document` persists only metadata (type/label/filename/confidence/actions), **not bytes
  or OCR text** (`rico_chat.py:1332-1339`).
- The image actions "Extract text (OCR)" / "Describe this image"
  (`document_classifier.py:246-251`) are dead-ends — **no OCR/vision pipeline exists** in `src/`.
- Follow-up chat turns route through the normal AI pipeline with no image attached
  (`rico_chat_api.py:9811-9840`).

> **NOTE:** Finding 2 (native image OCR/vision ingestion) is the subject of **PR #736**
> (`feat/vision-image-extraction`). It is explicitly **out of scope** for this session.

### Finding 3 — No "application evidence" destination
#674 framed screenshots as career *evidence*. The image action vocabulary is only Describe/OCR — there
is no "attach to application", "log as application evidence", or "save to workspace". Even with OCR,
there is no destination tying evidence to an application record. **Out of scope here.**

### Finding 4 — Only `/command` was updated; other upload surfaces mishandle `status="classified"`
- `apps/web/app/onboarding/page.tsx:198` hard-gates `file.type !== "application/pdf"` (a screenshot is
  rejected "PDF only") and ignores `res.status`, treating any result as a CV preview (`:205-214`).
- `apps/web/app/upload/page.tsx:370-382` with `docType='cv'`: a classified image returns `ok:true`, so
  the page calls `setIsProcessing(true)` → shows CV-processing UI for an image.

Frontend cleanup — **out of scope here** (frontend is explicitly off-limits this session).

### Finding 5 — Dead/duplicate threshold + stale doc
- `DocumentClassifier.CV_THRESHOLD = 0.50` (`document_classifier.py:298`) is **unused**; the router
  uses its own `confidence >= 0.18 and confidence > cv_score` gate (`rico_chat.py:1319`). Two sources of
  truth.
- `CLAUDE.md` still lists `apps/web/app/chat/page.tsx` as the live public-chat upload surface, but
  `/chat` now redirects to `/command`. Stale.

---

## Recommended sequencing

1. **This session (lowest-risk, highest-value):** stop routing no-text / image-only PDFs and
   `unknown@~0.0` near-empty documents into the CV pipeline → return a classified / needs-text
   response instead. Kills the residual #674 bug (Finding 1).
2. **PR #736 (separate):** native image ingestion via HF vision/OCR (Finding 2).
3. Later: application-evidence action + destination (Finding 3).
4. Later: make `onboarding`/`upload` honor `status="classified"`; remove dead `CV_THRESHOLD`; refresh
   `CLAUDE.md` (Findings 4 & 5).

---

## Scope of the fix in THIS session (branch `fix/no-text-pdf-avoid-cv-pipeline`)

Routing-safety only. Acceptance:

1. Image-only PDF with no extracted text must **not** enter CV extraction.
2. Empty / no-text PDF must **not** show a CV preview.
3. `unknown@0.0` with near-empty extracted text returns a classified / needs-text response.
4. Real text CV PDF still enters CV extraction normally.
5. Cover-letter behavior unchanged when confidently classified.
6. Native image behavior unchanged.
7. No OCR. 8. No HF vision. 9. No application-evidence workflow.

Allowed files: this audit doc, `src/services/document_classifier.py`,
`src/api/routers/rico_chat.py`, and related upload/document-routing tests.
