## Scope

P0 data-integrity fix for CV upload reliability. Prevents unreadable, corrupt, misidentified, or textless CV uploads from reaching `preview_ready` and corrupting canonical profile state.

## Root Cause

Three paths allowed garbage input to reach `preview_ready`:

1. **PyMuPDF fallback**: When PDF parsing failed, `CVParser._parse_pdf` fell back to `data.decode("utf-8", errors="ignore")`, injecting binary garbage as "text"
2. **Extension-only detection**: Files renamed to `.pdf` were forced through PDF parsing even without `%PDF` magic bytes
3. **Byte-size guard only**: The `no_text` guard relied on file byte size (1024 bytes) rather than extracted text quality

## Before/After Behavior

**Before:**

- Corrupt PDF with PyMuPDF failure → returns `preview_ready` with garbage `cv_text`
- Text file renamed to `.pdf` → returns `preview_ready` with decoded garbage
- Scanned PDF below 1024 bytes → returns `preview_ready` with "poor" quality
- No defense-in-depth in confirm endpoint

**After:**

- Corrupt PDF → returns `parse_failed` (parser exception raised, no fallback)
- Text file renamed to `.pdf` → returns `invalid_signature` (format integrity at upload boundary)
- Scanned PDF → returns `unreadable` (readability gate requires 50+ meaningful chars + 30% printable ratio)
- Confirm endpoint rejects artifacts with unreadable cv_text using shared contract

## Format Contract

- `.pdf` files without `%PDF` magic bytes → `invalid_signature` status
- Valid PDF with uppercase `.PDF` or MIME `application/octet-stream` → accepted
- Format check performed at upload boundary using `detect_format` result

## Parser Outcome Contract

Shared contract in `src/cv_parse_quality.py` with four outcomes:

- `parsed`: Parser succeeded with meaningful content (50+ chars, 30%+ printable)
- `no_text`: No extractable text (scanned, image-only)
- `unreadable`: Text extracted but below meaningful threshold
- `parse_failed`: Parser exception or format error

## Changed Files

- `src/cv_parser.py`:
  - Removed UTF-8 fallback in `_parse_pdf` (raises RuntimeError instead)
  - Added magic byte check in `parse_bytes` before trusting `.pdf` extension
- `src/cv_parse_quality.py` (new):
  - Shared parse-quality contract with conservative validation
  - `validate_parse_quality()` for upload gate
  - `validate_artifact_quality()` for confirmation defense-in-depth
- `src/api/routers/rico_chat.py`:
  - Added format integrity check at upload boundary (reject .pdf without PDF magic bytes)
  - Added readability gate using shared contract before `preview_ready`
  - Added confirmation defense-in-depth using shared contract
  - Implemented truthful response contract (parse_failed, invalid_signature, unreadable)
- `tests/integration/test_cv_parse_quality_gate_postgres.py`:
  - 10-scenario Postgres integration test suite
- `tests/test_cv_profile_extraction.py`:
  - Updated `test_pdf_magic_fallback` to expect RuntimeError (no fallback)
- `tests/test_rico_routes.py`:
  - Updated `_CV_PARSED` mock to include `extracted_chars` and `extraction_quality`

## Tests

**New integration tests (10 scenarios, all passing):**

1. Corrupt PDF → rejected before preview (PASS)
2. Renamed text as PDF → rejected as invalid_signature (PASS)
3. Scanned PDF → rejected by readability gate (PASS)
4. Small textless PDF → rejected by readability gate (PASS)
5. Parser exception → returns parse_failed (PASS)
6. Garbage extraction → rejected by readability gate (PASS)
7. Valid multi-page PDF → preview_ready (PASS)
8. Confirmation defense-in-depth → validates parse-quality contract (PASS)
9. Retry behavior → corrupt fails, valid succeeds (PASS)
10. Duplicate upload → endpoint accepts same bytes (PASS)

**Existing tests (no regressions):**

- `tests/test_upload_document_intelligence.py`: 12/12 passing
- `tests/unit/test_upload_cv_unknown_doc_type.py`: 4/4 passing
- `tests/test_cv_profile_extraction.py`: 45/45 passing
- `tests/test_rico_routes.py`: 6/6 passing (updated mocks)
- Full pytest suite: 3717 passed, 1 xfailed
- Postgres integration: 16/16 passing
- Frontend Vitest: 545/545 passing
- Playwright: 6/6 passed, 9 skipped

## Data-Integrity Proof

The fix ensures:

- No garbage `cv_text` reaches the database
- No artifact created for unreadable inputs
- No profile mutation from unreadable inputs
- No active CV document row from garbage inputs
- Confirm endpoint independently rejects unreadable artifacts
- Format integrity enforced at upload boundary
- Conservative validation using both character count and printable ratio

## Format-Signature Proof

Scenario 2 proves: text file renamed to `.pdf` returns `invalid_signature` with no artifact, no document, no profile mutation.

## Authenticated Data-Integrity Proof

Tests use public session pattern. Full authenticated flow (upload → artifact → confirm → user_documents → rico_profiles) requires authenticated user setup and is deferred to follow-up work. The shared parse-quality contract is tested independently.

## Duplicate/Retry Proof

Scenario 9 proves: corrupt upload fails (parse_failed), retry with valid PDF succeeds (preview_ready).
Scenario 10 proves: upload endpoint accepts same bytes multiple times. Document dedup at user_documents level is tested in `test_user_documents_postgres.py`.

## Risks

- **Low**: Readability gate threshold (50 chars + 30% printable ratio) may reject some valid but very short CVs. Mitigation: threshold is conservative; users can re-upload with more content.
- **Low**: Renamed text files now rejected as `invalid_signature` (correct behavior for format integrity).
- **None**: No schema changes, no migrations, no production data writes.

## Rollback

Revert the 5 changed files. The previous behavior was a data-integrity bug, so rollback is not recommended.

## Unverified Items

- Production smoke testing (not performed per rules)
- Authenticated user artifact creation flow (tests use public session pattern)
- Full upload → artifact → confirm → user_documents → rico_profiles flow (requires authenticated user setup)

## Recommendation

Merge after review. The fix is minimal, scoped, and proven by integration tests. All CI gates pass.
