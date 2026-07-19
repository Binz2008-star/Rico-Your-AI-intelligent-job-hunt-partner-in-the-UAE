# Canonical Career Context Program

Owner order (2026-07-19): one Draft PR — "Canonical Career Context and
Active-CV Provenance". Map first, prove the canonical source (or its
absence), document the program, then ship the smallest compatible
resolver. No schema changes. No production data mutation. Draft until
owner review.

## Vision

Every surface of Rico answers career questions (active CV, years of
experience, identity name) from ONE resolver with explicit provenance, so
the profile report and the job search can never contradict each other
again, for any user, in any language, on any provider path.

## Epic

EPIC-CAREER-CONTEXT — Canonical career context and active-CV provenance.

Production incident (2026-07-19, exposed by the owner smoke account; the
fix is global): the profile report said "10 years, active CV = Roben
Edwan CV.docx" while the job search silently used ~8 years from
Banking_CV.pdf, and the identity name surfaced as "Vip Relationship
Manager" (a CV title line).

## Milestones

1. **M1 — Read-side canonicalization (THIS PR).** One legal resolver
   (`src/services/career_context.py`) consulted by BOTH the profile
   report context and the job-search years read. Conflicts are exposed,
   never guessed. READ-ONLY: zero writes, zero schema changes.
2. **M2 — Duplicate-identity remediation (owner-gated, separate PR).**
   Merge/retire the duplicate `rico_users` rows and pin canonical-row
   selection so identity stops floating with `updated_at`. Touches
   production data → requires an explicit owner-approved migration plan.
3. **M3 — Write-side hygiene (separate PR).** CV extraction must stop
   writing title lines into `rico_users.name` and stop overwriting known
   profile values; write-path uses the same identity-name guard.

## Phase (M1 scope — this PR only)

- Resolver: active CV via `user_documents.is_primary` (through the
  existing `document_resolver`), latest-CV fallback labeled `"latest"`,
  conflicting primary flags surfaced, years provenance
  (profile vs primary CV) with conflict suppression of the absolute
  figure, identity-name guard (taxonomy + generic-role-token dominance).
- Wire points (both fail-soft to the legacy read on any resolver error):
  - `RicoChatAPI._build_openai_context` (`src/rico_chat_api.py:2469`) —
    injects `career_context` (active CV filename + source, years display
    + conflict + per-source values); on conflict removes the absolute
    `years_experience` from the AI context and instructs the model to ask
    for confirmation; flags an invalid identity name instead of showing it.
  - `RicoChatAPI._target_role_search_response`
    (`src/rico_chat_api.py:6053`) — years used for search context come
    from `resolve_career_context(...).display_years`.
- Out of scope (explicit owner boundary): context follow-up routing, chat
  sessions, analytics, retention, ranking, locale work, #1177, any data
  migration, any auto-overwrite of `rico_profiles` from CV extraction.

## PR

- Branch: `rico/canonical-career-context` (base `main` @ 38bf14a5).
- Draft. No auto-merge. Owner review required before merge; M2 data
  cleanup only after a separately approved plan.

## Task

- Ledger: `AI_WORKSPACE/TASKS.md` → TASK-20260719-020 (renumbered thrice
  during main-churn rebases: -017 was assigned to the WhatsApp task by
  the #1209 sync, then -018 to the sessions hotfix #1213, then -019 to the SSE-parity task by #1212).

---

## Evidence: reader/writer map (verified 2026-07-19)

### Active CV / `is_primary`

| Site | Role |
| --- | --- |
| `src/services/document_resolver.py` | Existing read resolver: `resolve_user_cv` precedence primary → latest → legacy profile `cv_filename`; `get_cv_candidates` (primary-first then newest). Before this PR its only src caller was the upload flow (`rico_chat_api.py:~2347`). |
| `src/rico_db.py:405-880` | Write side: `_lock_primary_slot` / `_promote_if_requested` / `save_user_document` / `set_primary_document` — primary switching is already atomic and user-scoped (FOR UPDATE on the primary slot; old primary cleared before the new one is set; at no point two `is_primary=TRUE` rows). |
| `src/rico_chat_api.py:2206-2360` | Uploaded-documents context builder + upload replies read `is_primary` to label "(active CV)". |
| `src/rico_identity.py:106` | Prompt contract: the model identifies the active CV as `is_primary: true`. |

### `years_experience`

- Readers (all funnel through `RicoChatAPI._profile_value(profile, "years_experience")`):
  search context (`rico_chat_api.py:6053` — now resolver-backed), AI
  context allowlist (`:2427`), profile report/summary sites (`:3339`,
  `:3470`, `:3502`, `:13752`, `:14105`, `:14188`, `:19786`), scoring
  paths (`:15983`, `:16422`, `:16530`, `:16806`, `:17179`),
  `role_normalization.py`, `cover_letter_writer.py`,
  `agent/context/resolver.py`.
- Writers: profile-update flow (`rico_chat_api.py:14350-14428`),
  onboarding, CV-parse profile write path.
- Storage: `rico_profiles` JSONB (`profile_repo._bundle_to_profile`),
  duplicated per `rico_users` row.

### Identity name

- Reader: `profile_repo` (name from `rico_users.name`) → every chat
  surface.
- Writer: CV parse wrote the CV title line into `rico_users.name`
  ("Vip Relationship Manager") on whichever duplicate row the bundle
  selection touched.

### Canonical source: PROOF THAT NONE EXISTS (pre-PR)

1. FIVE duplicate `rico_users` rows share one identity email (Neon,
   2026-07-19): `d45717cb` (name = "Vip Relationship Manager",
   years 8.0, updated today), `b1e024fd` (8.0), `cb8f9262` (10.0),
   `9c584f8a` (10, June 1 — the chat-history UUID), `d29dacc7` (10).
2. `rico_db.get_user_bundle` picks the canonical row with a 6-rule
   ORDER BY whose rule 5 is `updated_at DESC` — any CV upload floats the
   whole identity onto the row the parse touched last.
3. `user_documents.user_id` stores the EMAIL (shared across duplicates)
   while `rico_profiles` is row-scoped (fragmented) — so `is_primary`
   and the report's "active" marker can disagree by construction.

### Architecture boundary (owner ruling 2026-07-19)

- **`is_primary` is the active-DOCUMENT selector** — it answers "which CV
  is in force", nothing more. It is **not** a canonical user-identity
  source, and nothing in M1 treats it as one.
- **A matching email is not sufficient ownership/identity proof.** When
  more than one `rico_users` row matches the authenticated identifier
  (`rico_db.count_identity_rows`, same predicate as `get_user_bundle`),
  the identity is AMBIGUOUS: the resolver exposes
  `ambiguous_identity`/provenance state explicitly instead of silently
  trusting whichever row `updated_at DESC` floated to. Under ambiguity, a
  profile-sourced figure is displayable only when the email-scoped
  primary CV corroborates it, and the profile-row name is untrusted
  unless the user confirmed it (`name_confirmed`/`name_source="user"`).
- **Degradation is fail-SAFE, not fail-soft.** If resolution cannot be
  completed (document store error, unexpected failure), callers withhold
  absolute years and the unverified name and use neutral copy, logging a
  sanitized diagnostic (exception type only, never user data). The legacy
  read is what produced the incident — it is never the fallback.
- **M1 is a read-path consistency mitigation** — it makes the divergence
  impossible to display, it does not repair the data. **M2** resolves the
  duplicate identity/data rows themselves (owner-gated; production data).
  **M3** hardens all writers (CV parse must never write title lines into
  identity names or overwrite known values).

Conclusion: years/name have NO canonical source until M2. M1 therefore
exposes provenance, corroborates where it can, and refuses to guess.
