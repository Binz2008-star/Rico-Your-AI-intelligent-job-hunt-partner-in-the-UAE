# Rico Intelligence Phase 1

Owner decision (2026-07-14): the UI-unification program is closed
(`ATELIER_FULL_SITE_MIGRATION.md` §closure). From now on the priority is
**capability, not appearance**. This is the program control file for the
intelligence track.

## Sequence (owner-ordered; each Epic gates the next)

| # | Epic | One-line definition | Gate |
| --- | --- | --- | --- |
| 1 | **Career Memory Engine** | Rico's brain: who you are, what you want, what you rejected and why, what you learned, what changed, what Rico promised | **ADR-001** (`AI_WORKSPACE/ADR/ADR-001-rico-career-memory-engine.md`) must be owner-ACCEPTED before any code; then M1–M6 small PRs |
| 2 | **Application Intelligence** | Understand applications, not just store them — response rates, recurring gaps, actionable recommendations ("18 Operations apps, 6% response, PMP gap → target smaller firms for two weeks") | Epic 1 M3 (reader views) live |
| 3 | **Daily Executive Brief** | Every morning: what's new, what changed, what needs a decision, what to follow up, new opportunities, risks — an executive summary, not a report | Epic 1 M4 (summaries) live |
| 4 | **Autonomous Career Agent** | Proactive: follows up, suggests jobs, reminds, detects patterns, proposes CV improvements, learns from decisions — every action cites its memory justification and passes the safety approval gate | Epics 1–3 stable; separate owner go |

Explicitly NOT the first priority (owner ruling): Journey State, Daily Plan,
Follow-up features as standalone builds — they all become projections of the
Memory Engine.

## Standing rules for this program

Same discipline as the UI program: small reviewable PRs from latest `main`,
draft-first, owner approval per merge, additive-only migrations, synthetic
test data only, Product Generalization Rule, safety layer untouched, cost
rules (cheap-provider chain + keyword fallback for any summarization).

## Parked parallel track — /command UI completion (not scheduled)

Owner diagnosis 2026-07-14: `/command` is currently hybrid — new WorkspaceShell
chrome (#1020) around the old chat UI. Correct, expected from the phased split,
and **deliberately parked** to avoid another cosmetic week. When re-opened, it
runs as ONE program covering: 1) new composer, 2) new message design, 3) tool
cards (Jobs/CV/Applications), 4) thinking/streaming states, 5) attachments,
6) quick suggestions, 7) mobile polish — reference source: the owner's
`ricodesignreference` package (kit already in-repo under `components/ui/rico/`
+ `components/shared/`, byte-verified identical). Re-opening requires an
explicit owner instruction.

## Billing gate (outside this program, still open)

# 1022 (Paddle Setup-level eventCallback fix) merges only after a real browser

Sandbox smoke: checkout opens · cancel · successful payment · customer portal ·
webhook processing · USD 21.50 displayed correctly.
