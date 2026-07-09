# Master Index — AI Workspace

> The living map of every workspace document: what it is for, whether it is
> **Active** (maintained, trust it), **Historical** (dated record, do not edit),
> **Proposed** (not yet built), or **Template**. When you add, rename, retire, or
> supersede a workspace file, update this index in the same PR.
>
> **Last reviewed:** 2026-07-08. "Updated" = last commit date of the file.

## Start order (fastest path in)

1. **`PROJECT_STATUS.md`** — 30-second snapshot (read first).
2. **`START_HERE.md`** — entrypoint + full read order.
3. **`ENGINEERING_ROADMAP.md`** — authoritative "where is Rico now" (phases 0–7).
4. Latest handoff (see Handoffs below) → `CURRENT_STATE.md` → `TASKS.md`.

## Core — Active (source of truth)

| Document | Purpose | Status | Owner | Depends on | Updated |
| --- | --- | --- | --- | --- | --- |
| `PROJECT_STATUS.md` | One-page dashboard; read first | Active | Release/last-merger | ROADMAP, CURRENT_STATE | 2026-07-08 |
| `MASTER_INDEX.md` | This index | Active | Whoever adds/retires a doc | all workspace docs | 2026-07-08 |
| `START_HERE.md` | Session entrypoint + read order | Active | Core | PROJECT_STATUS, MASTER_INDEX, ROADMAP | 2026-07-09 |
| `ENGINEERING_ROADMAP.md` | Vision→…→releases; phase status (canonical "now") | Active | Owner/Architect | DECISIONS, AUDIT gate | 2026-07-08 |
| `CURRENT_STATE.md` | Dated state log (newest at top; see reconciliation header) | Active (log) | Release/last-merger | ROADMAP, handoffs | 2026-07-08 |
| `TASKS.md` | Task ledger | Active | Assignee per task | DECISIONS, EVALS | 2026-07-08 |
| `DECISIONS.md` | Decision log (ADRs — see ADR index below) | Active | Owner/Architect | — (source) | 2026-07-08 |

## Governance & process — Active

| Document | Purpose | Status | Owner | Depends on | Updated |
| --- | --- | --- | --- | --- | --- |
| `OPERATING_RULES.md` | GitHub/Render/Vercel/Neon/test/verify guardrails | Active | Owner/Architect | — (source) | 2026-07-06 |
| `AGENT_OPERATING_MODEL.md` | Owner/architect/Claude/Codex/Lovable/release roles | Active | Owner | — (source) | 2026-07-09 |
| `PROMPT_CONTRACT.md` | Required task-brief inputs + output format | Active | Owner/Architect | OPERATING_RULES | 2026-07-06 |
| `PR_CHECKLIST.md` | Checklist to paste into PRs | Active | Core | PR_QUALITY_GATE_RULES | 2026-07-06 |
| `PR_QUALITY_GATE_RULES.md` | Agent-side PR quality gate | Active | Owner/Architect | OPERATING_RULES | 2026-07-06 |
| `RICO_EXECUTION_PRINCIPLES.md` | Product constitution (v2.0) | Active | Owner | — (source) | 2026-07-06 |
| `HANDOFFS/README_PR_QUALITY_GATE.md` | Pointer to the quality-gate rules | Active | Core | PR_QUALITY_GATE_RULES | 2026-07-06 |

## Vision & architecture — Active

| Document | Purpose | Status | Owner | Depends on | Updated |
| --- | --- | --- | --- | --- | --- |
| `PROJECT_BRIEF.md` | Product + owner + shared-source-of-truth rule | Active | Owner | — (source) | 2026-07-06 |
| `CAREER_OS_VISION.md` | 10-layer Career OS vision (live-vs-vision table) | Active | Owner | RICO_EXECUTION_PRINCIPLES | 2026-07-06 |
| `ARCHITECTURE.md` | Live stack, system diagram, target (phased) architecture | Active | Owner/Architect | DECISIONS (DEC-20260707-001) | 2026-07-08 |

## Audit gate — Active / Historical

| Document | Purpose | Status | Updated |
| --- | --- | --- | --- |
| `AUDITS/2026-07-08-production-hardening-audit.md` | Near-term execution gate (read before feature/infra work) | Active | 2026-07-08 |
| `AUDITS/2026-07-08-audit-gate-codex-followup.md` | Codex follow-up on the gate (synthetic-users rule) | Active | 2026-07-08 |
| `AUDITS/attachment-document-routing-post-674-677.md` | Attachment/document routing audit (findings 1–5) | Historical | 2026-07-08 |
| `AUDITS/VERCEL_BUILD_FAILURE_2026_06_28.md` | Root-cause report (resolved) | Historical | 2026-07-08 |
| `RICO_CODEBASE_INVENTORY_2026_06_21.md` | Point-in-time codebase inventory snapshot | Historical | 2026-07-06 |

## Handoffs (dated records — Historical; newest is the live pointer)

Latest first; `START_HERE.md` names the current one. All are Historical (do not
edit for content); the newest doubles as the current status pointer.

| Handoff | Status |
| --- | --- |
| `HANDOFFS/2026-07-09-906-907-sync-and-908-909-triage.md` | Latest (current pointer) |
| `HANDOFFS/2026-07-09-446-stage1-cleanup.md` | Historical |
| `HANDOFFS/2026-07-09-security-data-risk-deep-dive.md` | Historical |
| `HANDOFFS/2026-07-09-board-health-scan.md` | Historical |
| `HANDOFFS/2026-07-09-board-clean-governance-complete.md` | Historical |
| `HANDOFFS/2026-07-08-technical-status.md` | Historical |
| `HANDOFFS/2026-07-04-search-relevance-followup.md` | Historical |
| `HANDOFFS/2026-07-03-tc2-tc8-merge-pair-decision.md` | Historical |
| `HANDOFFS/2026-06-30-chat-os-action-cards-and-smoke-test-fixes.md` | Historical |
| `HANDOFFS/2026-06-27-qa-cycle-1-complete.md` | Historical |
| `HANDOFFS/2026-06-23-attachment-document-routing.md` | Historical |
| `HANDOFFS/2026-06-22-job-flow-stabilization-complete.md` | Historical |
| `HANDOFFS/2026-06-22-job-flow-stabilization.md` | Historical (superseded by the -complete handoff) |
| `HANDOFFS/2026-06-21-system-quality-audit.md` | Historical |
| `HANDOFFS/2026-06-21-career-os-roadmap-status.md` | Historical |
| `HANDOFFS/2026-06-21-action-audit-schema-hardening.md` | Historical |
| `HANDOFFS/2026-06-21-action-audit-rollout-complete.md` | Historical |
| `HANDOFFS/2026-06-20-rico-career-os-roadmap.md` | Historical |
| `HANDOFFS/2026-06-20-profile-nudge-render-rollout.md` | Historical |
| `HANDOFFS/2026-06-20-agentic-ui-implementation-brief.md` | Historical |

## Evals (dated verification records — Historical)

| Eval | Status |
| --- | --- |
| `EVALS/2026-07-03-chat-live-qa.md` | Historical (source of TASK-20260703-* items) |
| `EVALS/2026-07-03-tc2-tc8-live-fix.md` | Historical |
| `EVALS/2026-07-03-tc2-tc8-wiring-followup.md` | Historical |
| `EVALS/2026-06-17-post-615-616-verification.md` | Historical |

## Proposals (not yet built)

| Document | Purpose | Status |
| --- | --- | --- |
| `proposals/RICO_JOB_ALERT_EMAILS.md` | Email job-alert design (shipped gated/inert as #805) | Proposed / partly shipped |
| `proposals/RICO_MISSION_CONTROL.md` | Career OS "Mission Control" dashboard | Proposed |

## Templates

| Document | Purpose | Status |
| --- | --- | --- |
| `HANDOFFS/TEMPLATE.md` | Copy for each task handoff | Template |
| `EVALS/TEMPLATE.md` | Copy when a task reaches review/verification | Template |

---

## ADR index (decisions live in `DECISIONS.md` — no parallel ADR system)

Rico's `DECISIONS.md` entries already follow ADR form (Context / Decision /
Consequences / Follow-up). This index gives them ADR-style discoverability
without duplicating them into separate files.

| ADR ref | Decision | Topic |
| --- | --- | --- |
| DEC-20260617-001 | Use `AI_WORKSPACE/` as the shared source of truth | Governance |
| DEC-20260618-001 | Close stale PR #601; merge docs PRs #608/#566 | PR hygiene |
| DEC-20260621-001 | Smallest-safe security hardening batch (#700–#705) | Security |
| DEC-20260621-002 | Harden existing `action_audit_log`; no parallel audit systems | Audit/approval |
| DEC-20260621-003 | Action-audit rollout; migration drift surfaced/tracked | Migrations |
| DEC-20260628-001 | No Dead UI Rule (route must be live / redirect-only / removed) | Frontend routing |
| DEC-20260703-001 | Partial-unique arbiter + codified full-unique (index cleanup) | Database |
| DEC-20260707-001 | Phased architecture maturation; persist state before migration/redesign | Architecture roadmap |
| DEC-20260708-001 | `command-concept-sandbox` = approved design reference | Design governance |
| DEC-20260708-002 | Agentic-UI action routing contract (no frontend-only actions) | Safety/actions |
| DEC-20260708-003 | Design-system boundary: Atelier (marketing) vs Nocturne (workspace) | Design systems |
| DEC-20260708-004 | Quarantine the Lovable streaming-chat experiment | Prototype governance |

_When you add a `DEC-*` entry, add a row here in the same PR._
