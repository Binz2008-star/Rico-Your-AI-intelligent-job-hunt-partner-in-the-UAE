# Live-path wiring follow-up: TC-2 search default + TC-8 dispatch hijack (2026-07-03)

Follow-up to `2026-07-03-tc2-tc8-live-fix.md` (PR #834). Owner's live re-test on
`/command` showed the new contracts **persist** but were **not used** by the
dispatched paths. Two legacy-path defects found by running the real code; both
are pure dispatch/wiring (no scoring/weights). Stacked on PR #834.

## TC-2 — bare search ignores the freshly-confirmed targets

**Live symptom:** after confirming `ESG Manager` + `Compliance Manager`,
"search for jobs now" still returned Operations/Admin and then "5 matches for
Operations Manager".

**Root cause (reproduced):** `"search for jobs now"` classifies as
`job_search_explicit` with **no** extracted role. Its dispatch
(`rico_chat_api.py`, `legacy_intent == "job_search_explicit"`) resolves the role
in this order:

1. explicit role in the message — none here;
2. **`ctx["recent_search_role"]` / `recent_role` / `recent_job`** (cached from a
   previous search) → **returns immediately**;  ← the bug
3. only then the profile's `target_roles`.

So a stale `recent_search_role = "Operations Manager"` (cached by the prior
search at the `ctx["recent_search_role"] = search_role` write) shadowed the new
ESG/Compliance targets. `target_roles` was correct in the profile but never
consulted.

**Fix:** when a target-role change is confirmed (`confirm_profile_update`
branch), invalidate the cached search role
(`recent_search_role`/`recent_role`/`recent_job`). The next bare "search for jobs
now" then falls through to the new `target_roles`. Non-role updates (e.g. a city
change) leave the continuity cache intact.

Contract now honored: *when targets are explicitly updated and confirmed, the
next search uses those targets unless the user names a different role.*

## TC-8 — interview-prep message hijacked by the company-openings search

**Live symptom:** "prepare me for an interview for the Retail Operations Manager
role at Richemont" returned Richemont openings (Field Service Engineer II,
ServiceNow Developer), not interview prep — even though PR #834 added a grounded
interview-prep path.

**Root cause (reproduced):** the company-openings fast-path
(`_COMPANY_SEARCH_RE` → `_handle_company_search`) runs **before** the
`interview_prep` dispatch, and its pattern `\brole\s+at\s+[A-Z]` matches
**"…Manager role at Ri**chemont"**. So the message was intercepted as a company
job search and never reached the grounded interview path. (This is the same
verb-blind class as the original TC-8 finding — a role/company token forcing a
search.)

Measured: `_COMPANY_SEARCH_RE` matches `"role at Ri"` in the interview message;
`"find jobs at ADNOC"` still matches (correct).

**Fix:** guard the company-search dispatch with `_INTERVIEW_REQUEST_RE` — an
interview-prep request ("prepare/practise … interview", "for an interview",
"interview prep/questions", Arabic equivalents) is coaching, not a job search, so
it falls through to the grounded `interview_prep` path. Genuine company searches
("find jobs at ADNOC", "openings at Emirates NBD") are unaffected.

## Verification

- `tests/test_tc2_tc8_wiring.py` — company-search guard (interview vs. genuine
  search) + confirm-clears-recent-search-role (and leaves it intact for non-role
  updates).
- Regression green: `test_bug04_profile_mutation`, `test_followup_fast_path`,
  `test_continuation_intent`, `test_search_confirmation_routing`,
  `test_job_search_action_contract`, `test_intent_router`,
  `test_bug12_arabic_search_locale`, plus the PR #834 suites (1200+ total).
- Still recommended: a live re-run of both `/command` sequences to confirm
  provider results and AI text under the corrected dispatch.

## Note

Stacked on `claude/tc2-tc8-live-path-fix` (#834): the TC-2 clear only matters once
target roles persist (#834), and the TC-8 guard hands off to the grounded
interview path (#834). Merge #834 first.
