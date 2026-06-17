# Architecture

## Current high-level flow

```text
Rico Quick Start Form
        ↓
Jotform Webhook
        ↓
FastAPI Rico Server
        ↓
Rico Safety + NLU + Memory
        ↓
AI Provider Layer
        ↓
Rico Tool Registry
        ↓
Existing Job Automation System
        ↓
Neon Database + Telegram + Dashboard
```

## Legacy pipeline

```text
JobSpy
  ↓
Filter
  ↓
Scoring
  ↓
Application Tracking
  ↓
Telegram Notifications
  ↓
Dashboard
  ↓
Follow-up Reminders
  ↓
Feedback Loop
```

## Core backend modules

- `src/rico_agent.py` — agent orchestration and profile model
- `src/rico_repo_adapter.py` — bridge to the existing job automation system
- `src/rico_chat_api.py` — chat-first controller
- `src/rico_memory.py` — lightweight JSON memory fallback
- `src/rico_db.py` — Neon/PostgreSQL Rico tables
- `src/rico_nlu.py` — English/Arabic/mixed language understanding
- `src/rico_safety.py` — guardrails and high-impact action checks
- `src/rico_identity.py` — canonical Rico identity and system prompt
- `src/rico_quality.py` — recommendation and response quality checks
- `src/rico_env.py` — environment readiness validation
- `src/rico_server.py` — FastAPI server and webhook routes
- `src/rico_jotform_webhook.py` — Jotform onboarding handler
- `src/rico_telegram_webhook.py` — Telegram webhook handler
- `src/rico_telegram_ui.py` — Telegram buttons and job card helpers
- `src/rico_openai_agent.py` — reasoning/tool-calling layer
- `src/rico_tool_registry.py` — tools exposed to Rico's AI layer
- `src/cv_parser.py` — CV parsing and profile extraction

## Architecture rules

- Preserve the existing Rico architecture unless the task explicitly approves changing it.
- Do not create parallel systems for routing, memory, scoring, billing, or application tracking without an explicit decision entry.
- Keep user-impacting actions permission-based.
- Do not claim production readiness without tests, deployment verification, and smoke evidence.
