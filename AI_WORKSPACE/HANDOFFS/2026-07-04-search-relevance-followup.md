# 2026-07-04 — Search relevance follow-up

## Current status

- Product Generalization Rule is live on main from PR #843.
- Explicit-title search relevance floor is live in production from PR #844.
- Production commit verified: `91c14fc9ed395c8bab3ca9c5be77cc8741b15d10`.
- PR #845 was closed unmerged as duplicate scope drift.

## Investigation summary

Three separate follow-up issues were identified after production smoke testing.

### A — stale search cards

Persisted assistant history can contain full `job_matches` payloads, including old match arrays. The frontend can rehydrate those persisted matches and render them as active cards. A stale card from before PR #844 is historical and should not be treated as a fresh backend result.

### B — requested location display

The pending confirmation path preserves the requested location for the search, but the response text in `_target_role_search_response` can still use profile preferred cities instead of the requested location. Display text should use the requested location when present and fall back to profile cities only when no location was requested.

### C — explicit search routing fallback

A mixed-language explicit job-search request can enter the explicit search branch, capture location, but fail to populate `intent_result.extracted_role`. In that case it can fall through to the generic profile-based `run_for_profile` path. That bypasses the PR #844 explicit-title floor, drops requested location, and emits the generic strong-matches message.

## Next scoped implementation task

### TASK — Explicit-search routing plus requested-location display

Status: scoped
Owner: next implementation agent
Branch: TBD
Issue/PR: TBD

#### Objective

Implement the smallest safe fix for B and C only.

1. Specific role/title searches that include a requested location must route to `_target_role_search_response` instead of the generic profile-search path when a role can be resolved from the message.
2. `_target_role_search_response` must display the requested location when present.

#### In scope

- `src/rico_chat_api.py` explicit job-search routing.
- `_target_role_search_response` location display text.
- Offline unit tests using synthetic users and synthetic jobs.

#### Out of scope

- Stale history rendering.
- Exact-vs-related labeling.
- Timeout or cold-start handling.
- Primary-link UX.
- Guest/public route wiring.
- Batch scorer bias cleanup.
- Provider, database, environment, migration, or frontend changes unless strictly required for this scoped fix.

#### Acceptance criteria

- [ ] Mixed-language explicit role + city reaches `_target_role_search_response`, not `run_for_profile`.
- [ ] The generic `strong UAE job matches` message is not emitted for this explicit-title path.
- [ ] Requested location is preserved in response text even when profile preferred cities differ.
- [ ] Off-profile confirmation flow preserves the requested location after confirmation.
- [ ] Existing PR #844 relevance-floor tests remain green.

#### Required tests

- [ ] Mixed-language explicit role + city with empty classifier role still routes to the floored explicit-title path.
- [ ] Requested city display overrides profile preferred city.
- [ ] Off-profile confirmation preserves requested region/city in reply text after confirmation.
- [ ] Regression: no generic strong-matches message for this explicit-title path.

#### Product generalization

This task is global and data-driven. The smoke test exposed the bug, but the fix must apply to all roles, all requested locations, all users, and supported languages. Do not hardcode one role, one city, one account, or one sampled dataset.

## Deferred follow-ups

Handle separately, one PR each:

1. Exact-vs-related labeling for family/adjacent roles.
2. Stale history rendering for persisted search cards.
3. Search timeout/cold-start handling.
4. Primary-link blocked UX cleanup.
