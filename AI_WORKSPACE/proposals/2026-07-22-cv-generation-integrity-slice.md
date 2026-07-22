# P1 — CV Generation Integrity: Repository Trace + Bounded Vertical Slice

Date: 2026-07-22
Status: evidence + plan (no production code changed in this document's PR)
Branch: `claude/cv-generation-integrity-cgggby`
Incident class: core-product integrity — Rico failed an Arabic tailored-CV request,
asked for data it already held, produced placeholders/unsupported claims, and
revealed that non-active CV documents retain only metadata.

Product rule applied: the smoke/production transcript exposed the bug, but the fix
is global — every finding below is a system behavior affecting all users, not one
account.

---

## Part 1 — Read-only repository trace (evidence)

### E1. Stored CVs do NOT retain retrievable extracted content (metadata-only)

- `user_documents` DDL has **no text/content column** — only filename, doc_type,
  file_size, label, is_primary, skills_count, skills_json, years_experience,
  current_role (`src/rico_db.py:201-220`).
- Full parsed CV text is persisted **only** to `rico_profiles.cv_text` at
  confirm time (`src/api/routers/rico_chat.py:2540-2546` →
  `profile_repo.upsert_profile(..., cv_text=...)`, COALESCE semantics
  `src/repositories/profile_repo.py:253-260`). One slot per profile → each newly
  confirmed CV overwrites it; previous CVs' content is gone.
- The confirm path writes the document row with metadata + skills_json only —
  `get_or_create_user_document(...)` receives no text
  (`src/api/routers/rico_chat.py:2500-2512`).
- `cv_upload_artifacts` (migration 038) does hold full `cv_text`, but is a
  **3-hour-TTL** bridge between upload and confirm — deliberately transient
  (`migrations/038_cv_upload_artifacts.sql`).
- `uploaded_document_context` (migration 032) keeps **one row per user** — only
  the latest transcript survives; a second upload erases the first.
- **My Files direct upload discards content entirely**: `POST /api/v1/user/files`
  validates PDF magic bytes, hashes, stores metadata — the bytes are never parsed
  and never stored (`src/api/routers/files.py:174-268`).
- The product **admits** the limitation in chat copy: "I only keep the full parsed
  content of the **active** CV. … open My Files and make it your active CV — I'll
  re-sync your profile from it" (`src/rico_chat_api.py:2795-2801` Arabic,
  `:2830-2837` English). But `set-primary` can only re-sync
  skills_json/years/current_role from the row — there is no stored text to
  re-sync from (`src/api/routers/files.py:355-373`), so that promise cannot be
  kept for any document whose extraction was never stored.
- My Files product promise: "Manage your CVs, cover letters, and career
  documents" (`apps/web/lib/translations.ts:604-605`, Arabic `:1968-1969`) —
  the UI implies stored, reusable documents; storage is metadata-only.

### E2. `_handle_cv_generate_from_profile` renders a skeleton, not a CV

- `src/rico_chat_api.py:15113-15288`: builds the draft **exclusively** from
  profile scalars — header (name/email/phone/cities), a one-line summary
  (current_role · years · industries), skills (≤12), certifications (≤6),
  target roles (≤4). It reads `work_experience`/`education` lists only to
  report them as "unparsed sections". It **never reads `rico_profiles.cv_text`**
  even though the full source document text is sitting there for the active CV.
- Consequence: it asks the user for "genuinely missing" profile fields
  (`:15152-15170`) that the stored CV text frequently already contains — the
  "asked for already available data" symptom is structural, not a prompt issue.
- The anti-placeholder guard `_CV_PLACEHOLDER_PATTERNS`
  (`src/rico_chat_api.py:452-463`) is **defined but never referenced anywhere
  in the repository** (single grep hit = its definition). The comment claims it
  is "Used as a post-generation guard in _handle_cv_generate_from_profile" —
  it is not. Dead guard.

### E3. Arabic multi-turn continuation into cv.generate has narrow coverage; everything else falls to generic AI fallback

- Intent entry: `_CV_GENERATE_RE` (`src/agent/intelligence/intent_classifier.py:644-659`)
  covers rewrite/refresh/اعملي/اكتبلي/جدد forms → `cv_generate` → deterministic
  handler (`src/rico_chat_api.py:9954-9959`). Good coverage for the *initial* ask.
- Continuation: after a draft, `last_flow_state == "cv_builder"` routes follow-ups
  to the deterministic handler **only** when they match `_CV_IMPROVE_FOLLOWUP_RE`
  ("improve it", "tailor it", "حسنها", "طورها" — `src/rico_chat_api.py:238-255`,
  gate at `:8045-8051`).
- A **role/city-targeted tailoring instruction** — the incident shape, e.g.
  "خصصها لوظيفة عمليات في دبي" / "make it for an Operations role in Dubai" —
  matches neither regex. Routing then proceeds through role classification and
  ends at the final fallback: `_answer_with_ai_fallback`
  (`src/rico_chat_api.py:11779`), a free-generation path with **no placeholder
  guard, no fact reconciliation, and no CV-flow awareness**. This is where
  "asked again for known data" + "invented content" enter.
- The pending-city resolver correctly resumes cv.generate after a city answer
  (`src/rico_chat_api.py:6121-6166`), but rejects any reply containing intent
  verbs (`cv`, `generate`, …) — an Arabic tailoring follow-up while a city is
  pending returns `None` and falls through to the same generic routing.

### E4. The tailoring engine exists but is unverified and placeholder-bearing

- `POST /api/v1/apply/prepare` (`src/api/routers/apply_queue.py:60-100`) and the
  chat `prepare_application` path (`src/rico_chat_api.py:10770-10890`) both use
  `rico_profiles.cv_text` (bundle) and call `tailor_application`.
- `src/rico_apply_ai.py:71-127`: the "never invent experience or dates" rule is
  **prompt-only** — there is no post-generation verification of the AI output
  against the source CV. Temperature 0.4, free text out, stored as-is into
  `application_drafts`.
- The no-AI fallback **emits a literal placeholder**: cover letter signs off
  `"Sincerely,\n[Your Name]"` (`src/rico_apply_ai.py:66`) — a direct violation
  of the no-placeholder invariant, in production code today.
- Success copy "Your tailored CV has been prepared" is emitted after draft
  insert (`src/rico_chat_api.py:10948-10954`) — text draft only; no document
  artifact exists.

### E5. No generated-artifact or download capability exists

- No `FileResponse` and no download route anywhere in `src/` (the only
  `StreamingResponse` uses are chat SSE — `src/api/routers/rico_chat.py`).
- `python-docx` is already a dependency (`requirements.txt:19`) but is used
  read-only (cv_parser, document_classifier). Nothing renders a CV to a file;
  nothing persists a generated document; nothing serves one for download.
- Therefore any chat claim that a tailored CV is "ready" can only ever point at
  chat text or the /applications text draft — the product cannot currently hand
  the user a file.

### E6. Verified-fact reconciliation layer already exists (reuse, don't rebuild)

- `src/services/career_context.py` — the M1 read-path resolver from the
  2026-07-19 incident: provenance-carrying years/name resolution, conflict ⇒
  omit absolutes, degraded ⇒ withhold, name-as-job-title guard. This is the
  designated reconciliation surface; the slice must consume it, not duplicate it
  (owner ruling recorded in the module docstring and
  `AI_WORKSPACE/CAREER_CONTEXT_PROGRAM.md`).
- `src/services/document_resolver.py` — canonical active-CV resolution
  (primary → latest → legacy profile fallback), including strict variants that
  distinguish "store down" from "no documents".
- `src/rico_safety.py` blocks forged-document requests ("forge" trigger, `:38`,
  `:101`) — the slice's reconciliation guard extends the same principle to
  *generated* output.

### E7. Transcript status

The verbatim Arabic production transcript was referenced by the incident report
but is not present in the repository and was not embedded in the task text
available to this session. The regression test (Part 2, step 6) is structured
turn-by-turn against the incident's described shape; the fixture file
`tests/fixtures/arabic_cv_tailoring_transcript.json` must be populated with the
exact supplied transcript by the owner (or pasted into the implementation task)
before the slice merges. No synthetic text may be labeled as the production
transcript.

---

## Part 2 — One bounded vertical slice (single task, single PR)

**Slice:** selected stored CV → verified fact reconciliation → Operations/Dubai
tailored CV → DOCX artifact → authenticated download.

Explicitly out of scope: Cognitive Control Plane, career-context M2 identity
dedupe, cover-letter overhaul, quota/plan changes, any deploy, any second PR.

### Step 1 — Every stored CV retains retrievable extracted content

- Add `extracted_text TEXT` (+ `extracted_at TIMESTAMPTZ`) to `user_documents`
  via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in `_USER_DOCUMENTS_DDL`
  (exact precedent: migration 026 `skills_json`, `src/rico_db.py:220`) plus a
  numbered migration file (`migrations/052_user_documents_extracted_text.sql`)
  kept in sync for `scripts/check_migration_drift.py`. Additive, idempotent,
  no backfill, no unique index — the 038-style runtime-auto-apply justification
  holds.
- Confirm path: pass the artifact's `cv_text` into
  `get_or_create_user_document` so every confirmed CV row keeps its full text.
- My Files direct upload (`files.py`): parse uploaded PDF bytes with the
  existing `CVParser` **via `run_in_executor`** (async-boundary rule in
  CLAUDE.md) and store `extracted_text` on the row. No profile mutation from
  this path.
- `set-primary` re-sync: when the newly activated document has
  `extracted_text`, also restore `rico_profiles.cv_text` from it — making the
  existing "I'll re-sync your profile from it" promise true.
- Honesty for legacy rows: bytes of previously uploaded non-active CVs were
  discarded and are unrecoverable. Rows without `extracted_text` surface
  "content not stored — re-upload to enable tailoring" in the existing
  stored-CV analysis reply instead of the current impossible promise
  (`src/rico_chat_api.py:2795-2801`). The invariant "all stored CVs retain
  retrievable extracted content" is enforced for every write from this slice
  forward; it cannot be retroactively conjured for discarded bytes.

### Step 2 — Fact sheet + reconciliation service (the integrity core)

New `src/services/cv_tailor.py`:

- `build_fact_sheet(user_id, document_id=None)` — resolves the source CV
  (`document_resolver`; explicit `document_id` when the user picked one),
  loads its `extracted_text` (fallback: `rico_profiles.cv_text` only when the
  resolved document is the active CV), and consults
  `career_context.resolve_career_context` for name/years trust. Output: typed
  fact sheet (contact, roles, employers, date ranges, duties, achievements,
  certifications, skills, education) where **every entry carries its source
  span** from the extracted text. Salary, visa status, location, and language
  proficiency are included only if literally present in the source.
- `reconcile(rendered_cv, fact_sheet)` — verification pass over the candidate
  output: every employer, role title, date token, certification, numeric claim,
  salary/visa/proficiency statement must map to a fact-sheet entry
  (normalized match); `_CV_PLACEHOLDER_PATTERNS` moves here, is extended
  (e.g. `[Your Name]`, «أدخل», «اسمك هنا»), and is finally enforced. Result:
  `(ok, violations, claim_source_map)`.
- `tailor(fact_sheet, target_role, target_city, language)` — AI pass
  (existing provider chain) restricted to reorder/rephrase/select; on any
  reconciliation violation → deterministic render **from the fact sheet only**
  (never placeholders, never a hollow apology). The deterministic render is the
  guaranteed floor and is what the no-AI fallback uses — the `[Your Name]`
  fallback in `rico_apply_ai.py` is corrected in passing (it violates the
  invariant in live code).

### Step 3 — DOCX artifact, persisted before any success claim

- New table `generated_documents` (same migration file): id UUID, user_id,
  doc_kind (`tailored_cv`), source_document_id, target_role, target_city,
  language, content_text, claim_source_map JSONB, docx_bytes BYTEA,
  created_at. Bytes are small (tens of KB) and persisting them makes the
  download byte-stable and restart-proof.
- Render with the already-present `python-docx` (write side). No new
  dependency.
- Chat/service flow: insert row (commit) → verify readable-back → only then
  emit the success message containing the download link. Failure at any point
  returns an honest "couldn't save it" reply (pattern already used at
  `src/rico_chat_api.py:10880-10890`).

### Step 4 — Authenticated download

- `GET /api/v1/user/generated/{id}/download` in a new
  `src/api/routers/generated_documents.py`: JWT via `get_current_user`,
  strictly user-scoped lookup (404 on other users' ids — same shape as
  files.py), returns the stored bytes with
  `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  and a content-disposition filename. Rate-limited with the existing limiter.
- `apps/web/lib/api.ts`: one helper for the download URL through the `/proxy`
  path (cookie carries auth). Chat renders the link markdown it already
  supports; no new UI surface in this slice.

### Step 5 — Chat continuation: the CV flow never falls to generic fallback

- Add `_CV_TAILOR_FOLLOWUP_RE` (Arabic + English): role/city-targeted forms —
  «خصصها لوظيفة … في …», «اجعلها ل…», «عدلها لوظيفة…», "tailor it for … in …",
  "make it for the … role" — routed to the tailor service with extracted
  role/city.
- Direct intent: extend `_CV_GENERATE_RE`-adjacent routing so "سيرة ذاتية
  لوظيفة عمليات في دبي" with a stored CV goes to tailor, not the skeleton
  builder.
- Flow guard: while `last_flow_state == "cv_builder"`, an unmatched follow-up
  gets a deterministic clarification listing the concrete supported actions
  (tailor for role/city, add section, download) — `_answer_with_ai_fallback`
  is unreachable from this state. This enforces the invariant *within the CV
  flow* (global fallback behavior elsewhere is untouched — that would be
  Cognitive-Control-Plane scope).
- `_handle_cv_generate_from_profile` gains the fact-sheet source: when the
  active CV has retrievable text, real Experience/Education sections are
  rendered from it instead of being reported "unavailable", and the handler
  stops asking for fields the fact sheet already contains.

### Step 6 — The supplied Arabic transcript as an end-to-end regression test

- `tests/test_cv_tailoring_arabic_transcript.py` replays
  `tests/fixtures/arabic_cv_tailoring_transcript.json` (verbatim production
  turns — owner-supplied, see E7) against `RicoChatAPI` with a synthetic user
  + synthetic stored-CV fixture. Assertions per invariant:
  1. no turn's `response_source` is the generic AI fallback;
  2. no placeholder pattern in any reply or artifact;
  3. every employer/date/duty/achievement/certification/salary/visa/location/
     proficiency string in the rendered CV maps into the fixture source text
     (reconciliation report empty);
  4. no reply claims readiness before the `generated_documents` row exists;
  5. the download route returns 200 + DOCX (ZIP `PK` magic) for the owner and
     404 for another user.
- Generalization coverage (Product Generalization Rule): the same suite runs
  an English variant, a no-CV user (deterministic "upload first" — never
  fabrication), a user with a second unrelated target role, and a
  legacy-document user without `extracted_text` (honest limitation reply).
- Existing suites `tests/test_cv_generation_continuity.py`,
  `tests/test_cv_generate_from_profile.py` must stay green; frontend
  `npm run build` for the api.ts change.

### Invariant → enforcement map

| Invariant | Enforced by |
|---|---|
| No placeholders | reconcile() placeholder patterns (finally wired) + deterministic floor render |
| No invented dates/employers/duties/achievements/certs/salary/visa/location/proficiency | fact-sheet-only sourcing + reconcile() claim mapping; violations ⇒ deterministic render |
| Every rendered claim maps to source evidence | claim_source_map persisted with the artifact |
| All stored CVs retain retrievable extracted content | Step 1 write paths (confirm, My Files upload); honest surfacing for legacy rows |
| Chat continuation never falls to generic fallback | Step 5 flow guard inside cv_builder state |
| No success claim before artifact persisted + downloadable | Step 3 ordering (insert → verify → claim) |
| Exact Arabic transcript is an E2E regression test | Step 6 fixture + suite |

### Sequencing, size, and rollout

- Implementation order: Step 1 → 2 → 3 → 4 → 5 → 6 (each step lands with its
  tests; one PR, reviewable commit-by-commit).
- Migration rollout: additive `ADD COLUMN IF NOT EXISTS` + new table only —
  runtime-auto-apply per 026/038 precedent, drift-checked file included;
  rollback = drop column/table, no data dependency.
- No env vars added. No provider changes. `agent_runtime`/safety layers
  untouched except consuming, not bypassing, them.
- Open decisions for owner sign-off before implementation starts:
  1. persist DOCX bytes (proposed) vs render-on-demand;
  2. My Files upload parsing in-slice (proposed: yes — required by the
     stored-content invariant) vs deferred;
  3. supply the verbatim transcript for the fixture (required to merge).
