## P0 candidate: unreadable CV parsing can reach preview and corrupt profile state

An unreadable, corrupt, misidentified, or textless CV upload can reach `preview_ready` and may overwrite canonical profile state as though parsing succeeded.

## Status

P0-candidate data-integrity defect. Component-level reproduction is confirmed. Real-Postgres end-to-end reproduction is still required.

## Component-level reproduction (confirmed)

Verified on `main` SHA `1285532837d6e421002c25431861ec61ce7f3866` using synthetic fixtures (no PII).

### Three confirmed paths to `preview_ready` from garbage input

1. **Corrupt PDF with PyMuPDF failure** — `CVParser._parse_pdf` catches the PyMuPDF exception and falls back to `data.decode("utf-8", errors="ignore")` (`src/cv_parser.py:339-340`). This returns raw binary bytes decoded as UTF-8 — 92% non-printable garbage (printable_ratio=0.079). The pipeline treats this as valid text with "partial" quality. Route returns `preview_ready`.

2. **Non-PDF file renamed to .pdf** — No `%PDF` magic bytes. `detect_format` falls back to extension-based detection, returns `"text"`. `CVParser.parse_bytes` decodes raw bytes as UTF-8 (`src/cv_parser.py:211-212`). 3,999 chars of garbage text. Quality = "good". Route returns `preview_ready`.

3. **Small empty/scanned PDF below 1024 bytes** — The no_text guard at `src/api/routers/rico_chat.py:1623` requires `len(data) >= _NO_TEXT_MIN_BYTES (1024)`. Small PDFs (e.g. 518-byte empty PDF, 668-byte scanned PDF) bypass this guard. Route returns `preview_ready` with "poor" quality.

### What happens after `preview_ready`

- An upload artifact is created for authenticated users (`rico_chat.py:1821-1829`), storing the garbage/empty `cv_text`.
- The confirm endpoint resolves the artifact (`rico_chat.py:1863-1891`) and proceeds — there is no quality gate on the artifact's `cv_text`.
- The confirm endpoint writes to `rico_profiles`: `cv_status="parsed"`, `cv_filename` set, `manual_profile_wizard_disabled=True`, plus empty/garbage fields (`rico_chat.py:1936-1949`).

### No active CV document row was proven for garbage inputs

For garbage/empty/corrupt files, classification returns `doc_type="unknown"`. In confirm, `"unknown"` is not in `_CONFIRMABLE_DOC_TYPES = ("cv", "cover_letter", "other")`, so `_resolved_doc_type = "other"` and `is_primary = False`. A `user_document` row IS created (type="other", is_primary=False), but it is NOT the active CV.

**Canonical profile corruption is the primary risk**, not active-CV creation.

## What works correctly

- Valid multi-page PDFs: all pages extracted, skills detected, `preview_ready` with correct preview. PASS.
- Uppercase `.PDF` extension: magic bytes checked first, extension lowercased. PASS.
- MIME mismatch (`application/octet-stream` with `.bin` extension): magic bytes override extension. PASS.
- Non-CV PDFs (invoice): classified as `"invoice"`, routed to `CLASSIFIED_non_cv`. No artifact, no confirm. PASS.
- Oversized files: rejected with 413 before classification. PASS.
- Large scanned/empty PDFs >= 1024 bytes: `no_text` guard triggers, `CLASSIFIED_no_text` response. PASS.

## Related issues (separate, not duplicates)

- **#1083** — My Files storage/deletion architecture. Separate: covers persistence and deletion truth boundaries.
- **#953** — Chat CV inventory hallucination. Separate: covers AI hallucination of document state.
- **#960** — Safe logical CV version handling. Separate: covers dedup/versioning.

## Scope

- No migration or object-storage decision is included.
- No database schema changes.
- No production data writes.
- Fix is scoped to: parser fallback behavior, readability gate, artifact integrity, confirm defense-in-depth, and truthful API responses.

## Required fix contract

1. **Format integrity**: A filename ending in `.pdf` must not force PDF treatment when bytes are not PDF.
2. **Parser failure**: PyMuPDF exception must NOT fall back to decoding raw PDF bytes as UTF-8. Return structured parse failure.
3. **Readability gate**: After successful PDF extraction, require meaningful readable text before `preview_ready`, artifact creation, or profile confirmation. Must not rely on file byte size alone.
4. **Artifact integrity**: Create artifact only when parsing reached an approved successful state. Preserve explicit parser outcome (parsed/no_text/unreadable/parse_failed).
5. **Confirmation defense-in-depth**: Confirm endpoint must independently reject any artifact not in an approved parsed state.
6. **Truthful API/UI result**: Distinguish invalid file signature, unreadable/corrupt PDF, scanned PDF requiring OCR, no readable text, oversized file, and parser failure.

## Roadmap mapping

Phase 2 — Hardening. Epic: Career Operating System. Milestone: Operational Memory.
