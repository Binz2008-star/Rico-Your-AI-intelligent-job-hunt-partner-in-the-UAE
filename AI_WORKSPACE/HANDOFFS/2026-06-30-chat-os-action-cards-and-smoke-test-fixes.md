# Handoff — Chat-OS Action Cards + Smoke-Test Fixes

**Date:** 2026-06-30
**Status:** COMPLETE — both PRs merged
**Production HEAD:** `e4979eb`

---

## What shipped

### PR #780 — Chat-OS: action cards for `application_status` and `prepare_application`
Merged at `6863409`.

Added two new action-card factories to `src/services/agentic_ui_composer.py`:

- `_application_status_actions()` → [View Application Flow (navigate /flow), Add application (chat_continue)]
- `_prepare_application_actions()` → [View Application Flow (navigate /flow), Find similar jobs (chat_continue)]

Both registered in `_RESPONSE_TYPE_ACTIONS`. Tests: 6 new unit tests in `tests/test_agentic_ui_composer.py`.

### PR #781 — Question-form routing + sidebar nav/count/plan fixes
Merged at `e4979eb`.

| Fix | Root cause | File(s) changed |
|---|---|---|
| Chat routing: "what are my applications?" returned AI prose | `_SHOW_MY_APPLICATIONS_RE` is imperative-only; question forms fell through to AI path | `src/rico_chat_api.py` — extended `_APPLICATIONS_LIST_RE` with 4 new question-form alternatives |
| No action cards on `application_list` type | `_RESPONSE_TYPE_ACTIONS` had no entry for `application_list` | `src/services/agentic_ui_composer.py` — added `"application_list": _application_status_actions` |
| BUG-1: sidebar count < /flow count | `useSidebarStatus.ts` summed only 5 statuses; backend has 10+ | `apps/web/hooks/useSidebarStatus.ts` — use `stats.total` from backend directly |
| BUG-4: sidebar nav injected chat queries | `chatPrompt` on nav items caused `/command?q=…` URLs from /command page | `apps/web/components/layout/app-nav.ts` — removed `chatPrompt` from all non-chat nav items |
| BUG-5: "Pro Plan / PREMIUM" label contradiction | Nav label "Pro Plan" clashed with plan badge showing `premium` | `app-nav.ts` label → "My Plan"; `AppSidebar.tsx` key → `navMyPlan`; `translations.ts` added `navMyPlan` EN + AR |

## CI history on PR #781

| Commit | CI result | Notes |
|---|---|---|
| `c1ea3f6` | ✅ QA Tests pass | Initial action cards (PR #780 content in PR #781 branch) |
| `d3eb49f` | ❌ QA Tests fail (3 failures) | Wrong approach: added question-forms to `_SHOW_MY_APPLICATIONS_RE`; broke 3 existing tests |
| `b2e93a8` | Not auto-triggered | Correct fix: reverted wrong regex; added question-forms to `_APPLICATIONS_LIST_RE` |
| `aafb9aa` | Not auto-triggered | BUG-1/4/5 fixes. Vercel ✅ |
| (manual trigger) | ✅ QA Tests pass | Manually dispatched `workflow_dispatch` on `aafb9aa`; all pass |
| `7db2e5c` | ✅ Vercel Ready | Merge-conflict resolution commit (main's #780 merge conflicted with branch's duplicate factory defs) |

**Conflict explanation:** PR #780 merged into main (`6863409`) while PR #781 was open. Both independently added `_application_status_actions`/`_prepare_application_actions` to `agentic_ui_composer.py`. Resolution: kept PR #781's added `application_list` mapping alongside main's existing entries; function bodies were identical (auto-merged cleanly).

## Remaining open bugs from 2026-06-30 smoke test

| ID | Priority | Description |
|---|---|---|
| BUG-2 | medium | Self-cancelling keyword filters (excluded keywords conflict with target keywords) |
| BUG-3 | medium | Duplicate board entry on /flow kanban |
| BUG-6 | medium | Status taxonomy mismatch between list view and kanban |
| BUG-7 | medium | Session hydration: logged-out appearance on first load |
| BUG-9 | low | Sidebar widgets disappear on /upload page |
| BUG-10 | low | Data quality: 30.0 yrs exp display, salary inconsistency |
| BUG-11 | low | Name casing inconsistency |

## Key files reference

- `src/rico_chat_api.py` — `_APPLICATIONS_LIST_RE` (line ~408), `_SHOW_MY_APPLICATIONS_RE` (line ~2559 approx)
- `src/services/agentic_ui_composer.py` — `_RESPONSE_TYPE_ACTIONS` dict, `_application_status_actions()`, `_prepare_application_actions()`
- `tests/test_agentic_ui_composer.py` — `TestApplicationListActions`, `TestApplicationStatusActions`, `TestPrepareApplicationActions`
- `apps/web/hooks/useSidebarStatus.ts` — pipeline total fix (uses `stats.total`)
- `apps/web/components/layout/app-nav.ts` — nav items (no `chatPrompt` on real-page destinations)
- `apps/web/components/layout/AppSidebar.tsx` — `NAV_ITEM_KEYS["/subscription"]` = `"navMyPlan"`
- `apps/web/lib/translations.ts` — `navMyPlan` key added in EN + AR sections

## Rollback

All changes are frontend-only (hooks, components, translations) + backend regex/composer (no schema, no migration, no env var). Rollback by reverting the squash commit `e4979eb` on main.
