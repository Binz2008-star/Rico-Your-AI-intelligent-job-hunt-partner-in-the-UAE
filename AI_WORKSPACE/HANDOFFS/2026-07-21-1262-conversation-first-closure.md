# Handoff — Issue #1262 conversation-first migration: CLOSED (phases 1–7)

Date: 2026-07-21
Author: Claude (session `claude/rico-system-audit-324rkq`)
Status: complete — all phases merged to `main` and production-verified via
`deploy-render`'s own gate (deployed-SHA match on `/version` + `/health` 200).

## Owner directive

> «ريكو كيان ذكي يعلم كل ما يدور حوله — يجب أن يخاطب وينفذ من خلال المحادثة.
> لغِ البطاقات والأزرار، خلّ ريكو يتكلم وينفذ أمام المستخدم.»

## What shipped, per phase

| Phase | PR | Merge SHA | Summary |
|---|---|---|---|
| 1 | #1258 | `1dcb0595` | Scheduled-search offer as an opt-in sentence (the idiom: spoken at message build, bilingual, per-user gated, suggested phrase cross-pinned to its deterministic intent). |
| 2 | #1265 | `e1cfe614` | Navigation cards → spoken markdown pointers (`[your jobs board](/flow)`, `/profile`, save/application pointers). |
| 3 | #1268 | `9fbd32c0` | Suggestion cards retired; save-search became a real conversational flow — and fixed the latent mis-route where "save this search for X" was swallowed by the save_job regex. |
| 4 | #1270 | `0581ca97` | Delete-saved-jobs Yes/No buttons → STRICT spoken confirm (`_is_delete_confirmation`: literal delete-verb phrases only — "yes, delete" / «نعم احذف»; loose "ok"/"sure"/«يلا» re-prompt). Tightened the previous `_is_affirmative` gate. |
| 5 | #1272 | `3f5f54a9` | Job-card SAVE/SKIP buttons retired; ordinal skip ("skip the first one" / «تجاهل الوظيفة الأولى») became deterministic (was AI fallback); results message speaks the how-to. Apply posture verified unchanged: external link on the card, agent_runtime approval gate on chat apply, no auto-apply. |
| 6 | — | — | Closed by owner decision DEC-20260721-002: the Refine drawer stays a structured UI action (P1 guarantee: UI wording never reaches the intent router). |
| 7 | (this PR) | — | Cleanup: dead `cmdMatchSave`/`cmdMatchSkip` translation keys removed (EN+AR); decision + this handoff recorded; Issue #1262 closed. |

## What deliberately remains non-conversational

- **Refine drawer** (`open_drawer` on job_matches) — DEC-20260721-002.
- **Real affordances**: apply/source external links, `JobFallbackActions`
  link/copy chips (degraded-link surface), Mark-as-Applied follow-up (its
  payload routes through the deterministic pre-classifier mark-applied path).
- **Runtime safety artifacts**: `permission_request` (approve/cancel) and any
  agent-attached `actions` from `RuntimeResult.data` — the composer's
  runtime-artifact merge is unchanged; `navigate` stays a valid wire kind.

## Safety invariants (unchanged in strength, now spoken)

- Apply requires explicit approval (`RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS`);
  bulk apply blocked; **no auto-apply anywhere**.
- Destructive delete requires a literal delete-verb phrase inside a 2-minute
  window; cancelling stays loose (fail-safe direction); #764 read-after-write
  guard intact.
- Guests keep sign-in prompts (save-search, scheduled-search, actions).
- Transcript parity: every spoken offer/pointer/instruction is part of the
  persisted message; every suggested phrase is cross-pinned in tests to its
  deterministic route (`tests/test_1262_conversational.py` is the map).

## Where the coverage lives

- `tests/test_1262_conversational.py` — classification, offer, gate, dispatch
  and cross-parity pins for phases 3–5.
- `tests/test_delete_saved_jobs_chat.py` — strict-gate suite (phase 4).
- `tests/test_agentic_ui_composer.py` — retired families pinned to `None`;
  job_matches pinned to refine-only.
- `tests/test_1249_scheduled_search.py` — phase-1 offer + phase-2 pointer pins.
- `apps/web/e2e/refine-search-structured.spec.ts` — refine-only card contract,
  spoken save offer, typed-phrase wire assertion.
- `apps/web/__tests__/command-job-match-card-atelier.test.tsx` — buttons-absent
  pin; RTL suites sync on localized markers.
