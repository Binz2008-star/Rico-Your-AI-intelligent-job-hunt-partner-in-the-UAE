# Proposal: Rico Personalized Job Alert Emails

Status: approved (owner: roben.edwan.26@icloud.com — "Yes and started")
Branch: `claude/rico-job-alert-emails-6fugqq`
Author: AI (planner → coder)
Date: 2026-07-01

Rico should email opted-in users personalized UAE job opportunities based on
their profile, CV-derived roles, target roles, preferred cities, excluded
keywords, saved searches, and application history — daily or weekly, with an
unsubscribe link and no spam.

---

## 1. Foundation investigation — what already exists

The Telegram job-alert system is an almost line-for-line blueprint for email,
and the profile-nudge email sweep is a working template for a cron-driven,
idempotent email job. ~80% of the parts already exist.

| Concern | Where | Reuse verdict |
|---|---|---|
| Notification settings | `settings.notifications` JSONB (`migrations/005`); `RicoAgentSettings` flags (`src/rico_agent.py:15`); opt-in/out endpoints (`src/api/routers/settings.py:67`) | Reuse pattern; **no email flag yet** |
| Saved searches / run tracking | `rico_saved_searches` + `profile_repo.save_search` (`src/repositories/profile_repo.py:444`); `pipeline_runs` (`migrations/005:59`) | Optional match source + run audit |
| Profile fields | `RicoProfile` (`src/rico_agent.py:31`): target_roles, preferred_cities, salary_expectation_aed/minimum_salary_aed, skills, industries. CV-derived roles merged into target_roles via `role_normalization` (`profile_repo.py:193`). Excluded keywords: `user_exclude_keywords` + `settings.exclude_keywords` | Fully reusable |
| Matching / scoring | `src/scoring.py:549` `score_jobs_for_user`; `rico_repo_adapter.run_for_profile` (search+score); `jsearch_client.search` | Reuse as match engine |
| Applied/saved/hidden | `user_job_context` + `user_job_context_repo.get_by_status` (`:498`) | Exclusion source |
| Email sender | `src/services/mailer.py` `send_email`; templates in `password_reset_email.py`, `verification_email.py`, `profile_nudge_service.py` | Reuse; **plain-text only** |
| Telegram alert logic | `src/services/telegram_alert_service.py` (`broadcast_job_alerts_to_subscribed_users`, dedup, `MAX_ALERTS_PER_DAY=5`); `telegram_alert_log` (`migrations/023`) | **Direct template** |
| Unsubscribe / preference | Telegram opt-in/out endpoints; nudge email "reply unsubscribe" | Pattern exists; **no email token/link** |
| Scheduler / cron | GitHub Actions cron (`daily.yml`); cron-guarded `POST /api/v1/pipeline/reminders` & `/profile-nudge` via `require_cron_secret` (`pipeline.py:44`) | **Direct template** |
| Tables for alert runs | `telegram_alert_log` (exact analog), `pipeline_runs`, `user_job_context` | Reuse schema shape |

### Missing (must build)
1. Email opt-in flag (rides in `RicoAgentSettings` JSONB — no migration).
2. `email_alert_log` table (dedup + cap; clone of `telegram_alert_log`).
3. Unsubscribe token + one-click, login-free link.
4. Frequency preference (daily/weekly).
5. HTML email rendering (`mailer` is plain-text).
6. Email broadcast orchestrator (analog to `broadcast_job_alerts_to_subscribed_users`).
7. Cron endpoint `POST /api/v1/pipeline/job-alert-emails` + GitHub Action.
8. Arabic/English localization (MVP: English only).

### Verdict
- **DB migration needed?** Yes, minimal: `email_alert_log` + `email_unsubscribe_tokens`. Opt-in + frequency ride in existing `settings` JSONB (no schema change).
- Match engine, sender, cron pattern, dedup pattern, profile fields, exclusion data all already exist.

---

## 2. Engineering plan

### Data source
- Profile via `profile_repo.get_profile` (target_roles already include CV-derived roles).
- Opt-in + frequency from `RicoAgentSettings` (`can_receive_email_alerts`, `email_alert_frequency`).
- Excluded keywords honored inside `score_jobs_for_user`.
- Exclude applied/saved/hidden via `user_job_context_repo.get_by_status(user_id, ["applied","saved","skipped","blocked"])`.

### Matching
- Candidates via `rico_repo_adapter.run_for_profile` or `jsearch_client.search` + `score_jobs_for_user`.
- Threshold: reuse `settings.min_score` / `score_threshold_watch` (default 50).
- Dedupe: skip `(user_id, job_key)` already in `email_alert_log`; `job_key` from `src.applications.get_job_id`.
- Frequency cap: one email per user per period, enforced via `email_alert_log`.

### Email content
- 3–5 jobs: title, company, location, salary, match %, one-line "why" (`job_match_explanation`).
- CTAs: View in Rico, Save, Prepare CV, Track — deep links to existing pages. Footer unsubscribe link.
- English MVP; copy behind a dict so Arabic (RTL) can follow.

### Sending rules
- Opt-in only (default off). Daily or weekly. Unsubscribe in every email.
- No send if no strong matches. Optional plan-limit hook (`subscription_gating`).

### Technical design
- Cron-guarded `POST /api/v1/pipeline/job-alert-emails` (`require_cron_secret`) driven by a GitHub Action.
- `src/services/email_alert_service.py` — `run_email_alert_sweep()` + `send_alert_email(user)`.
- `mailer.send_email` extended with optional HTML.
- Templates `src/templates/email/job_alert.{html,txt}`.
- `email_alert_log` + unsubscribe-token tables.
- Stamp-before-send idempotency (like `profile_nudge_service.py:203`); run summary counts.

### Safety / compliance
- One-click tokenized unsubscribe (no login). Frequency cap + dedup. No CV text/PII in body.
- Only jobs with a real apply/source URL (reuse `verification_status`). Reuse `_is_synthetic_email` guard.

### MVP scope
- Daily email to opted-in users, 3–5 matched jobs, English only, no auto-apply, drop-if-no-strong-matches.

### DB tables/fields
- New: `email_alert_log`, `email_unsubscribe_tokens`. No migration for opt-in/frequency (settings JSONB).

### API / admin controls
- `POST /api/v1/settings/email/opt-in` · `/opt-out` · `GET /email/status`.
- `GET /api/v1/email/unsubscribe?token=…` (public).
- `POST /api/v1/pipeline/job-alert-emails` (cron-guarded; `?dry_run=true`).

---

## 3. Rollout (staged PRs)

- **PR-1 (this branch — plumbing, NO sending):** migration `033` (both tables) + `mailer` HTML +
  `RicoAgentSettings` email fields + `email_notifications` service (opt-in/out/token) +
  opt-in/out/status endpoints + public unsubscribe endpoint + tests. Additive; zero user-facing behavior change.
- **PR-2:** `email_alert_service` + cron endpoint + templates, gated behind opt-in (default off) and a
  `RICO_ENABLE_EMAIL_ALERTS` kill-switch; validate with `dry_run=true`.
- **PR-3:** enable GitHub Action cron; monitor `email_alert_log`; then Arabic localization.

## Risks
- Plain-text → HTML deliverability (inherit SPF/DKIM from reset emails).
- SMTP rate limits on large lists → batch + per-run cap.
- Weak match quality → strict threshold + drop-if-empty.
- Unsubscribe must be reliable and login-free (CAN-SPAM/GDPR).

## Rollback
- Runtime code: revert PR. Migration: additive/idempotent, code tolerates missing tables (degrades). Cron (PR-2+): disable the workflow.
