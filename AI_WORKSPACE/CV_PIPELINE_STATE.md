# CV Pipeline — Continuity Document

**Read this first if you are picking up CV work with no prior context.**

This file exists because context was lost once already. It is written for someone
who has never seen this work before. It records what is true, what was decided,
and what must not be changed without the owner's explicit permission.

Last updated: 2026-07-25. Production head at time of writing: **`e26548b`**
(`9a9ee9b` plus the two changes merged after it).

---

## 1. Where production is

`main` is at **`e26548b`**. Three CV-related changes shipped in sequence, followed
by two unrelated merges (#1387, #1386) that moved the head without touching the CV
path — measure any baseline against the current head, never against `9a9ee9b`:

| Commit | What it did |
|---|---|
| `efcb9ce` (#1381) | Application counts: every status counted, buckets reconcile against the total, unmapped and NULL statuses surfaced, DB failure no longer renders a fabricated empty state |
| `7037f06` (#1383) | CV confirm returns real save evidence (`document_id`, canonical filename, `doc_type`, `is_primary`, `parse_status`, `inserted`), one server-derived principal, opt-in `rename_on_match` so profile and My Files cannot disagree about a filename |
| `9a9ee9b` (#1384) | The structured-CV pipeline: `cv_structured` finally written and read, CV state derived from content, one read path, parser extended with work-experience and education sections |

**Owner live verification of `9a9ee9b` is still pending.** The owner has been asked
not to re-upload a CV until the pending-confirm PR (below) ships, because a
re-upload now would burn the artifact TTL without a working confirm card.

---

## 2. Parallel work and file ownership

Three sessions run in parallel. Ownership prevents collisions; it does not
replace judgement.

| Track | Owns |
|---|---|
| CV pipeline (this track) | `src/cv_*.py`, `src/services/cv_*.py`, `src/api/routers/rico_chat.py`, `src/rico_chat_api.py`, `src/repositories/profile_repo.py`, `src/repositories/cv_upload_artifact_repo.py`, `AI_WORKSPACE/` |
| Test-baseline reporting | The failing-test inventory on `main` |
| Security audit (read-only) | Security review output |

**Shared scope — STOP and ask the owner before touching any of it:**

- the authentication principle (how identity is resolved)
- `migrations/` (any file; a new migration is also a stop)
- CI configuration and workflows
- shared CV contracts consumed by more than one track
- this `AI_WORKSPACE/` directory beyond the files your track owns

Ownership alone does not authorise a change in shared scope. Report the overlap
at first contact instead of resolving it yourself.

---

## 3. The core product decision: no automatic saving

**A CV is never saved automatically on upload.** It stays a short-lived artifact
until the user reviews it and explicitly confirms.

This is deliberate. `POST /api/v1/rico/confirm-cv-profile` carries four gates that
an auto-save would bypass in one step:

1. **Plan quota** — `enforce_profile_optimization_allowed`
2. **Readability** — `validate_artifact_quality`, which returns 409 for a CV whose
   text cannot be read, so an unreadable CV never lands in My Files
3. **Primary promotion** — `is_primary` moves atomically to the new CV
4. **Atomic structured write** — `cv_text` and `cv_structured` committed together

There is also a user-consent reason: confirm is the only moment the user sees what
was extracted before it becomes the professional identity Rico matches jobs
against. A parser misreading a name or a job title would otherwise become their
profile silently.

**The obligation that comes with this decision:** while a CV is unconfirmed, the
product must not behave as though it has it. Saying "your CV is under review and
not saved yet — confirm it and I'll save it" is required. Showing a partial
extraction and then asking the user to paste their work history by hand is
forbidden, and so is any wording that implies the file was saved.

---

## 4. The pending-artifact contract

Upload creates a row in `cv_upload_artifacts` (migration 038) carrying
`filename`, `doc_type`, `content_hash`, `file_size`, `cv_text`, `expires_at`.

**It does NOT store the preview.** The preview is computed at upload time,
returned in the response, and discarded. Anything that needs it later must rebuild
it from the stored `cv_text` — using the same builder the upload response uses,
never a second copy of that logic.

**TTL is 180 minutes** (`src/repositories/cv_upload_artifact_repo.py`,
`_DEFAULT_TTL_MINUTES`). Resolution requires `expires_at > NOW()`, and expired rows
are purged.

**The risk this creates:** a user who uploads and does not confirm within three
hours loses the file and its extracted text permanently, with no way to recover it
except uploading again. Any flow that leaves a confirm step unreachable is
therefore not a cosmetic bug — it is silent data loss on a three-hour timer.

---

## 5. CV state vocabulary

Derived from stored content in `src/services/cv_state.py`. Never read from a
stored label alone.

| State | Meaning |
|---|---|
| `structured` | `cv_structured` is valid and substantive (work experience, education, or a credible skill set) |
| `text_extracted` | `cv_text` passes the shared readability contract; structure is missing or thin |
| `metadata_only` | A document exists behind neither |
| `parse_failed` | Extraction was attempted and explicitly failed |
| `uploaded` | A file arrived; extraction/confirmation has not finished |
| `none` | Nothing on file |

**`parsed` is a legacy value, read-only.** It is written by no path. It contributes
one fact — that a CV exists — and can never promote a row to `text_extracted` or
`structured`. Production rows still carry it, which is why it is still read.

**`metadata_only` means the user HAS a CV.** The product says the content is not
available; it never says "you have no CV", because that sends someone to re-upload
a file that is already stored.

**A store failure is not an absence.** `store_unavailable` and `no_cv_on_file` are
different facts and must stay distinguishable all the way to the user-facing text.

### Replacement semantics on confirm

Confirming a CV **replaces** `cv_structured` (`replace_cv_structured=True`): the new
document when extraction is substantive, `{}` when it failed or was thin. The
default elsewhere stays MERGE.

Reason: the merge made `None` a no-op, so a previous CV's structure survived while
`cv_text` became the new CV's text — and state derivation prefers structure, so
Rico would answer from the old CV's employers while believing it had read the new
one. After one transaction, `cv_text` and `cv_structured` describe the same
document.

### No migration, no backfill

State is derived at read time, so no existing row needs rewriting to be read
correctly. No column was added to `cv_upload_artifacts`; migration 038 is
unmodified. Any future schema need gets a **new** migration file — never an edit
to an existing one.

---

## 6. Governance fact: a green CI is not a green suite

**The `pytest` job in `qa-tests.yml` runs an explicit allowlist of paths, not the
whole suite.** It collects `tests/unit/` as a directory plus a hand-maintained list
of files under `tests/`.

Consequences that everyone working here must internalise:

- A green CI has never meant the suite is green.
- The known failing tests on `main` sit largely where CI does not look.
- A test file added under `tests/` root runs in **no gate** unless it is added to
  that list. `tests/integration/` is collected by no gate at all except five
  explicitly named `*_postgres.py` files.
- Therefore: put new tests in `tests/unit/`, or add the file to the enumerated list
  in the same PR.

Always compare a full local suite run against a baseline measured on the same
commit with the same command. Counts measured on different trees are not
comparable.

**Baseline measured on `main@9a9ee9b`** with
`pytest tests/ -q --tb=no -p no:randomly` and the CI environment variables:

```
32 failed, 8670 passed, 91 skipped, 1 xfailed, 25 warnings in 620.73s
```

A different session measured 33 on `main`. The discrepancy is not resolved here;
treat your own same-command, same-commit measurement as the reference and require
zero NEW failures against it.

---

## 7. Security audit summary

No exploitable detail is recorded here — this repository is public.

- **No IDOR was found.** Ownership is resolved server-side; a client-supplied
  identifier cannot establish it.
- **The standing risk is operational privacy in logs**: user identifiers and CV
  filenames are written to logs in raw form in a number of places in the CV router.
  This is queued as its own PR and is deliberately not mixed into the pending-confirm
  work.

---

## 8. Known open defect: the confirm card is unreachable from the Vault

Verified against production by the owner, and traced in the code.

`/upload` (the Vault) uploads successfully and redirects to `/command?cv=ready`.
The confirm card, however, is **a chat message object**, appended only when the
upload happens inside `/command` itself. `cv=ready` renders a presentational panel
that fetches nothing and carries no `upload_id`. Both Vault components discard the
upload response. **No endpoint exists to read a pending artifact.**

Net effect: the artifact is alive in the database for three hours, nobody holds its
id, no confirm is ever called, and My Files stays empty while chat behaves as
though a CV exists.

`/upload`, both Vault components, `cv=ready` and the panel were all introduced
together in `c7bfa90` (#1328, 2026-07-23). This handoff was **never** wired — it is
not a regression from a working state.

### A second, independent falsehood in the same area

`_handle_cv_generate_from_profile` reads `work_experience` and `education` off
`RicoProfile`. **Neither field exists on that model**, so both always read as
absent, and the handler unconditionally tells every user that Work Experience and
Education "are not yet available from your parsed CV" and asks them to paste their
work history by hand — even for a user whose CV was confirmed and fully
structured. This is the same class of defect as the `cv_text`/`cv_structured` gap
fixed in `9a9ee9b`: reading CV grounding off a model that does not carry it.

Restoring the confirm card without also closing this is not an acceptable fix.

### A fourth entry point with the same false success: `/profile`

`ProfileEditorial` uploaded a CV, announced "CV uploaded — Rico is reading it",
reloaded the file list and refreshed the profile — all before confirmation had
created any document. The success message asserted an outcome the upload
response cannot know, and the list it reloaded was still empty.

**There are three CV upload entry points — Command, Vault and Profile — and they
must share one state machine.** Fixing two of them and leaving the third is how
this class of defect survives: the user simply meets it somewhere else.

### A third, independent falsehood: a banner with no artifact behind it

Observed in production. On the Vault surface, the pending-review banner ("CV
preview ready — complete the review in the chat to save it to My Files")
rendered directly above the empty state ("No files yet — upload your CV to get
started"), in one frame. The product told one person, at one moment, that their
preview was ready and that they had no files.

The banner was **client state, not a query**: a boolean set once by the upload
animation's completion callback, with no path back to false and nothing to
re-derive it. It therefore outlived the artifact it described and survived a
full delete cycle.

**Standing rule that comes out of this:** a claim about stored data is drawn
from a query of that data, at the moment of rendering. A flag, a URL parameter
or a browser-stored value may gate a claim, but none of them may be sufficient
to draw one — anything that can render the claim on its own will eventually
render it after the thing it describes is gone.

The empty state carries the second half of the rule. An empty list is a true
fact, but "upload your CV to get started" is the wrong *instruction* for someone
whose CV is uploaded and awaiting confirmation, and telling them to upload the
same file again is how two true-sounding lines came to contradict each other.

---

## 8b. The pending-upload endpoint contract

`GET /api/v1/rico/pending-cv-upload` answers with exactly one of **five named
states**. They are named, not inferred, because every pair that gets collapsed
becomes a lie the product tells:

| State | Meaning |
|---|---|
| `pending` | A real, retrievable, unconfirmed upload. Carries the preview and the expiry timestamp. |
| `already_saved` | A `user_documents` row matches on `(user_id, doc_type, content_hash)`. The user is told their CV **is saved**, with a pointer to My Files — never "nothing pending", which reads as "your upload went nowhere". |
| `expired` | The upload happened and its preview lapsed. Never reported as "no CV". |
| `absent` | No artifact at all. |
| `unavailable` | The store could not be read. Never reported as an absence. |

**Two vocabularies exist here on purpose, and neither is a drift from the other.**
The five words above are the `state` field of the READ endpoint — what a later
reader finds about an artifact. `preview_ready` / `preview_not_persistable` /
`cv_storage_unavailable` are the `status` field of the WRITE endpoint
(`POST /upload-cv`) — what happened to the request being answered. They describe
different things and never co-occur: `preview_not_persistable` hands the user a
real, readable extraction and says it cannot be confirmed, while `unavailable`
hands them nothing and says the store could not be read. Collapsing them would
turn "I read your CV but can't save it" into "I couldn't read anything".

The pending card **must show the user when their preview expires.** Temporary
retention is only defensible if the person whose data it is can see its duration.

"Pending" is derived from the triple key, never stored and never consumed. A
confirmed CV stops being pending the moment its document row exists, which also
keeps confirm idempotent — a second confirm of the same `upload_id` returns
`inserted: false` with the same document evidence, never a 409 and never "no CV".

### One artifact per `(user_id, doc_type, content_hash)`

This table stores the **full parsed text** of an unconfirmed CV, so a duplicate
row is a retained extra copy of someone's CV — not merely a wasted row. The
behaviour that amplifies it is ordinary: a user whose flow looks stuck uploads
the same file again, and again.

Two rules hold the bound:

1. **A CV that is already a saved document gets no artifact at all.** The upload
   answers `already_saved` and points at My Files. There is nothing to confirm,
   so creating a confirmable full-text copy would be both a redundant question
   and retained data with no purpose.
2. **A repeated upload refreshes the existing artifact instead of adding a
   sibling**, and returns the same `upload_id` — so a confirm already issued
   against an earlier attempt still resolves rather than being orphaned.

Rule 2 is serialised with a transaction-scoped **advisory lock keyed on the
triple**. A read-then-insert is not sufficient and the difference is not
theoretical: with the lock removed, eight concurrent uploads of the same bytes
produced **four** artifacts against a real server — four retained copies of one
CV. With it, exactly one. That is proven by a real-Postgres test, because the
interleaving does not exist at the mock layer.

No unique index was added: that is a schema change, and the lock gives the same
guarantee at the one place that writes.

### Deferred: purge for expired artifacts (belongs with the TTL change)

`expires_at` only blocks **reading**. Physical deletion today is opportunistic —
it happens when someone uploads again. In a low-upload account an expired CV's
full text therefore lingers in the table far longer than the advertised window,
which turns the stated retention period into a promise that is not kept. The TTL
PR must ship a **daily purge on a protected cron, in bounded batches, logging
counts only** — never filenames, CV text, or content hashes.

### Constraint, documented not built: re-processing is an explicit operation

Re-analysing an already-saved CV with a better parser needs a deliberate
`reprocess` / `parser_version` operation. It must never be achieved by asking the
user to silently re-upload: the triple key will correctly answer `already_saved`.
That is the contract working, not a defect to route around.

## 8c. Queued, not started

A separate small documentation batch, after the confirm PR opens:

1. **Fix duplicate task identifiers in `AI_WORKSPACE/TASKS.md`.** Two ids are each
   used twice for unrelated tasks. The test that detects this is correct and
   states a true fact — the fix belongs in the data, and the test must not be
   weakened to accommodate it.
2. **A cross-track decision log**, so today's rulings are not reopened: the
   file-ownership map and what counts as shared scope that stops at first
   contact; the five artifact states; the retention decision with its privacy
   rationale and the purge requirement; "a read failure is not evidence of
   absence"; how a failed write differs from an unusable store and what each
   returns; the `reprocess` constraint; and the rule that a new guard must be
   shown to fail before it is accepted.

Discipline for that batch: this repository is public. Engineering description
only — no environment configuration state, no counts of weak or unreviewed
areas, no names of absent configuration values, and no reproduction steps for any
defect.

## 9. Approved execution order

1. Any ownership or identity gap, if one is found — highest priority
2. **Restore the confirm path** (the PR this document ships with)
3. Owner live verification against production
4. Test-baseline cleanup in small PRs
5. Unify CV upload surfaces on PDF + DOCX, with honest matching copy
6. Rebase and review #1382 (the routing PR, currently a frozen draft)

Nothing merges without the owner. No autonomous merge, no deploy, no writes to the
production database for testing, no monitoring loops.
