# Handoff: Mobile UX + Document Context — 2026-06-21

**Branch:** `claude/system-quality-audit-ikkamf` (merged → `main`)
**PR:** #717 (merged 2026-06-21, SHA `b37fa62`)
**CI status:** pytest ✅ Vercel ✅ DEPLOYED

---

## Summary

Three UX/quality issues fixed in the same PR as the audit (round 2 + 3):
- Chat text rendered with broken markdown (no tables, no numbered lists)
- Typing a number like "3" to pick a Rico menu option sent it to the AI instead of routing it
- Mobile browsers zoom in on tap because chat textarea font-size was 14px (< iOS 16px threshold)
- Uploaded non-CV documents (cover letters, contracts, etc.) were classified correctly but that
  classification was never stored — Rico had no memory of what the user uploaded by the next chat turn

All fixed and merged. 190 tests pass (29 new).

---

## Changes shipped (commit `0c52ab9`, squashed into `b37fa62` on main)

### 1. Mobile zoom fix — `apps/web/app/command/page.tsx`

**Root cause:** The chat `<textarea>` had `text-sm` (14px). iOS Safari auto-zooms the entire
viewport when a user taps any input with `font-size < 16px`, causing the "page zooms out/in"
experience the user reported.

**Fix:** `text-[16px] sm:text-sm` — 16px on mobile (prevents iOS auto-zoom), 14px at ≥640px where
zoom isn't an issue. No visual change on desktop.

**Note:** The viewport meta (`width=device-width, initial-scale=1, viewport-fit=cover`) was already
correct. The textarea font-size was the sole cause of the auto-zoom.

---

### 2. Numeric option routing — `src/rico_chat_api.py`

(Shipped earlier in this PR session — documented here for completeness.)

**Root cause:** `_LETTER_CHOICE_RE` only matched A–D. When Rico presented a numbered list (1–4)
and the user typed "3", it fell through to the AI which fabricated a response instead of selecting
option 3.

**Fix:** Added `_NUMBER_CHOICE_RE = re.compile(r"^[1-9][.:\s]*$")` and dual-branch logic in
`_resolve_letter_choice`: letters (A–D) use `ord()` offset; digits (1–9) use `int() - 1`.
34 new tests in `tests/test_letter_choice_routing.py`.

---

### 3. Chat markdown rendering — `apps/web/app/command/page.tsx`

(Shipped earlier in this PR session — documented here for completeness.)

**Root cause:** `/command` page used a hand-rolled `renderMarkdown` function that only handled
`#` headers, `*` bullets, and `**bold**`/`*italic*`. Numbered lists, tables, code blocks, and `---`
dividers were rendered as raw text.

**Fix:** Removed `renderMarkdown`, `renderInline`, `INLINE_TOKEN_RE`, `MD_LINK_RE`, `LINK_CLASS`
(~70 lines). Rico messages now render through the existing `RicoMarkdownContent` component
(`react-markdown` v8 + `remark-gfm`), which handles the full GFM spec.

---

### 4. Document type context storage — `src/api/routers/rico_chat.py`

**Root cause:** The upload route called `classify_document()` and returned the type to the
frontend, but never wrote it to the user's session memory. By the next chat turn, Rico had no
knowledge of what was uploaded.

**Fix (non-CV path):** After `_classification_response()` is built for non-CV documents
(offer letters, contracts, cover letters, recruiter emails, certificates, company profiles),
writes `last_uploaded_document` to `recent_context` via `RicoMemoryStore` — authenticated
users only; try/except so upload can never break.

```python
_rctx["last_uploaded_document"] = {
    "document_type": doc_type,
    "display_label": classification.display_label,
    "filename": safe_name,
    "confidence": round(confidence, 3),
    "suggested_actions": list(classification.suggested_actions or []),
}
```

**Fix (CV path):** Same write after successful CV extraction (stores `document_type: "cv"`).

---

### 5. Document meta-query handler — `src/rico_chat_api.py`

**Root cause:** Even with context stored, Rico had no handler for "what did I upload?" — it would
fall through to the AI which would either make something up or say it doesn't know.

**Fix:** New `_UPLOAD_DOC_QUERY_RE` class attribute + `_get_recent_upload_document_reply` method.
Fires early in `_process_message_inner` (before onboarding checks and the main AI router) for
explicit document meta-queries only:
- "what did I upload?"
- "what type is the document?"
- "document type" / "file type"
- "the document I uploaded"
- etc.

Returns a plain-text reply with label, filename, confidence %, and suggested action labels.
Falls through to normal handling (returns `None`) for all other messages.

29 new tests in `tests/test_document_upload_context.py`.

---

## Remaining gap — TASK-20260621-030

The document type context is stored and surfaced for explicit meta-queries, but **broader queries
are not yet handled**:

- "can you review it?" — falls to AI with no document context
- "summarize the offer letter" — AI doesn't know what was uploaded
- "is there anything unusual in this contract?" — no context injected

**Required:** In `_process_message_inner` or the AI context builder, check for
`last_uploaded_document` in `recent_context` and inject a brief note into the system prompt or
user message context when the document is non-CV and recent. See TASK-20260621-030 in TASKS.md.

---

## UI/UX backlog — status

4 of 20 audit items done. 16 remain. Top 3 by impact:

| Item | Description | Effort |
|---|---|---|
| 1-C | Search timeout countdown + reliable fallback buttons | Medium |
| 3-A | Profile completeness single source of truth (sidebar 71% vs page 54%) | Medium |
| 2-D | "Mark as Applied" CTA inline on link-opened job cards | Low |

Full backlog: `TASK-20260619-028` in TASKS.md.

---

## What's next (recommended order)

1. **TASK-20260621-030** — Document context AI injection (completes CAREER-OS-04 end-to-end)
2. **1-C** — Search timeout/countdown indicator (immediate visible UX win)
3. **D1** — Runtime DDL audit tables (highest-risk tech debt from the audit)

---

## Verification

```
pytest (190 tests):   ✅ passing
Vercel preview:       ✅ DEPLOYED
PR #717:              ✅ merged → main (b37fa62)
No DB migrations:     ✅
No env changes:       ✅
```

## Changed files

- `apps/web/app/command/page.tsx` — textarea font-size + RicoMarkdownContent swap
- `src/rico_chat_api.py` — `_NUMBER_CHOICE_RE`, `_resolve_letter_choice`, `_UPLOAD_DOC_QUERY_RE`, `_get_recent_upload_document_reply`, `_process_message_inner` wiring
- `src/api/routers/rico_chat.py` — `last_uploaded_document` stored on upload (non-CV + CV paths)
- `tests/test_letter_choice_routing.py` — 34 new tests for numeric routing
- `tests/test_document_upload_context.py` — 29 new tests (new file)
- `AI_WORKSPACE/CURRENT_STATE.md` — updated
- `AI_WORKSPACE/TASKS.md` — TASK-20260621-029 → done; TASK-20260621-030 added

## Rollback

`b37fa62` is a squash merge. Revert via `git revert b37fa62` on main. No migrations, no Neon
changes, no Render env changes — fully safe to revert.
