# P1 — CV Generation Integrity: Repository Trace + Bounded Vertical Slice (RFC)

Date: 2026-07-22 (rev 3 — owner re-review corrections applied; bounds approved)
Status: RFC ready for owner merge decision — docs only; implementation gated on this RFC merging
Task: TASK-20260722-001 (canonical — one task, two sequential review gates)
RFC PR: #1312 (docs-only; stays docs-only per owner ruling)
Implementation PR: opened FRESH from then-current `main` only after this RFC
merges, same TASK ID. #1312 is never morphed into the implementation PR.
Incident class: core-product integrity — Rico failed an Arabic tailored-CV
request, asked for already-available data, produced placeholders/unsupported
claims, and revealed that non-active CV documents retain only metadata.

Product rule applied: the production transcript exposed the bug, but the fix is
global — every finding below is a system behavior affecting all users, not one
account.

## Owner decisions (2026-07-22, recorded from PR #1312 review)

1. **DOCX v1 = persisted bytes**, not render-on-demand — proving the file the
   user was told is ready was actually generated, saved, survives server
   restart, and is byte-identical across downloads. **Unbounded storage is NOT
   approved**: hard byte-size cap, SHA-256, bounded retention/lazy purge,
   account-deletion cleanup, defined source-deletion behavior, and no raw CV
   content/bytes/personal excerpts in operational logs are mandatory parts of
   the design.
2. **My Files parsing is in-slice for `doc_type=cv` only.** New CV uploads are
   parsed through the existing bounded/safe parser path before being accepted
   as reusable; no new metadata-only CV rows. Explicit extraction state
   (`ready` / `legacy_missing` / `failed`) + parser version; `NULL
   extracted_text` never ambiguously encodes state. Cover letters/other types
   are exempt.
3. **No verbatim production transcript in the repo** (public repository, real
   personal data — committing it to git history would be a permanent leak even
   if later deleted). The regression fixture is an owner-approved **redacted
   production-structure regression fixture** that preserves: the core Arabic
   command wording; the role ordering; the conversation transitions; the
   Operations/Dubai request; the user's objection to being re-asked for
   already-provided data; and the incorrect "cannot create the file" reply.
   It replaces: real name → synthetic test user; phone/email → synthetic
   values; filenames → `CV_Operations.pdf` and similar; company/account data →
   test data. It is labelled `redacted`, never `verbatim`. Evidentiary
   linkage, if needed, is a hash/reference to the private source held outside
   the repo.
4. **Deterministic-first implementation.** No free-form AI rewrite in the
   first slice; AI rephrasing is a later, separately gated enhancement.

**Owner re-review (2026-07-22, second pass) — bounds APPROVED, all decisions
answered:**

5. **Extracted-text cap: 512 KiB, truncation REJECTED.** Over-cap extraction
   is an honest 4xx failure with no new row and no profile/document mutation —
   never a silently shortened CV that could omit work history yet still
   produce a "verified" artifact.
6. **`failed` extraction status is reserved** for an *existing* row that later
   fails re-validation/reparse. A failed NEW upload creates no row at all —
   the two events are never conflated.
7. **DOCX/storage: 2 MiB hard cap approved**, SHA-256 write/read-back
   verification, account-deletion cleanup, strict user scope, sanitized
   download filename — plus defense in depth: creation consumes the existing
   CV/profile-optimization allowance (`profile_optimization_limit`
   entitlement, `src/subscription_plans.py`), and an absolute maximum of
   **60 retained generated artifacts per user** (successful creation purges
   the oldest rows beyond the cap).
8. **Retention: 90 days from artifact creation** (not rolling from last
   access) as **logical expiry + lazy physical purge** — persisted
   `expires_at`, expired rows filtered to 404 on every read, bounded-batch
   deletes on create/download, immediate and complete purge on account
   deletion. A strict physical day-90 deletion guarantee would need a
   separately approved scheduler job and is NOT part of v1.
9. **Fixture approval boundary:** the redaction *contract* is approved here;
   the actual synthetic fixture (exact token mapping) is reviewed in the
   implementation PR — it is not a blocker on this RFC. The private verbatim
   transcript stays out of git history.
10. **No migration number is reserved by this RFC** — the implementation PR
    uses the next available migration number at its then-current `main`.

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

### E6. Existing components and their honest reuse boundary

- `src/services/career_context.py` — the M1 read-path resolver from the
  2026-07-19 incident. **Scope correction (owner review):** it resolves
  active-document provenance plus trusted name/years/conflict state. It is
  **not** an employer/date/duty/achievement reconciliation layer. The slice
  reuses it for **identity/name/years only**; document-level fact extraction is
  a new bounded component (Part 2, Step 2).
- `src/services/document_resolver.py` — canonical active-CV resolution
  (primary → latest → legacy profile fallback), including strict variants that
  distinguish "store down" from "no documents". Reused as-is.
- `src/rico_safety.py` blocks forged-document requests ("forge" trigger, `:38`,
  `:101`) — the slice's reconciliation guard extends the same principle to
  *generated* output.
- `src/cv_parser.py` + `src/services/docx_safety.py` — the existing bounded/safe
  parse path (decompression-bomb guard, sync parser behind `run_in_executor`).
  The My Files CV parse (Step 1) goes through this path, not a new parser.

### E7. Transcript status

The verbatim Arabic production transcript exists only outside the repository
(it contains real personal data; the repo is public). Per owner ruling it is
**never committed**. The regression fixture is a redacted structural fixture
(exact turn/intent sequence, synthetic tokens for all personal/account values),
labelled `redacted`. If evidentiary linkage is required, the fixture records a
SHA-256 of the private source transcript — nothing more.

---

## Part 2 — One bounded vertical slice (single task, two review gates)

**Approved boundary (owner review):**

> selected readable CV → provenance-bearing fact sheet → deterministic
> Operations/Dubai CV → verified DOCX persisted with retention controls →
> JWT-scoped download → Arabic redacted transcript regression

Explicitly out of scope for the first implementation: free-form AI rewriting
(later, separately gated enhancement), cover-letter overhaul, PDF rendering,
Cognitive Control Plane, multi-agent/fleet writers, deployment, any second
product objective, career-context M2 identity dedupe.

Process: after this RFC merges, ONE fresh Draft implementation PR is opened
from the then-current `main` under TASK-20260722-001. No competing PRs.

### Step 1 — Every stored CV retains retrievable extracted content, with explicit state

- Schema (additive, 026/038 precedent, drift-checked numbered migration file —
  **next available migration number at implementation time**, not reserved
  here — mirrored into `_USER_DOCUMENTS_DDL` via `ADD COLUMN IF NOT EXISTS`):
  - `extracted_text TEXT` — hard cap **512 KiB** (owner-approved) enforced at
    write time. **No truncation**: an over-cap extraction is an honest 4xx
    failure with no new row and no profile/document mutation — a silently
    shortened CV could omit work history yet still yield a "verified"
    artifact, so it is rejected outright.
  - `extraction_status TEXT NOT NULL DEFAULT 'legacy_missing'`
    (`ready` | `legacy_missing` | `failed`) — `NULL extracted_text` never
    encodes state by itself; every reader branches on `extraction_status`.
    `failed` is reserved for an EXISTING row that later fails
    re-validation/reparse; a failed new upload creates no row (the two events
    are never conflated).
  - `extraction_parser_version TEXT`, `extracted_at TIMESTAMPTZ`.
- Confirm path (`/api/v1/rico/confirm-cv-profile`): pass the artifact's
  `cv_text` into `get_or_create_user_document` → row lands `ready`.
- My Files direct upload (`files.py`), **`doc_type=cv` only**: parse the PDF
  bytes through the existing bounded/safe parser (`CVParser` behind
  `run_in_executor`, docx_safety guard untouched). Commit semantics are
  all-or-honest-failure: either extraction succeeds and the reusable `ready`
  row is committed, or the API returns an explicit parse-failure response and
  **no new CV row is created**. No new metadata-only CV rows, ever. Cover
  letters/other doc types keep current behavior (exempt).
- `set-primary` re-sync: when the newly activated document is `ready`, also
  restore `rico_profiles.cv_text` from its `extracted_text` — making the
  existing "I'll re-sync your profile from it" promise true. For
  `legacy_missing` rows the promise copy is corrected instead (below).
- Honesty for legacy rows: previously uploaded non-active CVs' bytes were
  discarded and are unrecoverable — rows stay explicitly `legacy_missing` and
  chat/analysis surfaces say "content not stored — re-upload to enable
  tailoring" (replacing the impossible re-sync promise at
  `src/rico_chat_api.py:2795-2801`). The stored-content invariant is enforced
  for every write from this slice forward; discarded bytes are not conjured.

### Step 2 — Provenance-bearing fact sheet (new bounded component; deterministic)

New `src/services/cv_fact_sheet.py` (name final at implementation):

- `build_fact_sheet(user_id, document_id=None)`:
  - Source resolution via `document_resolver` (explicit `document_id` when the
    user picked one; else primary → latest). Only `ready` documents are
    tailorable; `legacy_missing`/`failed` → honest re-upload reply.
  - Content: the resolved document's `extracted_text`
    (fallback to `rico_profiles.cv_text` only when the resolved document is
    the active CV and predates the column).
  - Identity fields (name/years) come from `career_context` **only** — trusted
    name gate, display_years conflict handling. Nothing else is claimed from
    career_context (owner correction: it is not a duty/achievement layer).
  - Output: typed entries (contact, roles, employers, date ranges, duties,
    achievements, certifications, skills, education, and — only if literally
    present in source — salary, visa status, location, language proficiency).
    Every entry carries provenance as
    `{document_id, start_offset, end_offset, source_hash}` — offsets into the
    stored extracted text; **no raw source spans duplicated** into the
    provenance records, and none in logs.
- `verify_render(rendered_text, fact_sheet)`: every employer, role title, date
  token, certification, and numeric/salary/visa/proficiency claim in the
  rendered output must resolve to a fact-sheet entry; `_CV_PLACEHOLDER_PATTERNS`
  moves here, is extended (`[Your Name]`, «أدخل», «اسمك هنا», …) and is finally
  enforced. Because Step 3 renders deterministically *from the fact sheet*,
  this check is a hard invariant gate (belt-and-braces), not a best-effort
  post-hoc matcher over free AI text.
- Deliberately **no AI generation in this slice**. The known limitation is
  accepted: duties/achievements are selected and ordered for the target role
  (keyword relevance against role/city), never rephrased. AI rephrasing, if
  ever added, is a separately gated enhancement with its own review — the
  owner's point that normalized post-hoc matching cannot prove paraphrase
  grounding is recorded here as the reason.

### Step 3 — Deterministic DOCX artifact, persisted with lifecycle controls

- New table `generated_documents` (same migration file): `id UUID`, `user_id`,
  `doc_kind` (`tailored_cv`), `source_document_id`, `target_role`,
  `target_city`, `language`, `content_text`, `provenance_json JSONB`
  (offset-based, per Step 2), `docx_bytes BYTEA`, `docx_sha256 TEXT`,
  `byte_size INTEGER`, `created_at`, `expires_at TIMESTAMPTZ NOT NULL`.
- Storage/lifecycle contract (owner-approved bounds):
  - hard DOCX size cap **2 MiB** (deterministic render stays ~tens of KB);
  - SHA-256 recorded at write; download re-verifies bytes against it;
  - creation consumes the existing CV/profile-optimization allowance
    (`profile_optimization_limit` entitlement, `src/subscription_plans.py` —
    "20 CV & profile optimizations per month" paid / 1 free);
  - absolute cap of **60 retained generated artifacts per user** — a
    successful creation purges the oldest rows beyond the cap (defense in
    depth so retention is bounded even if lazy purge lags);
  - retention = **logical expiry + lazy physical purge**, NOT guaranteed
    physical deletion at exactly day 90 (that would require a separately
    approved scheduler job): `expires_at = created_at + 90 days` persisted at
    write; every read/download filters expired rows and returns 404; create
    and download paths delete a bounded batch of expired rows (038 lazy-purge
    precedent — no background worker exists on Render);
  - account deletion purges all `generated_documents` rows for the user
    immediately and completely (wired into the existing deletion path
    alongside `clear_cv_grounding`);
  - source-CV deletion: generated artifacts SURVIVE (they are the user's own
    derived documents) but `source_document_id` dangles to NULL via
    `ON DELETE SET NULL`, and re-tailoring from the deleted source is
    naturally impossible;
  - no raw CV text, extracted text, or source excerpts in logs or audit
    metadata — log ids, sizes, hashes, and statuses only.
- Render with the already-present `python-docx` (write side; no new
  dependency). Deterministic template: header → summary → experience →
  education → certifications → skills, from fact-sheet entries only.
- Ordering invariant: insert + commit → read-back verify (hash) → only then
  the success reply containing the download link. Any failure → honest
  "couldn't save it" reply (pattern at `src/rico_chat_api.py:10880-10890`).

### Step 4 — Authenticated download

- `GET /api/v1/user/generated/{id}/download` in new
  `src/api/routers/generated_documents.py`: JWT via `get_current_user`;
  strictly user-scoped lookup — cross-user ids return **404** (never 403,
  matching files.py information-hiding); rate-limited with the existing
  limiter; response is the stored bytes with the DOCX MIME type and a
  **sanitized `Content-Disposition`** filename (`_safe_filename`-equivalent:
  ASCII-safe, no CR/LF/control chars, fixed `.docx` suffix).
- `apps/web/lib/api.ts`: one helper producing the `/proxy` download URL
  (cookie carries auth). Chat renders the markdown link it already supports;
  no new UI surface in this slice.

### Step 5 — Chat continuation: the CV flow never falls to generic fallback

- Add `_CV_TAILOR_FOLLOWUP_RE` (Arabic + English): role/city-targeted forms —
  «خصصها لوظيفة … في …», «اجعلها ل…», «عدلها لوظيفة…», "tailor it for … in …",
  "make it for the … role" — routed deterministically to the fact-sheet →
  render path with the extracted role/city.
- Direct intent: extend `cv_generate`-adjacent routing so "سيرة ذاتية لوظيفة
  عمليات في دبي" with a `ready` stored CV goes to the tailor path, not the
  skeleton builder.
- Flow guard: while `last_flow_state == "cv_builder"`, an unmatched follow-up
  gets a deterministic clarification listing the concrete supported actions
  (tailor for role/city, add a section from source, download) —
  `_answer_with_ai_fallback` is unreachable from this state. The invariant is
  enforced *within the CV flow*; global fallback behavior elsewhere is
  untouched (that would be Cognitive-Control-Plane scope).
- `_handle_cv_generate_from_profile` gains the fact-sheet source: when the
  active CV is `ready`, real Experience/Education sections render from source
  content instead of being reported "unavailable", and the handler stops
  asking for fields the fact sheet already contains.

### Step 6 — Arabic redacted-transcript regression (end-to-end)

- Fixture: `tests/fixtures/arabic_cv_tailoring_transcript.redacted.json` —
  the owner-approved **redacted production-structure regression fixture**
  (see Owner decision 3 and E7): preserved elements are the core Arabic
  command wording, role ordering, conversation transitions, the
  Operations/Dubai request, the user's objection to re-asked data, and the
  incorrect "cannot create the file" reply; all personal/account values are
  synthetic (`CV_Operations.pdf`-style filenames). Header fields
  `"fidelity": "redacted-production-structure"` and
  `"source_sha256": "<hash of private verbatim transcript>"`.
- `tests/test_cv_tailoring_arabic_transcript.py` replays the fixture
  turn-by-turn against `RicoChatAPI` with a synthetic user + synthetic stored
  CV. Assertions per invariant:
  1. no turn's `response_source` is the generic AI fallback;
  2. no placeholder pattern in any reply or artifact;
  3. every employer/date/duty/achievement/certification/salary/visa/location/
     proficiency string in the rendered CV resolves to a fact-sheet entry with
     valid offsets into the fixture source text;
  4. no reply claims readiness before the `generated_documents` row exists
     and hash-verifies;
  5. the download route returns 200 + DOCX (ZIP `PK` magic) for the owner-user
     and 404 for another user.
- Generalization coverage (Product Generalization Rule): English variant;
  no-CV user (honest "upload first", never fabrication); user with a second
  unrelated target role; `legacy_missing` document user (honest limitation
  reply); `failed` extraction path (upload rejected honestly, no row).
- Existing suites `tests/test_cv_generation_continuity.py`,
  `tests/test_cv_generate_from_profile.py` stay green; `npm run build` for the
  api.ts change; `python -m pytest tests/ -v --tb=short` scope per CLAUDE.md.

### Invariant → enforcement map

| Invariant | Enforced by |
|---|---|
| No placeholders | deterministic render from typed fact sheet + `verify_render` placeholder gate (guard finally wired) |
| No invented dates/employers/duties/achievements/certs/salary/visa/location/proficiency | deterministic selection-only render — no free-form generation exists in the path; `verify_render` as hard gate |
| Every rendered claim maps to source evidence | offset-based provenance `{document_id, start_offset, end_offset, source_hash}` persisted with the artifact |
| All stored CVs retain retrievable extracted content | Step 1 write paths (confirm; My Files cv parse-or-reject); explicit `extraction_status`; honest `legacy_missing` surfacing |
| Chat continuation never falls to generic fallback | Step 5 flow guard inside `cv_builder` state |
| No success claim before artifact persisted + downloadable | Step 3 ordering (insert+commit → hash read-back → claim) |
| Arabic transcript is an E2E regression test | Step 6 redacted structural fixture + suite (verbatim stays private, hash-linked) |

### Sequencing, size, and rollout

- Implementation order: Step 1 → 2 → 3 → 4 → 5 → 6, one fresh Draft PR from
  then-current `main` after this RFC merges; reviewable commit-by-commit.
- Migration rollout: additive `ADD COLUMN IF NOT EXISTS` + one new table —
  runtime-auto-apply per 026/038 precedent, drift-checked file included;
  rollback = drop columns/table, no data dependency.
- No env vars added. No provider changes. `agent_runtime`/safety layers
  consumed, never bypassed. No deploys from either PR; Render/Vercel
  verification follows OPERATING_RULES after owner merge.
- All owner decisions are ANSWERED (see Owner decisions 1–10 above): bounds
  approved (512 KiB extracted-text / no truncation; 2 MiB DOCX; 90-day logical
  expiry + lazy purge; 60-artifact per-user cap; optimization-allowance
  consumption). The redaction *contract* is approved; the actual synthetic
  fixture (exact token mapping) is reviewed in the implementation PR and is
  not a blocker on this RFC.
- The only remaining gate before implementation is the owner's RFC merge
  decision on #1312. The RFC merge authorizes NO deploy and NO production
  migration — implementation is a fresh Draft PR under TASK-20260722-001.
