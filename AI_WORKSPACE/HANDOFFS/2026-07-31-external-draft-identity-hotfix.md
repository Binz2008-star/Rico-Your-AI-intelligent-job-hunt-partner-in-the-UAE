# External Draft Identity Guard — 2026-07-31

## Why this exists

Production chat generated an Arabic HR follow-up draft containing an unconfirmed candidate name and phone number. When challenged, Rico asserted that the name came from registered account data without proving that provenance from the current model context.

This is a user-trust incident: external professional drafts must not silently publish stale, conflicting, or unconfirmed identity/contact details.

## Governance mapping

- **Vision:** Rico as an AI Career Operating System
- **Epic:** AI Response Reliability & Performance
- **Milestone:** Grounding integrity and user-trust containment
- **Phase:** P1 production hotfix
- **Task:** `TASK-20260731-003`
- **PR:** `#1477` (Draft)
- **Branch:** `fix/external-draft-identity-guard`
- **Base:** `3bcac4d5d418b3711b71976733b4baf3d6876570`
- **Owner:** Rico Engineering

## Objective

Add one provider-agnostic rule that prevents Rico from treating saved profile or parsed-CV identity/contact fields as automatically approved for recruiter emails, cover letters, HR follow-ups, signatures, or other drafts intended to leave Rico.

## Scope

- Add `EXTERNAL_DRAFT_IDENTITY_RULE` to the shared grounding contract in `src/rico_identity.py`.
- Deliver the same exact rule to primary OpenAI-compatible providers and the HuggingFace fallback.
- Require placeholders or omission when identity/contact values are not explicitly confirmed for the current draft.
- Require one concise confirmation question when profile and parsed CV values disagree.
- Forbid unsupported provenance claims such as “registered account data” or “from your CV” unless the current context proves that source.
- Add focused regression tests and enroll them in required CI.
- Keep the existing primary-prompt grounding-order regression synchronized with the intentional addition of the external-draft rule.

## Explicit exclusions

- No profile or Career Profile mutations.
- No migrations or Neon changes.
- No automatic correction of the user’s stored name, phone, email, or LinkedIn URL.
- No timeout/retry or “server waking up” reliability changes; that is a separate incident.
- No broad prompt rewrite.
- No Review UI.

## Acceptance criteria

1. The primary provider system prompt contains the exact shared external-draft identity rule.
2. The HuggingFace fallback system prompt contains the same exact rule.
3. The contract names `name`, `email`, `phone`, and `linkedin_url` as unapproved-by-default for external drafts.
4. Unconfirmed values require a neutral placeholder or omitted signature/contact block.
5. Conflicting profile/CV identity requires a confirmation question, not silent selection.
6. Provenance answers cite only an exact source present in context; otherwise Rico states that the source cannot be verified.
7. Existing grounding, filename, safety-constraint, provider-cascade, frontend, and Postgres tests remain green.

## CI finding and bounded repair

The first QA run after synchronization with `main` completed with `6192 passed`, `1 skipped`, and one failed regression assertion. The failure was not an implementation failure: `tests/test_ai_grounding_contract.py` still expected the pre-change numbering where the untrusted-metadata rule was item 10. Adding the external-draft identity rule intentionally moved the shared grounding rules to items 9–12.

The regression now asserts the complete ordered sequence:

1. Identity integrity.
2. External-draft identity.
3. Untrusted metadata.
4. User safety constraints.

No runtime behavior was relaxed to satisfy the test. Exact-head CI must complete successfully before this Draft can be considered merge-ready.

## Risks and residual debt

This hotfix strengthens the shared provider contract but does not yet create a server-owned confirmation envelope for each identity/contact field. Prompt enforcement is therefore containment, not the final deterministic architecture.

Follow-up work should introduce an `external_draft_identity` context envelope with exact value, source, confirmation state, and conflict state, then add server-side output validation for external drafts. That work must be a separate PR because it changes the data contract and conversation state model.

## Rollback

Revert the eventual squash merge commit. No database, migration, environment, or user-data rollback is required.

## Required production smoke after merge

1. Ask in Arabic and English for an HR follow-up draft while profile name/phone exist but are not confirmed for the draft.
2. Verify no name, phone, email, or LinkedIn value is inserted; placeholder or unsigned draft only.
3. Explicitly confirm one exact name for the draft and regenerate; verify only that exact value appears.
4. Ask where the name came from; verify Rico cites the exact confirmed source or says it cannot verify the source.
5. Test conflicting profile/CV names; verify Rico asks one confirmation question instead of choosing.
