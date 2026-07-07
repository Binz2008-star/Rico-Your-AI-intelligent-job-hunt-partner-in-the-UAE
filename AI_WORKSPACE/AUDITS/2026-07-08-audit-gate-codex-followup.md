# Codex follow-up — Production hardening audit gate

Status: merged follow-up note

This note records the two Codex findings on the audit gate and the required correction for future agents.

## Finding 1 — Smoke users

Authenticated production smoke must not be treated as generally authorized by the audit gate.

Default rule:

- Use synthetic users and synthetic profile data by default.
- Do not mutate real users.
- Do not perform authenticated production smoke against a real owner/user account unless the owner explicitly approves that specific smoke run.
- Do not print or store passwords, tokens, cookies, or session values.
- Any smoke that writes job context, saves jobs, marks applications applied, or changes profile data must be isolated to synthetic/smoke data.

## Finding 2 — Workspace entrypoints

The audit gate must be visible from normal workspace entrypoints.

Canonical audit document:

```text
AI_WORKSPACE/AUDITS/2026-07-08-production-hardening-audit.md
```

Agents should read this audit before starting feature, redesign, worker, notification, or infrastructure work.

## Active principle

Rico must never forget what it found, what the user opened, what was applied, and what needs follow-up.
