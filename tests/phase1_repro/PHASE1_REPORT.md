# Phase 1 Reproduction Report: CV Upload Pipeline Reliability

**Branch:** `audit/cv-ingestion-recovery`  
**Baseline SHA:** `1285532837d6e421002c25431861ec61ce7f3866` (verified origin/main)  
**Worktree:** `X:\rico-worktrees\cv-ingestion-recovery`  
**Date:** 2026-07-17  
**Role:** WRITER (audit only — no code changes, no PRs)  
**Production SHAs:** UNKNOWN (not independently verified)

---

## 1. Open Issue Ownership

No single open issue owns this exact defect. Related open issues:

- **#1083** (P1): My Files storage/deletion mismatch — covers persistence and deletion truth boundaries, but not parser failure → garbage profile.
- **#953** (P1 deferred): Chat must not invent CV inventory — covers AI hallucination of document state, not pipeline data integrity.
- **#960** (P2, reopened): Safe logical CV version handling — covers dedup/versioning, not parser reliability.
- **#962** (P2): Login return path — unrelated.
- **#147**: Engineering guardrails — umbrella, not defect-specific.

**Conclusion:** The parser-failure → garbage-profile path is not tracked by any existing open issue. A new issue may be warranted after owner review.

---

## 2. Reproduction Environment

- **Python:** 3.12.10
- **PyMuPDF (fitz):** 1.28.0
- **python-docx:** 1.2.0
- **DATABASE_URL:** Not set (no live DB)
- **Method:** Direct pipeline component execution (detect_format → classify_document → CVParser.parse_bytes → route decision trace). No HTTP server, no database writes.
- **Fixtures:** All synthetic, no PII. Generated in-memory with PyMuPDF.
- **Scripts:** `tests/phase1_repro/run_repro.py`, `tests/phase1_repro/run_supplemental.py`
- **Results JSON:** `tests/phase1_repro/repro_results.json`

### Limitations

- Full HTTP flow (upload → preview → confirm → My Files → logout/login → duplicate → picker reuse) requires a running server with database. Not executed due to no DATABASE_URL.
- The route decision trace is a static analysis of the upload route's branching logic, not a live HTTP test.
- Frontend behavior (file picker reset, error display) not tested — requires running frontend.
- The confirm-cv-profile endpoint's DB writes (get_or_create_user_document, upsert_profile) not executed — requires database.

---

## 3. Reproduction Matrix

| Fixture | Size | detect_format | Classification | Quality | Route | Artifact? | Active CV? | Profile? |
|---|---|---|---|---|---|---|---|---|
| valid_multipage_cv.pdf | 3,916 | pdf | cv (0.02) | partial | PREVIEW_READY | Yes | **Yes** | Yes |
| VALID_MULTIPAGE_CV.PDF | 3,916 | pdf | cv (0.02) | partial | PREVIEW_READY | Yes | **Yes** | Yes |
| empty.pdf (518 B) | 518 | pdf | unknown (0.0) | poor | PREVIEW_READY | Yes | No* | **Yes** |
| scanned_image_only.pdf (668 B) | 668 | pdf | unknown (0.0) | poor | PREVIEW_READY | Yes | No* | **Yes** |
| large_scanned_pdf.pdf (3,355 B) | 3,355 | pdf | no_text (0.9) | poor | CLASSIFIED_no_text | No | No | No |
| large_empty_pdf.pdf (1,158 B) | 1,158 | pdf | no_text (0.9) | poor | CLASSIFIED_no_text | No | No | No |
| corrupt_renamed.pdf | 4,000 | text | unknown (0.0) | good | PREVIEW_READY | Yes | No* | **Yes** |
| garbage_pdf.pdf | 543 | pdf | unknown (0.0) | partial | PREVIEW_READY | Yes | No* | **Yes** |
| non_cv_invoice.pdf | 1,616 | pdf | invoice (0.117) | poor | CLASSIFIED_non_cv | No | No | No |
| oversized.pdf (26 MB) | 27,262,976 | pdf | unknown (0.0) | poor | **REJECT 413** | No | No | No |
| valid_pdf_octet_stream.bin | 3,916 | pdf | cv (0.02) | good | PREVIEW_READY | Yes | **Yes** | Yes |

\* = doc_type "unknown" resolves to "other" in confirm, so is_primary=False. Profile is still updated.

---

## 4. Critical Hypothesis: Can Parser Failure/Garbage Produce Active CV + Profile Data?

### Hypothesis H1: Parser failure/garbage can produce `status=preview_ready`

**CONFIRMED.** Three distinct paths produce preview_ready from garbage/empty input:

1. **Corrupt PDF with PyMuPDF failure** (`garbage_pdf.pdf`): PyMuPDF fails to open the stream. The parser falls back to `data.decode("utf-8", errors="ignore")` at `@X:\rico-worktrees\cv-ingestion-recovery\src\cv_parser.py:339-340`. This produces 543 bytes of raw PDF binary decoded as UTF-8 — 92% non-printable garbage (printable_ratio=0.079). The pipeline treats this as valid text with "partial" quality (543 > 300). Route returns preview_ready.

2. **Non-PDF file renamed to .pdf** (`corrupt_renamed.pdf`): No `%PDF` magic bytes. `detect_format` falls back to extension-based detection, returns "text" (not "pdf"). `CVParser.parse_bytes` at `@X:\rico-worktrees\cv-ingestion-recovery\src\cv_parser.py:211-212` decodes the raw bytes as UTF-8. 3,999 chars of garbage text. Quality = "good" (3,999 > 1,000). Route returns preview_ready.

3. **Small empty/scanned PDFs < 1024 bytes** (`empty.pdf` 518 B, `scanned_image_only.pdf` 668 B): The no_text guard at `@X:\rico-worktrees\cv-ingestion-recovery\src\api\routers\rico_chat.py:1626` requires `len(data) >= _NO_TEXT_MIN_BYTES (1024)`. Small PDFs bypass this guard. The classifier returns "unknown" with 0 confidence and 0 chars, but the guard's second condition (`doc_type == "unknown" and confidence <= 0.0 and extracted_chars < 25`) only triggers when `len(data) >= 1024`. Route returns preview_ready with "poor" quality.

### Hypothesis H2: Preview_ready leads to artifact creation

**CONFIRMED.** The upload route creates a `cv_upload_artifact` for any authenticated user when status=preview_ready (`@X:\rico-worktrees\cv-ingestion-recovery\src\api\routers\rico_chat.py:1821-1829`). The artifact stores the garbage/empty `cv_text` from the parser.

### Hypothesis H3: Artifact allows confirm to proceed

**CONFIRMED.** The confirm endpoint resolves the artifact via `_resolve_trusted_cv_artifact` (`@X:\rico-worktrees\cv-ingestion-recovery\src\api\routers\rico_chat.py:1863-1891`). As long as the artifact exists, is unexpired, scoped to the user, and the filename matches, confirm proceeds. There is no quality gate on the artifact's cv_text.

### Hypothesis H4: Confirm writes profile data from garbage

**CONFIRMED.** The confirm endpoint at `@X:\rico-worktrees\cv-ingestion-recovery\src\api\routers\rico_chat.py:1936-1949` writes `profile_updates` including:
- `cv_filename`: the garbage filename
- `cv_status`: "parsed"
- `cv_extracted_at`: current timestamp
- `skills`: empty list (from garbage parse)
- `name`: None
- `current_role`: None
- `years_experience`: None
- `target_roles`: None
- `certifications`: empty list
- `languages`: empty list
- `profile_creation_mode`: "cv_first"
- `manual_profile_wizard_disabled`: True

This is written to `rico_profiles` via `upsert_profile` with `require_db=True`. The profile is corrupted with a "parsed" CV status and empty/garbage fields.

### Hypothesis H5: Confirm creates an active CV (is_primary=True) from garbage

**NOT CONFIRMED for garbage/unknown types.** In confirm at `@X:\rico-worktrees\cv-ingestion-recovery\src\api\routers\rico_chat.py:2039-2056`:
- `_resolved_doc_type` = artifact["doc_type"] if in ("cv", "cover_letter", "other") else "other"
- For garbage/empty/corrupt files, classification returns doc_type="unknown"
- "unknown" is NOT in _CONFIRMABLE_DOC_TYPES, so _resolved_doc_type = "other"
- `is_primary = (_resolved_doc_type == "cv")` = False
- A user_document row IS created (type="other", is_primary=False), but it is NOT the active CV

**However:** If a file is classified as "cv" but contains garbage text (e.g., a crafted file with CV keywords but corrupt content), an active CV WOULD be created with garbage data. This is a theoretical risk — the reproduction matrix did not produce this case naturally.

### Hypothesis H6: The no_text guard protects against empty/scanned PDFs

**PARTIALLY CONFIRMED.** The guard works correctly for PDFs ≥ 1024 bytes:
- `large_scanned_pdf.pdf` (3,355 B) → CLASSIFIED_no_text ✓
- `large_empty_pdf.pdf` (1,158 B) → CLASSIFIED_no_text ✓

**But fails for PDFs < 1024 bytes:**
- `empty.pdf` (518 B) → PREVIEW_READY_poor ✗
- `scanned_image_only.pdf` (668 B) → PREVIEW_READY_poor ✗

The 1024-byte threshold at `@X:\rico-worktrees\cv-ingestion-recovery\src\api\routers\rico_chat.py:1623` (`_NO_TEXT_MIN_BYTES = 1024`) is the root cause. Small empty PDFs bypass the guard and enter the CV pipeline.

---

## 5. Additional Findings

### F1: Uppercase .PDF extension works correctly

`VALID_MULTIPAGE_CV.PDF` → detect_format returns "pdf" (magic bytes checked first, extension lowercased). Full pipeline works identically to lowercase. **PASS.**

### F2: MIME mismatch (octet-stream) works correctly

`valid_pdf_octet_stream.bin` → detect_format returns "pdf" (magic bytes `%PDF` override the `.bin` extension). Full pipeline works. **PASS.**

### F3: Multi-page PDF parsing extracts all pages

Valid 3-page PDF: all 3 pages extracted, 483 chars total, no page loss. Skills correctly detected: `['hse', 'safety', 'risk assessment', 'iso 45001', 'audit']`. **PASS.**

### F4: Non-CV PDFs correctly rejected

`non_cv_invoice.pdf` → classified as "invoice", routed to CLASSIFIED_non_cv. No artifact, no confirm, no profile update. **PASS.**

### F5: Oversized files rejected by route

The route checks `declared_size > _MAX_UPLOAD_BYTES` at line 1420 and `len(data) > size_limit` at line 1447. A 26MB PDF would get 413 before reaching classification. **PASS** (verified by code trace, not by live HTTP test).

### F6: Parser UTF-8 fallback is the primary garbage injection vector

`@X:\rico-worktrees\cv-ingestion-recovery\src\cv_parser.py:338-340`:
```python
except Exception as exc:
    logger.warning("cv_parser: PyMuPDF failed, falling back to raw UTF-8 decode: %s", exc)
    return data.decode("utf-8", errors="ignore")
```

This fallback returns raw binary bytes decoded as UTF-8 with errors ignored. For a corrupt PDF, this produces mostly non-printable garbage that flows through the entire pipeline without any readability check. The quality metric (`@X:\rico-worktrees\cv-ingestion-recovery\src\cv_parser.py:229-234`) is based solely on character count, not on whether the text is actually readable.

### F7: Non-PDF files renamed to .pdf bypass PDF parsing entirely

`detect_format` at `@X:\rico-worktrees\cv-ingestion-recovery\src\services\document_classifier.py` checks magic bytes first. If no known magic bytes match, it falls back to extension-based detection. A `.pdf` extension with no `%PDF` magic returns "text" (not "pdf"). The parser then decodes the raw bytes as UTF-8 at `@X:\rico-worktrees\cv-ingestion-recovery\src\cv_parser.py:211-212`. This means any text file renamed to .pdf goes through the CV pipeline as "text" format.

### F8: Phone regex extracts PDF metadata as phone numbers

For `valid_pdf_octet_stream.bin`, the parser extracted phone numbers like `['0 0 595 842', '0 25 0000000000 65535', ...]` — these are PDF coordinate metadata, not real phone numbers. The phone regex `(?:\+?\d[\d\s().-]{7,}\d)` at `@X:\rico-worktrees\cv-ingestion-recovery\src\cv_parser.py:221` matches numeric sequences in PDF internal data. This is a parser quality issue, not a data integrity risk (phones are not persisted to profile per the security comment at line 1929-1935).

---

## 6. Root Cause Analysis

### Primary root cause: No readability/quality gate between parser and preview_ready

The upload route has a no_text guard and a classification gate, but no check on the **quality of the parser's output**. Once the parser returns any text (including garbage from UTF-8 fallback), the pipeline proceeds to preview_ready as long as:
1. The file format is text-bearing (pdf/doc/docx/text)
2. The classification doc_type is in {"cv", "cover_letter", "unknown"}
3. The no_text guard doesn't trigger (which has a size threshold bug)

### Contributing factors:

1. **`_NO_TEXT_MIN_BYTES = 1024` threshold** (`rico_chat.py:1623`): Small empty/scanned PDFs bypass the no_text guard.
2. **Parser UTF-8 fallback** (`cv_parser.py:339-340`): Returns raw binary as text without any printable-ratio check.
3. **Quality metric based on char count only** (`cv_parser.py:229-234`): 300+ chars of garbage = "partial" or "good" quality.
4. **No confirm-side quality gate**: The confirm endpoint validates the artifact's existence, scope, filename, and hash — but never checks whether the cv_text is actually readable content.

---

## 7. Impact Assessment

| Scenario | User Impact | Data Impact | Severity |
|---|---|---|---|
| Corrupt PDF → preview_ready → confirm | User sees "preview" with garbage, can confirm | Profile written with cv_status="parsed", empty fields, garbage cv_filename | **High** |
| Empty PDF < 1024 B → preview_ready → confirm | User sees empty preview, can confirm | Profile written with cv_status="parsed", all fields empty | **High** |
| Non-PDF renamed to .pdf → preview_ready → confirm | User sees garbage text as "CV", can confirm | Profile written with garbage text as cv_text | **High** |
| Scanned PDF < 1024 B → preview_ready → confirm | User sees empty preview, can confirm | Profile written with empty cv_text | **Medium** |
| Scanned PDF ≥ 1024 B → CLASSIFIED_no_text | User told file is unreadable | No writes | **None (correct)** |
| Valid CV → preview_ready → confirm | User sees correct preview | Profile written correctly | **None (correct)** |

### Affected scope: All users

The fix must be global and user-agnostic. Any user uploading a corrupt, empty, or renamed file hits these paths. No owner-account special-casing.

---

## 8. Test Coverage Gaps

1. **No test for corrupt PDF with PyMuPDF failure** — the UTF-8 fallback path is not tested.
2. **No test for non-PDF file renamed to .pdf** — the detect_format → "text" → parser UTF-8 path is not tested.
3. **No test for empty/scanned PDF < 1024 bytes** — the no_text guard's size threshold is not tested at the boundary.
4. **No test for printable-ratio / garbage detection** — no such check exists in the codebase.
5. **No test for confirm with garbage cv_text** — the confirm endpoint has no quality gate.
6. **No end-to-end test for parser failure → profile corruption** — the full upload → confirm → profile state is not tested with garbage input.
7. **No test for multi-page page loss** — only tested with 3 pages, all extracted. No test for large page counts or complex layouts.

---

## 9. Proposed Smallest Safe Fixes (for owner approval — NOT implemented)

### Fix A: Remove the `_NO_TEXT_MIN_BYTES` threshold (1 line change)

`@X:\rico-worktrees\cv-ingestion-recovery\src\api\routers\rico_chat.py:1623`:
Change `_NO_TEXT_MIN_BYTES = 1024` to `_NO_TEXT_MIN_BYTES = 0` or remove the `len(data) >= _NO_TEXT_MIN_BYTES` condition.

**Risk:** Very low. The guard already checks `doc_type == "no_text"` or `(doc_type == "unknown" and confidence <= 0.0 and extracted_chars < 25)`. Removing the size threshold only extends protection to small files.

### Fix B: Add printable-ratio check in the parser fallback (3-5 lines)

`@X:\rico-worktrees\cv-ingestion-recovery\src\cv_parser.py:338-340`:
After the UTF-8 fallback, check if the decoded text has a printable ratio below a threshold (e.g., 0.5). If so, return empty string instead of garbage. This causes the pipeline to treat it as no_text/poor quality.

**Risk:** Low. Only affects corrupt PDFs that PyMuPDF can't parse. Legitimate PDFs that PyMuPDF can parse are unaffected.

### Fix C: Add quality gate in the upload route after parsing (5-10 lines)

`@X:\rico-worktrees\cv-ingestion-recovery\src\api\routers\rico_chat.py:~1723` (after `parsed = ...`):
Check if `parsed.text` is empty or has a very low printable ratio. If so, return a "no_text" or "error" response instead of preview_ready.

**Risk:** Low-medium. Could affect edge cases where a legitimate CV has very little extractable text. Should be combined with a clear user message.

### Fix D: Add quality gate in the confirm endpoint (3-5 lines)

`@X:\rico-worktrees\cv-ingestion-recovery\src\api\routers\rico_chat.py:~1998` (after `confirmed_cv_text` is resolved):
Check if `confirmed_cv_text` is empty or garbage. If so, reject the confirm.

**Risk:** Low. Only affects confirms with garbage/empty cv_text, which should never be confirmed.

### Recommended combination: Fix A + Fix B

Fix A closes the small-file bypass. Fix B closes the corrupt-PDF garbage fallback. Together they prevent all three garbage-injection paths identified in H1. Fix C and D are defense-in-depth additions for owner consideration.

---

## 10. Risks and Rollback

- **No code changes made.** All fixes are proposals for owner approval.
- **No database migrations required.**
- **No production writes.** All testing was in-memory with synthetic fixtures.
- **Rollback:** N/A (no changes to roll back). If fixes are implemented, each is a single-file change that can be reverted independently.

---

## 11. Unverified Items

1. **Full HTTP flow** (upload → preview → confirm → My Files → logout/login → duplicate → picker reuse): Not tested due to no DATABASE_URL. Requires running server with database.
2. **Frontend file picker reset after failure**: Not tested. Requires running frontend.
3. **Duplicate upload deduplication**: Not tested. Requires database for `get_or_create_user_document` with content_hash.
4. **Logout/login persistence**: Not tested. Requires database and auth flow.
5. **Production frontend/backend SHAs**: Not independently verified. Marked as UNKNOWN.
6. **Confirm endpoint DB writes**: Not tested. Requires database.
7. **Artifact TTL and opportunistic purging**: Not tested. Requires database.

---

## 12. Related Closed Issues

- **#960** (closed, reopened P2): CV dedup — Stage 1 (exact-byte dedup) is complete. Stage 2 (logical versioning) is deferred. Does not own this defect.
- **#963** (closed): Onboarding persistence — fixed the artifact-based confirm flow. Does not address parser quality gates.

---

## 13. Recommendation

**Stop here for owner approval.** Do not implement fixes until the owner reviews this report and approves a fix strategy. The recommended next steps are:

1. Owner reviews this report and approves Fix A + Fix B (or alternative).
2. Create a focused PR with the approved fixes + regression tests.
3. Run focused tests (`pytest tests/test_cv_parser.py`, `pytest tests/test_upload*.py`).
4. Verify with a running server + database if available.
5. No merge or deploy without explicit owner approval.
