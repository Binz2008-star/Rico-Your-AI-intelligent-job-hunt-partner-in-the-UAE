# Handoff — Profile Nudge + Render Cron Rollout

Date: 2026-06-20
Status: production hotfix live; cron remains active

## Executive summary

The profile-completion nudge rollout is now live and safe after the synthetic/internal recipient hotfix.

- PR #663 shipped the onboarding/profile-nudge feature set:
  - signup redirect to `/onboarding`
  - dashboard incomplete-profile banner
  - cron-guarded `POST /api/v1/pipeline/profile-nudge`
  - migration `029` adding `users.profile_nudge_sent_at`
- Manual production run before recipient filtering worked but sent 40 emails:
  - first run: `nudges_sent=40`, `nudges_failed=0`, `skipped=3`
  - second run: `nudges_sent=0`, `nudges_failed=0`, `skipped=0`
- Bounce investigation found synthetic/internal recipients:
  - `test_user_####@ricohunt.com`
  - `info@ricohunt.com`
- PR #665 hotfixed recipient eligibility and is merged to main:
  - squash commit: `8200811fdf93196cbb646b73a77e34ee934d641c`
  - merged at: 2026-06-20T08:59:56Z
  - changed files:
    - `src/services/profile_nudge_service.py`
    - `src/schemas/pipeline.py`
    - `tests/unit/test_profile_nudge_synthetic_guard.py`
- Production Render endpoint confirmed #665 live by returning the new field:

```json
{"status":"ok","nudges_sent":0,"nudges_failed":0,"skipped":0,"skipped_synthetic":0}
```

This proves the deployed service includes #665 because `skipped_synthetic` did not exist before that PR.

## Current Render cron state

Render audit reported these live services:

- `rico-job-automation-api` — web service, active
- `rico-followup-reminders` — cron service, active
- `rico-profile-nudge-daily` — cron service, active
- workers: 0

Profile nudge daily cron:

```text
Schedule: 0 5 * * *
Timezone meaning: 05:00 UTC = 09:00 UAE
Command: curl -fsS -X POST "https://rico-job-automation-api.onrender.com/api/v1/pipeline/profile-nudge" -H "X-Cron-Secret: $RICO_CRON_SECRET"
```

Important command rule: keep double quotes around the header so `$RICO_CRON_SECRET` expands in the shell. Do not change to single quotes.

Follow-up reminder cron remains separate:

```text
Schedule: 0 4 * * *
Endpoint: /api/v1/pipeline/reminders
```

## Recipient filtering now live

#665 blocks and stamps without sending:

- any `@ricohunt.com` address by default, including `info@ricohunt.com`
- local parts starting/matching obvious synthetic patterns:
  - `test`
  - `test_user`
  - `dummy`
  - `demo`
  - `example`
  - `seed`
  - `fake`
  - `user_<digits>`

For excluded recipients:

- `profile_nudge_sent_at` is stamped
- `send_email` is not called
- `skipped_synthetic` increments
- logs avoid full private email addresses

Normal real external emails remain eligible.

## Render workflow policy

Use Render-related workflows this way:

| Workflow | Role |
|---|---|
| `.github/workflows/deploy-render.yml` | Force backend redeploy after merge only when Render auto-deploy does not pick up latest main |
| `.github/workflows/render-audit.yml` | Read-only verification of Render services, env-key presence, deploy history, health, route probes, and cron count |
| `.github/workflows/render-cleanup2.yml` | Do not use unless explicitly approved; it can delete non-prod services / disable previews |
| `render.yaml` | Declarative Render service config; currently `plan: starter` |

Do not trigger fresh deploys unless needed after a merge. Do not use `render-cleanup2.yml` during normal rollout verification.

## Render audit known issues to fix separately

Open a small follow-up PR only after the hotfix is stable. Scope:

- print real live Render deploy commit SHA from the deploys API
- fix env-var API limit from `200` to `100`
- fix suspended handling so `"not_suspended"` is treated as active
- remove stale summary boilerplate such as “No cron jobs exist” and old “plan free → starter” wording
- keep audit read-only: GET requests only, no deploy triggers, no deletes, no env value logging

Do not mix these audit fixes with runtime code.

## Verification already completed

- PR #665 merged and closed
- GitHub QA Tests green before merge
- Render production endpoint returned HTTP 200
- `X-Cron-Secret` accepted from Render shell environment
- Response included `skipped_synthetic`, confirming #665 live
- No additional emails sent in the final verification run

## Open items / do not forget

1. Run or review `render-audit.yml` after the hotfix settles to document final cron count and deploy status.
2. Open separate PR for render-audit fixes listed above.
3. Leave PR #640 (`feat/password-complexity`) on hold until explicitly approved.
4. Do not run manual profile-nudge curl repeatedly; daily cron is active and should handle normal operation.
5. If bounces continue, inspect whether new synthetic recipients were created after #665 or if there are external invalid addresses not covered by the synthetic guard.

## Rollback plan

If the profile nudge cron causes unexpected email behavior:

1. Suspend `rico-profile-nudge-daily` in Render.
2. Do not delete the cron unless instructed; suspend is safer for quick restore.
3. Revert #665 only if the guard itself breaks normal delivery; otherwise keep #665 because it is protective.
4. Re-enable cron after validating `POST /api/v1/pipeline/profile-nudge` returns expected counters.
