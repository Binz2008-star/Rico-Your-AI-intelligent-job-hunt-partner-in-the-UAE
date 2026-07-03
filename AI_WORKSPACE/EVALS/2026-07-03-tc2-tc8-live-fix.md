# Live-path root cause + fix: TC-2 target propagation, TC-8 interview prep (2026-07-03)

- Method: ran the **real** classifier, router, extractor, and dispatch code in
  this environment (pure-Python layers) and mirrored the DB field whitelist. The
  container cannot reach live Neon / JSearch / DeepSeek, so provider results and
  final LLM text still need a live re-test; every root cause below was confirmed
  by running the actual code, not by reading it.
- Rule honored: instrument first, no blind regex/weight edits. Each fix is
  backed by a reproduction and a regression test.

---

## TC-2 — target-role propagation (exact root cause)

**Symptom (live):** user confirms new targets `ESG Manager` + `Compliance
Manager`; the next search still returns Operations/Admin roles and later reverts
to "5 matches for Operations Manager."

**Root cause — two defects in the live path, both reproduced:**

1. **Classifier plural gap.** `intent_classifier._PROFILE_UPDATE_RE` matched
   `\brole\b` / `\btitle\b` — *singular only*.
   - `"update my target role to ESG Manager"` → `profile_update` ✓
   - `"update my target roles to ESG Manager and Compliance Manager"` → **`unknown`** ✗
   The exact repro sets *two* roles, so it fell through to `unknown` and never
   reached the profile-update handler → nothing was staged or saved.

2. **Extractor + persist mismatch.** Even when correctly classified, the router
   (`rico_intent_router`) emitted a singular `preferences["target_role"]`. But
   `RicoProfile` has **no** `target_role` field — the canonical field is
   `target_roles` (a list). `upsert_profile`'s field whitelist therefore
   **silently dropped** the value (BUG-08 class). The user saw "Saved" while
   nothing persisted. The plural message extracted *nothing at all*.

Net: the confirmed targets never reached the DB, so the next search read the
stale `Operations` profile → the reversion.

**Note:** the ranking layer is *not* implicated. Prior trace
(`2026-07-03-tc2-tc8-path-trace.md`) already showed `rank_by_profile_fit` orders
ESG/Compliance correctly *when given the right targets*. This fix makes the right
targets actually arrive.

### Before → after (measured here)

| Input | Before | After |
|---|---|---|
| `update my target roles to ESG Manager and Compliance Manager` | intent=`unknown`; prefs `{}`; persisted `{}` | intent=`profile_update`; prefs `{target_roles:[Esg Manager, Compliance Manager]}`; **persisted** `{target_roles:[…]}` |
| `set my target role to ESG Manager` | prefs `{target_role: Esg Manager}` → **dropped** by whitelist | prefs `{target_roles:[Esg Manager]}` → **persisted** |
| `I want to target ESG Manager and Compliance Manager roles` | `job_search_multi_role` | `job_search_multi_role` (unchanged — still a search) |

### Fix

- `src/agent/intelligence/intent_classifier.py` — `_PROFILE_UPDATE_RE`:
  `role|title` → `roles?|titles?`.
- `src/rico_intent_router.py` — `_PREFS_PATTERNS` plural; `_extract_entities`
  parses a multi-role clause into `entities["target_roles"]` (new
  `_split_target_roles` helper); `_build_tool_args` emits the canonical
  `preferences["target_roles"]` **list** (never the dropped singular key).

### Still needs live verification

- End-to-end on `ricohunt.com/command`: confirm two roles → run search → the
  provider query + `rank_by_profile_fit` use the new targets and top-5 is
  ESG/Compliance-aligned. (Persistence is unit-verified against the whitelist;
  provider behavior is not reachable here.)

---

## TC-8 — interview prep (exact root cause)

**Symptom (live):** "prepare me for an interview for the Retail Operations
Manager role at Richemont" returned unrelated Richemont openings (Field Service
Engineer II, ServiceNow Developer) instead of preparing for that role.

**Root cause — dispatch/grounding, not classification (reproduced):**

- The classifier already returns `interview_prep` for every variant of the
  phrase (verified). So this is **not** a classification bug.
- The `interview_prep` dispatch (`rico_chat_api.py`, `legacy_intent ==
  "interview_prep"`) sent the **raw message straight to the AI provider** with no
  grounding: it never parsed the role/company and never checked tracked
  applications. The result is entirely at the model's discretion (and, if
  production lags `main`, an older path routed the company token to a search).
- Two `_handle_interview_prep` methods existed; the later (static, keyed off
  `profile.target_roles[0]`) **shadowed** the earlier richer one, which was dead
  code. Neither parsed the company/role or looked up a tracked application.
- The regex fast-path (`_INTERVIEW_PREP_RE`) does **not** match this phrasing
  ("prepare me for an interview for … at …"), so the message reaches the LLM
  dispatch, confirming the grounding gap is the live path.

### Fix

- Removed the dead duplicate `_handle_interview_prep` (one active handler now).
- Added a deterministic resolver: `_extract_interview_context` (role + company
  from the message), `_match_tracked_application` (match a tracked app by
  company/role), `_resolve_interview_prep_target` (role = message → tracked →
  profile), and `_build_interview_prompt_override`.
- The `interview_prep` dispatch now passes a **grounded prompt** to the AI that
  pins the exact role/company, tailors to a tracked application when one exists,
  states plainly when the role is **not** tracked, and **forbids listing job
  openings** ("this is coaching, not a job search"). Response carries
  `target_role` + `company`. All wrapped in try/except so it degrades to the
  prior behavior on any error.

### Before → after (measured here)

| | Before | After |
|---|---|---|
| Role/company parsed | none | `("Retail Operations Manager", "Richemont")` |
| Tracked-app lookup | none | matches a tracked Richemont role when present |
| Prompt to model | raw message | grounded: pins role+company, "Do NOT list openings", tracked/not-tracked note |
| Duplicate handler | 2 (one dead/shadowed) | 1 |

### Still needs live verification

- The final AI **text** (needs DeepSeek/OpenAI). The grounding *inputs* are
  unit-verified; the model's adherence to "prep for this role, don't list
  openings" should be confirmed on the live stack.

---

## Tests

- `tests/test_tc2_target_role_propagation.py` — 8 tests (classifier plural,
  multi-role extraction, whitelist persistence, splitter).
- `tests/test_tc8_interview_prep_grounding.py` — extraction, tracked-match,
  grounded-prompt, resolver (tracked/not), single-handler guard.
- Regression: `tests/unit/test_intent_router.py`, `test_bug04_profile_mutation`,
  `test_bug08_city_declaration`, `test_followup_fast_path`,
  `test_agentic_ui_composer/schema`, `test_profile_query_intent` all green.

## Environment note

This container lacked several runtime deps (`pydantic`, `psycopg2`, `filelock`,
`rapidfuzz`, …) that had to be installed to run the suites; a few unrelated test
modules fail to *collect* due to native-extension (`pyo3`) panics. These are
pre-existing environment issues, independent of this change.
