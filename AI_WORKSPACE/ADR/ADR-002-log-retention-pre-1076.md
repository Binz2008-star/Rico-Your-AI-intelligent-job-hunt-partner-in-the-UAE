# ADR-002 — Retention of logs emitted before the #1076 log-privacy release

- Status: **ACCEPTED** (owner decision, 2026-07-17)
- Date: 2026-07-17
- Deciders: Owner (Roben)
- Context PRs/issues: #1076 (log privacy), merged as `907b404f` on 2026-07-17;
  related credential findings #1095 (reset tokens), #1084 (workflow secrets)

## Context

Until commit `907b404f` (PR #1140), operational logs and exported error events
could contain profile values, contact identifiers (email/phone/Telegram),
chat/document/search text, and bearer credentials (password-reset URLs with
tokens, Paddle checkout session tokens). The code paths are fixed from that
commit onward; this ADR governs what already left the system before the fix.

## Decision (verbatim, owner-approved)

> Logs and events emitted before commit 907b404f on 2026-07-17 must be treated
> as potentially containing PII or sensitive data. They must not be exported,
> migrated, or reused for analytics. They should expire under each platform's
> verified retention policy, with earlier deletion where safely available.

## Scope and application

- Applies to every sink that received application output before `907b404f`:
  Render service logs, Sentry events/breadcrumbs, GitHub Actions run logs, and
  any ad-hoc copies.
- Reset and checkout tokens in that window are treated as **credentials**, not
  merely profile PII (#1076 close-gate).
- Platform retention durations are **not asserted here**; they must be read
  from each platform's actual account settings before being relied upon.
- Historical log content must never be pasted into GitHub issues/PRs or any
  workspace document.

## Consequences

- No backfill, analytics import, or export tooling may consume pre-`907b404f`
  logs.
- Where a platform offers safe early deletion (e.g. clearing old Sentry
  events), it should be used; otherwise the data ages out naturally.
- From `907b404f` onward, `src/log_privacy.py` + the static guard in
  `tests/test_1076_log_privacy.py` are the enforcement mechanism, and
  production refuses to boot with any token-logging flag enabled.
