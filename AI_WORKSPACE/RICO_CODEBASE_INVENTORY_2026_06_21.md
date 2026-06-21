# Rico Codebase Inventory  Agentic Vision / Product State

Audit date: 2026-06-21
Audit branch: `audit/rico-codebase-inventory-agentic-vision`
Audited baseline: `c8c033f1ce48f6d89c6bec70796ba538500064d8` (`origin/main`)
Latest product/workspace merge in that baseline: PR #707, following the #700–#705 hardening batch
Scope: documentation-only inspection. No runtime, frontend, backend, database, migration, deployment, or production changes were made.

## 1. Executive Summary

Rico is currently a production UAE-focused career companion with authenticated profiles, CV ingestion, multi-CV storage, job search, deterministic match explanations, application tracking, subscriptions, Arabic/English chat, Telegram/JotForm integrations, and guarded job actions. It is not a blank slate and it is not yet a unified autonomous Career OS.

The strongest Agentic Vision foundations already implemented are:

- A canonical authenticated chat response contract with optional action cards, permission requests, progress, proposed changes, and attachment analysis.
- A production action runtime with JWT-derived identity, action allowlisting, idempotency checks, subscription checks, tool dispatch, audit writes, and job context updates.
- A server-issued pending permission ID that is bound to user, action, and job, has a backend-enforced expiry, and is consumed once.
- A real apply approval gate controlled by `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS`, defaulting to approval required.
- Public `/actions/run` input now strips the internal `_approved` sentinel, so only the validated permission-execution path can inject approval.
- A real application tracker and a real draft queue, although queue approval currently records status rather than sending an external application.
- Deterministic CV generation and match explanation components designed to avoid fabricated facts.
- Existing document classification, active-CV resolution, multiple CV storage, learning signals, and career memory.

Prototype-only or parallel work includes:

- PR #688 `/ask`: authenticated and visibly marked Preview/Demo, but entirely mock-driven and not connected to Rico's canonical backend contracts, permission execution, or real backend expiry metadata.
- The `/api/v1/agent/chat` orchestrator and the stateful workflow coordinator: both are real code, but they overlap the production `agent_runtime` and canonical `/api/v1/rico/chat` path.
- The stateful coordinator's separate confirmation token store, which lacks the protections now present in `pending_permissions.py`.
- Legacy browser apply modules, which are disabled by default and are not a production browser-assisted Agentic capability.

Missing or incomplete foundations are:

- One explicit, canonical action policy gate covering all internal writes and external actions.
- Database-enforced append-only operational audit events and a clean migration-owned schema.
- A consolidated, production-used FitScorer/ATS gap model.
- Verified zero-fabrication per-job CV tailoring.
- Real company research, outreach drafting/sending policy, and browser-assisted apply.
- Real `/ask` backend wiring using the existing `RicoAgenticUi` contract.

The #700–#707 batch already fixed job binding, denial audit writes, missing commits, connection cleanup, approval-sentinel forgery, and workspace verification. The next foundation PR should therefore be narrowly named `feat/action-audit-schema-hardening`: extend the existing `action_audit_log`, remove request-time schema mutation from that path, and add database-level append-only protection. Permission expiry metadata should be a separate small PR that exposes the backend's actual expiry to canonical UI clients. Do not begin by adding a new approval-token service, a second audit table, a new FitScorer from scratch, a second action-card schema, or a separate application queue.

## 2. Current PR / Branch Context

### Current repository state

| Item | Value |
|---|---|
| Audit branch | `audit/rico-codebase-inventory-agentic-vision` |
| Base branch | `main` |
| Latest audited `origin/main` SHA | `c8c033f1ce48f6d89c6bec70796ba538500064d8` |
| Latest audited merge | PR #707, `docs(workspace): record #705 merge + Render deploy live verification` |
| Later automated commits | `41d3085` and `c8c033f`, both `Update dashboard [skip ci]`; changed only `docs/index.html` and did not alter Agentic conclusions |
| Worktree | Isolated from the pre-existing dirty worktree |

### Relevant pull requests

| PR | State | Scope | Inventory conclusion |
|---|---|---|---|
| #683 | Merged | Agentic UX contract | Useful product contract. Its implementation-status text is now stale because #672, #673, #676, #677, #700, and #701 implemented part of it. |
| #688 | Open, not draft | `/ask` conversational UX prototype | Auth guarded and visibly marked Preview/Demo; mock-only; no backend changes. Its 300-second countdown is local prototype state, not live permission expiry. Keep preview-only until it uses canonical chat/permission contracts and backend-provided expiry metadata. |
| #698 | Open draft | GitHub intelligence / Agentic Vision report | Docs-only parallel version. Main already contains a different version of the same path. Do not merge blindly. |
| #699 | Open, not draft | Parallel GitHub intelligence report | Overlaps #698 and the file already on `main`; should be reconciled or closed, not stacked. |
| #685 | Open draft; superseded/duplicate-risk | Audit policy gate and approval token | Adds two competing audit migrations/tables, a parallel HMAC approval authority, and a parallel audit writer after the existing foundations were hardened. It is superseded as a foundation and must not be merged. |
| #672 | Merged | Optional Agentic UI contracts | Added canonical backend/frontend action-card contracts and tests. |
| #673 | Merged | Permission engine and UI bridge | Added permission request cards, pending permission service, execution endpoint, runtime integration, and tests. |
| #676 | Merged | Career OS action kinds and career memory | Added proposed changes, career memory, universal-upload UI pieces, and navigation changes. |
| #677 | Merged | Document intelligence | Added document classification before CV upload and tests. |
| #700 | Merged | Permission hardening | Bound permissions to `job_key` and audited denials. |
| #701 | Merged | Audit persistence fix | Added the missing transaction commit for `action_audit_log` writes. |
| #702 | Merged | Application-attempt dedup persistence fix | Added commit and reliable connection close for application-attempt/dedup writes in the legacy apply engines; does not make browser apply product-ready. |
| #703 | Merged | Identity resolver DB connection fix | Corrected connection cleanup in the parallel stateful identity resolver; does not make that stack canonical. |
| #704 | Closed, unmerged | Agentic foundation rollout workspace handoff | Superseded by the smaller workspace decision updates included through #705/#707. |
| #705 | Merged | Approval-bypass hardening | Strips client-forged `_approved` from `/actions/run`; only validated permission execution may inject it. |
| #707 | Merged | Workspace deployment record | Records #705 merge and live Render verification in `AI_WORKSPACE/DECISIONS.md`. |
| #691 | Open | Onboarding checklist/help UX | Adjacent frontend work, not a policy/audit foundation. |
| #695 | Open | AI workspace refresh | Documentation overlap; some proposed state is already behind current Agentic merges. |

### Stale or overlapping branches

- `feat/agent-audit-policy-gate`: overlaps the merged permission/audit foundations and contains two competing audit migrations. Treat as superseded/duplicate-risk and keep it unmerged.
- `feat/agentic-conversational-ux` and `feature/rico-agentic-conversational-ux`: overlapping `/ask` naming suggests parallel implementation risk.
- `feat/career-os-01-agentic-contracts`, `feat/career-os-02-action-cards`, and `claude/career-os-agentic-contracts-hddsld`: foundations represented by these names are already substantially merged through #672/#673/#676.
- `claude/practical-noether-7mikmr` and `claude/vigilant-faraday-tiv8vf`: both edit the same intelligence-report path already present on `main`.
- Old `docs/agentic-ui-architecture`-style branches should be checked against merged docs before reuse.

Branch presence alone does not prove abandonment. The risk classification above is based on overlap with merged files, PR state, and incompatible implementation choices.

## 3. File-by-file Inventory

### 3.0 Scan coverage

The audit enumerated all files under the requested roots:

| Root | Files |
|---|---:|
| `src/` | 216 |
| `migrations/` | 25 |
| `apps/web/app/` | 47 |
| `apps/web/components/` | 67 |
| `apps/web/lib/` | 17 |
| `AI_WORKSPACE/` | 15 |
| `docs/` | 47 |
| `tests/` | 225 |

Detailed entries below cover files that define current product behavior, persistence, Agentic contracts, safety, or a credible duplicate path. Remaining support/UI/test files are classified in compact indexes after the detailed entries.

### 3.1 API, schemas, repositories, and services

### `src/api/app.py`
- Status: implemented
- Area: infra / auth
- What it does: Builds the FastAPI application, middleware, startup checks, and registers all current routers.
- What depends on it: Production API process and API tests.
- What it depends on: Auth, rate limiting, database checks, every registered router.
- Agentic relevance: Confirms that both `/api/v1/actions` and the parallel `/api/v1/agent` router are live.
- Problems / risks: Registering parallel agent endpoints makes architectural duplication externally reachable.
- Recommended action: keep as-is; consolidate routers later without changing production routes abruptly.

### `src/api/auth.py`
- Status: implemented
- Area: auth
- What it does: JWT creation/validation, password handling, cookie auth, signup/login flows.
- What depends on it: Protected API routes and frontend session checks.
- What it depends on: User repository and environment configuration.
- Agentic relevance: Agentic actions must continue deriving identity from JWT, not action payloads.
- Problems / risks: Any new Agentic endpoint that bypasses these dependencies would create user-isolation risk.
- Recommended action: keep as-is.

### `src/api/deps.py`
- Status: implemented
- Area: auth
- What it does: Provides `get_current_user` and common request dependencies.
- What depends on it: Actions, agent, jobs, application, subscription, and other protected routers.
- What it depends on: JWT auth and user lookup.
- Agentic relevance: Canonical identity boundary for action execution.
- Problems / risks: None specific; duplicate endpoints must use it consistently.
- Recommended action: keep as-is.

### `src/api/routers/actions.py`
- Status: implemented
- Area: agentic / permissions / audit
- What it does: Exposes `POST /api/v1/actions/run`, strips the internal `_approved` sentinel from client job payloads, and dispatches authenticated actions to `agent_runtime`.
- What depends on it: Current and future action-card clients.
- What it depends on: `src/agent/runtime.py`, action schemas, JWT, rate limits.
- Agentic relevance: This is the clearest current universal action boundary.
- Problems / risks: Direct actions and permission-approved actions enter through different endpoints before converging on the runtime; PR #705 closed the known client-forged approval sentinel bypass.
- Recommended action: extend; make it the canonical execution boundary after policy consolidation.

### `src/api/routers/agent.py`
- Status: duplicate-risk
- Area: agentic / chat / audit
- What it does: Exposes `/api/v1/agent/chat` using the older orchestrator and `src/schemas/agent.py`.
- What depends on it: `sendAgentChat` and orchestration adapter code.
- What it depends on: `src/agent/orchestrator/orchestrator.py`.
- Agentic relevance: A second externally reachable agent/action stack.
- Problems / risks: Duplicates action validation, idempotency, tool execution, audit, and UI contracts.
- Recommended action: consolidate; retain compatibility until clients move to canonical Rico chat/runtime contracts.

### `src/api/routers/rico_chat.py`
- Status: implemented
- Area: chat / agentic / permissions / CV / audit
- What it does: Authenticated/public chat, streaming, history, profile, CV upload/confirmation, webhooks, and permission execution.
- What depends on it: `/command`, integrations, chat tests, Agentic UI composer.
- What it depends on: `RicoChatAPI`, auth, schemas, pending permissions, runtime, audit repository.
- Agentic relevance: Canonical conversational product surface and current permission-consumption endpoint.
- Problems / risks: Very broad router; action execution at `/rico/actions/execute` overlaps `/actions/run`; denied permission audit is present but policy is not centralized.
- Recommended action: extend narrowly; do not add a separate policy sub-application.

### `src/api/routers/jobs.py`
- Status: implemented
- Area: jobs / applications / permissions
- What it does: Lists jobs and handles explicit save/skip/block/apply requests.
- What depends on it: Jobs page and action flows.
- What it depends on: Jobs service/repository, apply service, JWT.
- Agentic relevance: Explicit authenticated apply is treated as user approval and passes `approved=True`.
- Problems / risks: The distinction between direct user click and agent-proposed approval must remain explicit and audited.
- Recommended action: keep as-is; test more when policy gate is centralized.

### `src/api/routers/applications.py`
- Status: implemented
- Area: applications
- What it does: Creates, lists, updates, and summarizes application lifecycle records.
- What depends on it: `/flow`, dashboard metrics, chat application commands.
- What it depends on: `applications_repo`, lifecycle schemas, JWT.
- Agentic relevance: Existing application state must be reused by future queues and operational memory.
- Problems / risks: Legacy fallback storage and `user_job_context` create multiple state representations.
- Recommended action: extend; consolidate lifecycle ownership later.

### `src/api/routers/apply_queue.py`
- Status: partial
- Area: applications / CV / agentic
- What it does: Prepares tailored drafts, lists queue entries, approves/rejects drafts, and lists follow-ups.
- What depends on it: `/queue` page and application-draft tests.
- What it depends on: `rico_apply_ai`, `rico_db` application drafts, profile/document data.
- Agentic relevance: Existing foundation for a Tailored Application Queue.
- Problems / risks: Approval marks a draft/application as approved/applied but does not submit externally; naming and UI copy can overstate effects. Tailoring path lacks a post-generation fact verifier.
- Recommended action: extend and correct semantics; do not create another queue.

### `src/api/routers/files.py`
- Status: implemented
- Area: CV / auth
- What it does: Authenticated document list/upload/delete/rename/retype, quotas, and active-CV switching.
- What depends on it: Upload/profile/files UX and chat document context.
- What it depends on: `rico_db`, parser metadata, profile repository.
- Agentic relevance: Canonical multi-CV and active-document management.
- Problems / risks: Base `user_documents` schema is created in runtime DDL; upload/confirm paths are not fully unified.
- Recommended action: extend; migrate schema ownership later.

### `src/api/routers/job_lifecycle.py`
- Status: implemented
- Area: applications / audit
- What it does: Records opened and other lifecycle events in `user_job_context`.
- What depends on it: Job cards, follow-up logic, application intelligence.
- What it depends on: User job context repository.
- Agentic relevance: Useful operational event source for future memory.
- Problems / risks: Overlaps application tracker state.
- Recommended action: consolidate later around one lifecycle model.

### `src/api/routers/pipeline.py`
- Status: implemented
- Area: jobs / agentic
- What it does: Pipeline status, triggers, reminders, and profile nudges.
- What depends on it: Dashboard/command operations.
- What it depends on: Pipeline service and profile nudge service.
- Agentic relevance: Existing long-running job-discovery operation surface.
- Problems / risks: Trigger permissions differ across parallel agent stacks.
- Recommended action: extend after policy classification is canonical.

### `src/api/routers/subscription.py`
- Status: implemented
- Area: billing
- What it does: Plans, current subscription, checkout, portal, webhook, and intent endpoints.
- What depends on it: Subscription page and action entitlement checks.
- What it depends on: Subscription repositories/services and Stripe integration.
- Agentic relevance: Existing entitlement source for premium Agentic capabilities.
- Problems / risks: Permission tier and billing plan must not be conflated without an explicit product decision.
- Recommended action: keep as-is.

### `src/schemas/actions.py`
- Status: implemented
- Area: agentic / permissions
- What it does: Defines the action request/response contract and execution allowlist.
- What depends on it: `/api/v1/actions/run`, permission execution response, frontend API.
- What it depends on: Pydantic only.
- Agentic relevance: Current server-side list of executable action names.
- Problems / risks: It is separate from UI action kinds and policy risk classes.
- Recommended action: extend into a canonical action registry; do not create another action enum.

### `src/schemas/chat.py`
- Status: implemented
- Area: chat / agentic / permissions / frontend
- What it does: Defines canonical Rico chat, action-card, permission, progress, proposed-change, and attachment-analysis contracts.
- What depends on it: Rico chat router, composer, frontend mirrored Zod schemas, tests.
- What it depends on: Pydantic only.
- Agentic relevance: Canonical Agentic UI contract already exists.
- Problems / risks: Impact levels are `low/medium/high`, while PR #688 adds `safe/critical`; uncontrolled divergence would duplicate the contract.
- Recommended action: extend carefully and mirror frontend changes; do not create `ActionCard` v2 schemas.

### `src/schemas/agent.py`
- Status: duplicate-risk
- Area: agentic / frontend
- What it does: Defines an older `AgentUIResponse`, generic UI component, and direct executable action payload.
- What depends on it: `/api/v1/agent/chat` and its orchestrator.
- What it depends on: Pydantic only.
- Agentic relevance: Parallel action-card response model.
- Problems / risks: Allows a full job payload in the action and differs from canonical chat contracts.
- Recommended action: deprecate later after clients migrate.

### `src/services/pending_permissions.py`
- Status: implemented
- Area: permissions / agentic
- What it does: Registers server-issued permission IDs and validates user, action, job binding, TTL, and one-time consumption.
- What depends on it: Permission factory and `/rico/actions/execute`.
- What it depends on: In-process memory, lock, clock.
- Agentic relevance: Current production approval capability store.
- Problems / risks: In-memory state is lost on restart and is not shared across workers. The internal expiry is not exposed through the canonical permission response, so the UI cannot display the backend's actual deadline.
- Recommended action: extend by returning real expiry metadata; move to Redis only when deployment topology or restart durability requires it.

### `src/services/permission_factory.py`
- Status: implemented
- Area: permissions / agentic
- What it does: Creates the canonical apply permission request and registers the pending permission.
- What depends on it: Runtime apply result composition.
- What it depends on: Chat schemas and pending permission service.
- Agentic relevance: Existing approval issuance path that should be generalized.
- Problems / risks: Apply-specific factory; risk/action policy is embedded rather than registry-driven.
- Recommended action: extend into reusable constructors after action policy is defined.

### `src/services/agentic_ui_composer.py`
- Status: implemented
- Area: agentic / chat / frontend
- What it does: Converts runtime result artifacts into `RicoAgenticUi`.
- What depends on it: Rico chat finalization.
- What it depends on: Runtime result shape and chat schema.
- Agentic relevance: Single existing composition point for production Agentic UI.
- Problems / risks: Silent failure returns no Agentic UI, which can hide schema drift.
- Recommended action: keep as canonical; add observability/tests for invalid artifacts.

### `src/services/apply_service.py`
- Status: implemented
- Area: applications / permissions
- What it does: Enforces approval and auto-apply feature flags, subscription checks, board routing, and manual fallback.
- What depends on it: Job routes, runtime tools, legacy apply paths.
- What it depends on: Apply engines, environment flags, subscription gating.
- Agentic relevance: Current hard safety floor for external submission.
- Problems / risks: Board-specific automation is legacy and disabled; callers passing `approved=True` must be tightly controlled.
- Recommended action: keep as-is; route all future external apply through an explicit policy decision.

### `src/services/career_memory.py`
- Status: partial
- Area: agentic / profile / audit
- What it does: Stores and summarizes selected career-memory signals.
- What depends on it: Runtime actions and Career OS features.
- What it depends on: Profile/job context persistence.
- Agentic relevance: Existing memory foundation.
- Problems / risks: It is not a full chronological operational event model.
- Recommended action: extend after audit events are canonical.

### `src/services/document_classifier.py`
- Status: implemented
- Area: CV / agentic
- What it does: Classifies uploaded documents before CV-specific processing.
- What depends on it: Upload routes and document-intelligence UI.
- What it depends on: Deterministic signatures and text extraction inputs.
- Agentic relevance: Prevents non-CV documents from entering the wrong workflow.
- Problems / risks: Classification confidence must remain separate from CV suitability.
- Recommended action: keep as-is; test more with new document classes.

### `src/services/document_resolver.py`
- Status: implemented
- Area: CV / agentic
- What it does: Resolves primary CV, latest CV fallback, and parsed-profile fallback.
- What depends on it: Chat context and tailoring candidates.
- What it depends on: `rico_db` document queries and profile data.
- Agentic relevance: Canonical source-selection logic for future tailoring.
- Problems / risks: Multiple storage paths can make provenance unclear.
- Recommended action: extend with explicit source/provenance fields.

### `src/services/job_match_explanation.py`
- Status: implemented
- Area: scoring / jobs
- What it does: Produces deterministic V2 explanation/verdict from job/profile data and an existing score.
- What depends on it: Jobs service and visible job cards.
- What it depends on: Existing ranking score and normalized job/profile fields.
- Agentic relevance: Existing explanation layer for FitScorer output.
- Problems / risks: Overlaps `rico_match_explainer.py`; it explains a score but does not establish an ATS score.
- Recommended action: consolidate with the V1 explainer.

### `src/services/jobs_service.py`
- Status: implemented
- Area: jobs / scoring
- What it does: Retrieves user-scoped jobs and attaches normalized match explanations.
- What depends on it: Jobs API.
- What it depends on: Jobs repository and V2 explainer.
- Agentic relevance: Production job-card data path.
- Problems / risks: Score provenance is not obvious to the UI.
- Recommended action: extend with score type/version metadata.

### `src/services/subscription_gating.py`
- Status: implemented
- Area: billing / permissions
- What it does: Determines feature/action entitlements from plan state.
- What depends on it: Apply and premium features.
- What it depends on: Subscription repository/plans.
- Agentic relevance: One input to policy, not a replacement for action-risk policy.
- Problems / risks: Future P-level permissions could be incorrectly mapped directly to price plans.
- Recommended action: keep separate from permission policy.

### `src/repositories/audit_repo.py`
- Status: partial
- Area: audit / agentic / infra
- What it does: Persists action audit logs, checks idempotency, reads recent events, and writes learning/profile/permission audit records.
- What depends on it: Runtime, older orchestrator, stateful coordinator, permission denial path.
- What it depends on: Psycopg2 database access with in-memory fallback.
- Agentic relevance: Existing audit system must be extended rather than replaced casually.
- Problems / risks: `write_audit_log` performs runtime `ALTER TABLE`; helper paths create additional audit tables at runtime; append-only is not DB-enforced.
- Recommended action: consolidate and harden with one migration-owned schema.

### `src/repositories/applications_repo.py`
- Status: implemented
- Area: applications
- What it does: Persists and reads application lifecycle using the SaaS recommendation table with fallback behavior.
- What depends on it: Applications router, stats, chat.
- What it depends on: Database and legacy application storage.
- Agentic relevance: Existing application record of truth.
- Problems / risks: Fallback and context lifecycle create dual-state complexity.
- Recommended action: consolidate later; do not create a new Agentic applications repository.

### `src/repositories/user_job_context_repo.py`
- Status: implemented
- Area: jobs / applications / audit
- What it does: Stores per-user job interactions, lifecycle, URLs, and follow-up context.
- What depends on it: Runtime actions, lifecycle route, chat intelligence.
- What it depends on: `user_job_context` migrations.
- Agentic relevance: Rich operational context for memory and receipts.
- Problems / risks: Some fields duplicate application tracker status.
- Recommended action: extend only after ownership boundaries are documented.

### `src/repositories/learning_repo.py`
- Status: partial
- Area: agentic / profile
- What it does: Persists user preference/behavior learning signals.
- What depends on it: Stateful coordinator and feedback paths.
- What it depends on: Database, with runtime table creation fallback.
- Agentic relevance: Existing preference-learning substrate.
- Problems / risks: Runtime DDL and unclear relationship to `rico_learning_signals`.
- Recommended action: consolidate schema ownership.

### `src/repositories/profile_repo.py`
- Status: implemented
- Area: profile / auth
- What it does: Loads and updates canonical profile/settings models.
- What depends on it: Chat, onboarding, CV activation, jobs.
- What it depends on: Rico database layer.
- Agentic relevance: Source of user facts; generated documents must not exceed these facts.
- Problems / risks: Multiple profile hydration/merge paths require provenance discipline.
- Recommended action: keep as-is; expose provenance to tailoring.

### `src/repositories/subscription_repo.py`
- Status: implemented
- Area: billing
- What it does: Persists subscription state, entitlements, and events.
- What depends on it: Subscription APIs and gating.
- What it depends on: Subscription migrations.
- Agentic relevance: Existing commercial entitlement source.
- Problems / risks: None specific to Agentic Vision.
- Recommended action: keep as-is.

### 3.2 Agent runtime and parallel agent stacks

### `src/agent/runtime.py`
- Status: implemented
- Area: agentic / permissions / audit / applications
- What it does: Validates actions, enforces idempotency/subscription behavior, dispatches tools, logs outcomes, updates context/memory, and creates permission requests.
- What depends on it: `/actions/run`, `/rico/actions/execute`, chat action flows.
- What it depends on: Tool registry, action schemas, audit repo, permission factory, context/memory repositories.
- Agentic relevance: Canonical current action execution boundary.
- Problems / risks: Policy decisions are distributed around the runtime rather than represented by one explicit decision object.
- Recommended action: extend; make policy evaluation a pre-execution stage here.

### `src/agent/registry/tool_registry.py`
- Status: implemented
- Area: agentic
- What it does: Registers callable tools and resolves them by name.
- What depends on it: Runtime and older orchestrator.
- What it depends on: Tool modules.
- Agentic relevance: Existing capability registry.
- Problems / risks: Registry metadata does not fully describe risk, side effects, approval, reversibility, or external systems.
- Recommended action: extend metadata instead of adding a second policy registry.

### `src/agent/tools/job_tools.py`
- Status: implemented
- Area: jobs / applications / permissions
- What it does: Implements apply/save/skip/block job tools and bridges pre-approved apply to `apply_service`.
- What depends on it: Runtime/tool registry.
- What it depends on: Apply service and repositories.
- Agentic relevance: Current side-effecting job action implementation.
- Problems / risks: `_approved` is an internal sentinel. PR #705 strips it from `/actions/run`; future callers must preserve the rule that only valid permission consumption may inject it.
- Recommended action: keep as-is; add policy metadata/tests.

### `src/agent/orchestrator/orchestrator.py`
- Status: duplicate-risk
- Area: agentic / audit
- What it does: Independently detects intent, validates actions, checks idempotency, dispatches tools, and writes audits.
- What depends on it: `/api/v1/agent/chat`.
- What it depends on: Older agent schemas, intent detector, tool registry, audit repo.
- Agentic relevance: Functional but parallel implementation of runtime responsibilities.
- Problems / risks: Creates two sources of truth for action validation, response construction, and audit semantics.
- Recommended action: consolidate into `agent_runtime`.

### `src/agent/orchestrator/intent_detector.py`
- Status: partial
- Area: agentic / chat
- What it does: Simple intent-to-tool mapping for the older agent endpoint.
- What depends on it: Older orchestrator.
- What it depends on: Keyword logic.
- Agentic relevance: Parallel to richer Rico chat intent routing.
- Problems / risks: A third intent-routing vocabulary can drift from production chat.
- Recommended action: deprecate later.

### `src/agent/coordinator.py`
- Status: partial
- Area: agentic / profile / audit
- What it does: Coordinates identity, hydrated profile context, workflow execution, learning, and response conversion.
- What depends on it: Stateful chat adapter and direct helper calls.
- What it depends on: Identity/context resolvers and workflow coordinator.
- Agentic relevance: A credible stateful architecture prototype.
- Problems / risks: Parallel to `RicoChatAPI`; uses a separate confirmation model and audit helper tables.
- Recommended action: investigate and extract useful context ideas; do not make it a second production runtime.

### `src/agent/workflow/coordinator.py`
- Status: duplicate-risk
- Area: agentic / permissions / jobs
- What it does: Routes workflow intents, assigns `PermissionLevel`, stores confirmation tokens, and executes legacy workflows.
- What depends on it: Stateful coordinator.
- What it depends on: Rico repo adapter and agent intelligence modules.
- Agentic relevance: Contains early permission concepts and role intelligence.
- Problems / risks: Its in-memory confirmations have no TTL/lock/job binding; `autonomy_level == auto` can downgrade apply confirmation; permission levels do not match P0-P4.
- Recommended action: deprecate confirmation execution; preserve only reusable intelligence after review.

### `src/services/stateful_chat_adapter.py`
- Status: partial
- Area: chat / agentic
- What it does: Adapts legacy chat calls to the stateful coordinator.
- What depends on it: Limited/experimental migration paths.
- What it depends on: Stateful coordinator and memory store.
- Agentic relevance: Migration bridge, not canonical product path.
- Problems / risks: Keeps the parallel stack alive without clear cutover ownership.
- Recommended action: investigate usage; deprecate if no production callers.

### `src/agent/context/resolver.py`
- Status: partial
- Area: profile / agentic / audit
- What it does: Hydrates profile context and writes hydration audit events.
- What depends on it: Stateful coordinator.
- What it depends on: Profile data, audit repo, behavior signals.
- Agentic relevance: Useful context/provenance concepts.
- Problems / risks: Audit writes rely on runtime schema mutation.
- Recommended action: reuse concepts after audit schema hardening.

### `src/agent/identity/resolver.py`
- Status: partial
- Area: auth / profile / agentic
- What it does: Resolves identities across email, session, Telegram, JotForm, and CV.
- What depends on it: Stateful coordinator.
- What it depends on: Identity repositories/mappers.
- Agentic relevance: Useful cross-channel identity model.
- Problems / risks: Protected web routes must still trust JWT as authoritative.
- Recommended action: investigate; do not replace JWT route identity.

### `src/agent/intelligence/scorer.py`
- Status: partial
- Area: scoring / agentic
- What it does: Scores profile fit against a small predefined role-requirement catalog.
- What depends on it: Stateful role-intelligence flow and tests.
- What it depends on: Normalized role/profile data.
- Agentic relevance: One possible FitScorer input.
- Problems / risks: Not general per-job ATS scoring and not the primary jobs score path.
- Recommended action: consolidate with other scorers; do not promote alone.

### `src/agent/intelligence/intent_classifier.py`
- Status: implemented
- Area: chat / jobs / agentic
- What it does: Classifies rich English/Arabic chat intents and explicit job-search signals.
- What depends on it: Rico chat routing and many regression tests.
- What it depends on: Deterministic rules and context.
- Agentic relevance: Production intent foundation.
- Problems / risks: Do not mix action authorization into intent classification.
- Recommended action: keep as-is.

### `src/agent/intelligence/role_classifier.py`
- Status: implemented
- Area: jobs / scoring
- What it does: Classifies role families from profile/job text.
- What depends on it: Role intelligence.
- What it depends on: Normalization rules.
- Agentic relevance: Useful for fit decomposition.
- Problems / risks: Coverage limitations can look like scoring certainty.
- Recommended action: extend with evidence/versioning.

### `src/agent/intelligence/role_suggester.py`
- Status: implemented
- Area: jobs / profile
- What it does: Suggests adjacent roles from profile evidence.
- What depends on it: Chat role suggestion flows.
- What it depends on: Role normalization/classification.
- Agentic relevance: Existing career guidance capability.
- Problems / risks: Must not fabricate jobs or unsupported user skills.
- Recommended action: keep as-is.

### 3.3 Core product engines and legacy modules

### `src/rico_chat_api.py`
- Status: implemented
- Area: chat / jobs / CV / applications / agentic
- What it does: Main conversational product engine: routing, context, job search, profile updates, CV builder, applications, and response assembly.
- What depends on it: Rico chat router, web command UI, extensive regression suite.
- What it depends on: Agent intelligence, repo adapter, providers, repositories, safety, composer.
- Agentic relevance: The real conversational backend that `/ask` should call or evolve from.
- Problems / risks: Very large module; contains multiple historical paths and both V1/V2 match explanation calls.
- Recommended action: extend narrowly; extract only with behavior-preserving tests.

### `src/rico_repo_adapter.py`
- Status: implemented
- Area: jobs / infra
- What it does: Bridges modern Rico chat/agent code to the legacy job automation pipeline.
- What depends on it: Rico chat, tool registry, stateful workflow, CLI import, tests.
- What it depends on: Dashboard/pipeline/job-source modules.
- Agentic relevance: Current compatibility boundary with legacy search.
- Problems / risks: Carries legacy dashboard dependencies into modern runtime.
- Recommended action: keep until pipeline replacement is explicit; do not duplicate the bridge.

### `src/rico_match_explainer.py`
- Status: implemented
- Area: scoring / jobs
- What it does: Deterministic V1 match explanation from role/skills/location evidence.
- What depends on it: Rico chat match formatting and tests.
- What it depends on: Job/profile facts.
- Agentic relevance: Reusable explanation evidence model.
- Problems / risks: Overlaps V2 explanation service and is not a hiring probability or ATS score.
- Recommended action: consolidate; retain deterministic evidence extraction.

### `src/scoring.py`
- Status: partial
- Area: scoring / jobs
- What it does: Contains legacy HSE-oriented scoring and newer user-specific scoring.
- What depends on it: Legacy pipeline and tests.
- What it depends on: Job/profile keyword structures.
- Agentic relevance: Existing score logic that must be inventoried before FitScorer work.
- Problems / risks: Hardcoded HSE lineage and mixed old/new functions make score meaning unclear.
- Recommended action: consolidate behind a versioned scoring interface.

### `src/llm_scorer.py`
- Status: implemented
- Area: scoring / jobs
- What it does: Embedding/keyword scoring plus fast profile-fit ranking for searched jobs.
- What depends on it: Profile-driven JSearch ranking and pipeline.
- What it depends on: Hugging Face/client configuration and deterministic fallback.
- Agentic relevance: One source of the visible job score.
- Problems / risks: Score is a Rico relevance heuristic, not ATS compatibility.
- Recommended action: keep; label score provenance.

### `src/resume_screener.py`
- Status: unused
- Area: scoring / CV
- What it does: Deterministic 100-point resume-versus-job-description screening with gap details.
- What depends on it: Unit tests only; no runtime caller was found.
- What it depends on: Resume/JD text parsing.
- Agentic relevance: Strong candidate component for a future FitScorer/ATS gap service.
- Problems / risks: Unused code may not reflect current product data models; must be validated before activation.
- Recommended action: investigate and adapt; do not create a new scorer first.

### `src/cv_parser.py`
- Status: implemented
- Area: CV
- What it does: Extracts text and structured CV facts from PDF/DOCX/TXT inputs and detects document type.
- What depends on it: Upload, profile hydration, CV tests.
- What it depends on: File parsers and deterministic extraction.
- Agentic relevance: Fact source for zero-fabrication generation.
- Problems / risks: Extraction quality is not the same as suitability or truth confidence.
- Recommended action: keep as-is; preserve provenance.

### `src/cover_letter_writer.py`
- Status: implemented
- Area: CV / applications
- What it does: Generates identity-bound AI or deterministic cover letters and rejects missing identity.
- What depends on it: Cover-letter flows and tests.
- What it depends on: Verified identity/profile facts and optional AI provider.
- Agentic relevance: Existing safe cover-letter foundation.
- Problems / risks: Not currently the queue's tailoring writer.
- Recommended action: extend and reuse in the queue; do not create a second writer.

### `src/rico_apply_ai.py`
- Status: partial
- Area: CV / applications / agentic
- What it does: Produces tailored CV text and a cover letter for application drafts.
- What depends on it: Apply queue prepare endpoint.
- What it depends on: AI provider, CV text, profile, job data.
- Agentic relevance: Existing per-job tailoring implementation.
- Problems / risks: Prompt-only no-fabrication enforcement; fallback includes generic unsupported claims and a `[Your Name]` placeholder; no fact verifier or diff/provenance output.
- Recommended action: harden and consolidate with deterministic CV builder and identity-safe cover-letter writer.

### `src/rico_db.py`
- Status: implemented
- Area: infra / profile / CV / applications
- What it does: Core Rico database access and runtime schema initialization for users, profiles, chat, jobs, documents, and application drafts.
- What depends on it: Most Rico services/repositories.
- What it depends on: Psycopg2/Postgres.
- Agentic relevance: Stores current profile, documents, recommendations, drafts, and chat state.
- Problems / risks: Runtime DDL owns important tables and alters, bypassing numbered migration discipline.
- Recommended action: consolidate schema ownership through future migrations.

### `src/applications.py`
- Status: stale
- Area: applications
- What it does: Legacy JSON/local application tracking fallback.
- What depends on it: Compatibility paths.
- What it depends on: Local files.
- Agentic relevance: None desirable for production operational memory.
- Problems / risks: Creates a second application store.
- Recommended action: deprecate later after fallback removal is proven safe.

### `src/apply_assistant.py`
- Status: partial
- Area: applications / agentic
- What it does: Legacy interactive apply assistant with optional control-server call.
- What depends on it: Daily legacy pipeline.
- What it depends on: Decision engine, control server, local interaction.
- Agentic relevance: Historical approval workflow ideas.
- Problems / risks: Not web-product-safe and overlaps current action runtime.
- Recommended action: deprecate later; do not reuse as Agentic queue.

### `src/indeed_apply.py`
- Status: prototype
- Area: applications / infra
- What it does: Board-specific automated apply implementation.
- What depends on it: Apply service when all feature/approval gates allow.
- What it depends on: Browser automation and credentials/session state.
- Agentic relevance: Future browser-assisted apply research only.
- Problems / risks: Disabled by default, fragile external UI dependency, not integrated with canonical receipts/policy.
- Recommended action: ignore for current foundation; reassess at P3.

### `src/naukrigulf_apply.py`
- Status: prototype
- Area: applications / UAE targeting
- What it does: Naukrigulf-specific application automation.
- What depends on it: Apply service/legacy daily pipeline behind flags.
- What it depends on: Browser/session automation.
- Agentic relevance: UAE-specific future capability.
- Problems / risks: Same external-side-effect and maintainability risks as Indeed path.
- Recommended action: ignore for current foundation; reassess at P3.

### `src/auto_apply.py`
- Status: prototype
- Area: applications
- What it does: Legacy LinkedIn/browser auto-apply logic.
- What depends on it: Limited legacy paths.
- What it depends on: Browser automation.
- Agentic relevance: Historical prototype, not product-ready Agentic execution.
- Problems / risks: Auto-apply framing conflicts with explicit per-action approval.
- Recommended action: deprecate later or isolate as research.

### `src/control_server.py`
- Status: stale
- Area: infra / applications
- What it does: Legacy control HTTP server retained for backward compatibility.
- What depends on it: Legacy apply assistant and adversarial tests.
- What it depends on: API-key checks and legacy automation.
- Agentic relevance: None for the modern FastAPI product.
- Problems / risks: A second server/action surface increases security and maintenance burden.
- Recommended action: deprecate later after caller inventory.

### `src/dashboard.py`
- Status: implemented
- Area: jobs / infra
- What it does: Legacy pipeline dashboard/result builder still used by daily run and repo adapter.
- What depends on it: `run_daily`, health checks, repo adapter.
- What it depends on: PDF manager, scoring, pipeline data.
- Agentic relevance: Legacy search output source.
- Problems / risks: Name suggests UI but functions as legacy pipeline assembly; imports stale PDF manager.
- Recommended action: keep until adapter replacement; document as legacy.

### `src/dashboard_v2.py`
- Status: unused
- Area: jobs / infra
- What it does: Refactored dashboard variant.
- What depends on it: Only `src/test_refactored_system.py` reference found.
- What it depends on: Refactored pipeline modules.
- Agentic relevance: None.
- Problems / risks: Parallel implementation with no production caller.
- Recommended action: investigate, then deprecate later.

### `src/dashboard_refactored.py`
- Status: unused
- Area: jobs / infra
- What it does: Another dashboard refactor variant.
- What depends on it: No current production caller found.
- What it depends on: Legacy pipeline.
- Agentic relevance: None.
- Problems / risks: Duplicate naming obscures current implementation.
- Recommended action: investigate, then deprecate later.

### `src/dashboard_ai.py`
- Status: unused
- Area: jobs / scoring
- What it does: AI-oriented dashboard experiment.
- What depends on it: No current production caller found.
- What it depends on: Legacy job data.
- Agentic relevance: Historical prototype only.
- Problems / risks: Could be mistaken for current Agentic dashboard.
- Recommended action: deprecate later.

### `src/dashboard_decision.py`
- Status: unused
- Area: jobs / applications
- What it does: Standalone dashboard decision experiment/script.
- What depends on it: No production caller found.
- What it depends on: Legacy decision engine.
- Agentic relevance: Historical only.
- Problems / risks: Parallel decision path.
- Recommended action: deprecate later.

### `src/pdf_manager.py`
- Status: stale
- Area: CV / infra
- What it does: Local PDF file management for the legacy dashboard.
- What depends on it: `src/dashboard.py`.
- What it depends on: Local filesystem.
- Agentic relevance: Should not be used for multi-user document storage.
- Problems / risks: Conflicts conceptually with authenticated `user_documents`.
- Recommended action: deprecate with legacy dashboard, not before.

### `src/rico_safety.py`
- Status: implemented
- Area: permissions / agentic
- What it does: Classifies and blocks unsafe/high-impact command patterns.
- What depends on it: Chat/provider tool flows.
- What it depends on: Rule-based safety categories.
- Agentic relevance: Existing safety input to policy.
- Problems / risks: Safety classification is not a complete authorization/policy decision.
- Recommended action: extend as a policy input, not as the policy gate itself.

### `src/rico_tool_registry.py`
- Status: implemented
- Area: chat / agentic
- What it does: Registers chat/provider tools such as search, profile, applications, and cover letters.
- What depends on it: LLM tool-routing paths.
- What it depends on: Repo adapter and product services.
- Agentic relevance: Existing conversational tool catalog.
- Problems / risks: Parallel to `src/agent/registry/tool_registry.py`.
- Recommended action: consolidate tool metadata/ownership over time.

### `src/rico_openai_agent.py`
- Status: implemented
- Area: chat / agentic
- What it does: Provider/tool-calling agent with approval awareness and HF-primary behavior.
- What depends on it: Chat fallback/tool paths.
- What it depends on: Provider runtime and Rico tool registry.
- Agentic relevance: Existing reasoning/tool layer.
- Problems / risks: Must not become an independent action authorization layer.
- Recommended action: keep reasoning separate from execution policy.

### `src/rico_memory.py`
- Status: implemented
- Area: chat / agentic
- What it does: Stores/retrieves conversational memory with safety controls.
- What depends on it: Rico chat and stateful adapter.
- What it depends on: Database/local fallback.
- Agentic relevance: Conversation memory, distinct from immutable operational audit memory.
- Problems / risks: Do not overload it with action receipts.
- Recommended action: keep separate.

### `src/rico_identity.py`
- Status: implemented
- Area: chat / safety / UAE targeting
- What it does: Defines product identity, UAE focus, truthfulness, and no-fabrication instructions.
- What depends on it: AI prompts and identity tests.
- What it depends on: Static product rules.
- Agentic relevance: Core behavioral policy for generation.
- Problems / risks: Prompt rules alone cannot guarantee zero fabrication.
- Recommended action: keep; add deterministic verification around generated artifacts.

### `src/run_daily.py`
- Status: implemented
- Area: jobs / applications / infra
- What it does: Runs the legacy scheduled job collection/scoring/notification pipeline.
- What depends on it: Worker/scheduler processes.
- What it depends on: Sources, scoring, dashboard, apply assistant, notifications.
- Agentic relevance: Current automation backbone, not interactive Agentic orchestration.
- Problems / risks: Legacy action paths and global feature flags coexist with web runtime.
- Recommended action: keep operationally stable; do not fold into new agent code casually.

### `src/linkedin_demo.py`
- Status: unused
- Area: applications
- What it does: LinkedIn demonstration script.
- What depends on it: No production caller found.
- What it depends on: Demo/browser assumptions.
- Agentic relevance: None.
- Problems / risks: Can be mistaken for supported integration.
- Recommended action: deprecate later.

### `src/test_email.py`
- Status: unused
- Area: infra
- What it does: Standalone email test script inside runtime source.
- What depends on it: No production caller found.
- What it depends on: Email environment configuration.
- Agentic relevance: None.
- Problems / risks: Source-tree test utility can invite accidental external sends.
- Recommended action: investigate and move/deprecate later.

### `src/test_refactored_system.py`
- Status: stale
- Area: infra
- What it does: Standalone test script for the unused dashboard V2 path.
- What depends on it: No production caller.
- What it depends on: `dashboard_v2`.
- Agentic relevance: None.
- Problems / risks: Not part of the normal test suite and preserves dead architecture.
- Recommended action: deprecate later.

### 3.4 Migrations and database ownership

### `migrations/006_action_audit_log.sql`
- Status: partial
- Area: audit / infra
- What it does: Creates `action_audit_log` and indexes for action, user, and timestamp queries.
- What depends on it: `audit_repo`, action runtime, idempotency checks.
- What it depends on: PostgreSQL.
- Agentic relevance: Existing canonical action audit table.
- Problems / risks: No trigger or privilege rule prevents `UPDATE`/`DELETE`; newer event fields are added at runtime instead of by migration.
- Recommended action: extend with one additive hardening migration.

### `migrations/018_user_job_context.sql`
- Status: implemented
- Area: jobs / applications / audit
- What it does: Creates per-user job context.
- What depends on it: Runtime, lifecycle, follow-up, context repositories.
- What it depends on: User/job identifiers.
- Agentic relevance: Existing action/job memory foundation.
- Problems / risks: Overlaps application tracker state.
- Recommended action: keep; document ownership.

### `migrations/019_user_job_context_interaction.sql`
- Status: implemented
- Area: jobs / audit
- What it does: Adds interaction metadata to job context.
- What depends on it: Job action and lifecycle paths.
- What it depends on: Migration 018.
- Agentic relevance: Useful for action receipts and user behavior.
- Problems / risks: Not an immutable event stream.
- Recommended action: keep as current-state storage.

### `migrations/020_user_job_context_gap_filler.sql`
- Status: implemented
- Area: jobs / infra
- What it does: Fills missing context fields.
- What depends on it: Context repository compatibility.
- What it depends on: Earlier context schema.
- Agentic relevance: Supports richer job context.
- Problems / risks: None specific.
- Recommended action: keep as-is.

### `migrations/021_user_job_context_alt_url.sql`
- Status: implemented
- Area: jobs
- What it does: Adds alternate/source URL support.
- What depends on it: Link verification and job cards.
- What it depends on: User job context.
- Agentic relevance: Supports trustworthy apply-link selection.
- Problems / risks: None specific.
- Recommended action: keep as-is.

### `migrations/022_user_job_context_lifecycle.sql`
- Status: implemented
- Area: applications / audit
- What it does: Adds lifecycle status fields to job context.
- What depends on it: `/flow`, opened/applied/follow-up behavior.
- What it depends on: User job context.
- Agentic relevance: Current lifecycle memory.
- Problems / risks: Status overlaps application records.
- Recommended action: consolidate later.

### `migrations/025_learning_signals.sql`
- Status: implemented
- Area: agentic / profile
- What it does: Creates structured learning signals.
- What depends on it: Learning repository and feedback flows.
- What it depends on: Users/profile identity.
- Agentic relevance: Existing preference-learning event source.
- Problems / risks: Runtime code also creates similarly named tables.
- Recommended action: consolidate schema ownership.

### `migrations/026_user_documents_skills_json.sql`
- Status: partial
- Area: CV / infra
- What it does: Adds parsed skills JSON to `user_documents`.
- What depends on it: Multi-CV activation and profile resync.
- What it depends on: A base `user_documents` table created by runtime DDL.
- Agentic relevance: Stores facts needed for tailoring and fit analysis.
- Problems / risks: The base table has no numbered migration in this directory.
- Recommended action: investigate and normalize migration history.

### `migrations/027_followup_reminders.sql`
- Status: implemented
- Area: applications / agentic
- What it does: Adds follow-up timing to recommendations.
- What depends on it: Follow-up service and queue follow-ups.
- What it depends on: Job recommendation table.
- Agentic relevance: Existing reminder foundation.
- Problems / risks: Application drafts also have runtime-added follow-up fields.
- Recommended action: consolidate later.

### `migrations/028_performance_indexes.sql`
- Status: implemented
- Area: infra
- What it does: Adds production query indexes.
- What depends on it: Repositories and operational performance.
- What it depends on: Existing tables.
- Agentic relevance: Supports action/context queries.
- Problems / risks: Comments acknowledge schema differences around audit/job IDs.
- Recommended action: keep as-is.

### Remaining numbered migrations

| Files | Status | Area | Recommendation |
|---|---|---|---|
| `005_mvp_settings_pipeline_runs.sql`, `008_onboarding_state.sql`, `009_saved_searches.sql`, `012_add_updated_at_to_saved_searches.sql`, `024_blocked_companies.sql`, `029_profile_nudge_sent_at.sql` | implemented | profile / jobs / onboarding | Keep; these support current product state but are not new Agentic foundations. |
| `007_users.sql`, `010_password_reset_tokens.sql`, `017_email_verification_tokens.sql` | implemented | auth | Keep; all Agentic routes must preserve this identity boundary. |
| `011_rico_recommendation_uniqueness.sql` | implemented | jobs | Keep; supports deduplication. |
| `013_user_subscriptions.sql` through `016_user_subscriptions_entitlements.sql` | implemented | billing | Keep; use as entitlement input, not permission policy. |
| `023_telegram_notifications.sql` | implemented | integrations | Keep; separate notification state from action audit. |

No migration numbered `030` exists on the audited `main`. PR #685 proposes two different audit migrations; neither should be accepted without consolidation.

### 3.5 Frontend routes, components, and libraries

### `apps/web/app/command/page.tsx`
- Status: implemented
- Area: chat / agentic / CV / frontend
- What it does: Main authenticated/public conversational UI with streaming, jobs, CV upload/confirmation, action cards, permissions, and proposed changes.
- What depends on it: Primary Rico product navigation.
- What it depends on: `lib/api.ts`, canonical schemas, Rico UI components.
- Agentic relevance: Existing production Agentic conversation surface.
- Problems / risks: Large component; future `/ask` could duplicate it instead of reusing its live behavior.
- Recommended action: keep as current production surface; extract shared presentation only when `/ask` is wired.

### `apps/web/app/chat/page.tsx`
- Status: implemented
- Area: chat / frontend
- What it does: Redirects `/chat` to `/command`.
- What depends on it: Legacy links.
- What it depends on: Next redirect.
- Agentic relevance: Confirms `/command` is canonical today.
- Problems / risks: None.
- Recommended action: keep as-is.

### `apps/web/app/orchestrate/page.tsx`
- Status: stale
- Area: agentic / frontend
- What it does: Redirects `/orchestrate` to `/command`.
- What depends on it: Legacy orchestration links.
- What it depends on: Next redirect.
- Agentic relevance: Former orchestration surface has already been demoted.
- Problems / risks: Related orchestration stores/API remain even though route redirects.
- Recommended action: investigate client usage and deprecate dead support code later.

### `apps/web/app/jobs/page.tsx`
- Status: implemented
- Area: jobs / applications / frontend
- What it does: Displays live user jobs and invokes save/skip/apply/status actions.
- What depends on it: Main navigation.
- What it depends on: Jobs/applications API.
- Agentic relevance: Existing job-action surface future action cards must align with.
- Problems / risks: Job action semantics are implemented in more than one UI.
- Recommended action: keep; share canonical action helpers.

### `apps/web/app/flow/page.tsx`
- Status: implemented
- Area: applications / frontend
- What it does: Real application lifecycle/Kanban view.
- What depends on it: `/applications` redirect and navigation.
- What it depends on: Applications API and lifecycle status model.
- Agentic relevance: Existing application tracker; future queue should feed it.
- Problems / risks: Status ownership is split across applications and job context.
- Recommended action: extend; do not replace with a parallel tracker.

### `apps/web/app/applications/page.tsx`
- Status: implemented
- Area: applications / frontend
- What it does: Redirects to `/flow`.
- What depends on it: Legacy links.
- What it depends on: Next redirect.
- Agentic relevance: Confirms `/flow` is canonical tracking UI.
- Problems / risks: None.
- Recommended action: keep as-is.

### `apps/web/app/queue/page.tsx`
- Status: partial
- Area: applications / CV / agentic / frontend
- What it does: Lists real application drafts/follow-ups and supports approve/reject actions.
- What depends on it: Queue navigation.
- What it depends on: Queue API and `ApplicationDraftCard`.
- Agentic relevance: Existing Tailored Application Queue foundation.
- Problems / risks: Product copy can imply send/submission although backend approval changes status only.
- Recommended action: extend after semantic correction and zero-fabrication hardening.

### `apps/web/app/upload/page.tsx`
- Status: implemented
- Area: CV / frontend
- What it does: Uploads and previews CV extraction/profile changes.
- What depends on it: Onboarding/profile workflows.
- What it depends on: CV upload/confirm APIs.
- Agentic relevance: Existing document intake and preview gate.
- Problems / risks: Preview/confirmation and file-manager persistence paths are complex and not fully unified.
- Recommended action: keep; consolidate provenance later.

### `apps/web/app/profile/page.tsx`
- Status: implemented
- Area: profile / CV / frontend
- What it does: Displays and edits profile/document state.
- What depends on it: User account workflow.
- What it depends on: Profile/files APIs.
- Agentic relevance: User-controlled fact source.
- Problems / risks: Agent-proposed changes must remain previewed and explicit.
- Recommended action: extend with canonical proposed-change cards.

### `apps/web/app/settings/page.tsx`
- Status: implemented
- Area: profile / permissions / frontend
- What it does: Manages current user settings and integrations.
- What depends on it: User preferences.
- What it depends on: Settings API.
- Agentic relevance: Natural future place for permission preferences, but P0-P4 do not exist yet.
- Problems / risks: Do not expose permission tiers before backend policy semantics exist.
- Recommended action: keep; add policy settings only after backend foundation.

### `apps/web/app/subscription/page.tsx`
- Status: implemented
- Area: billing / frontend
- What it does: Displays plans and initiates checkout/portal flows.
- What depends on it: Billing navigation.
- What it depends on: Subscription API.
- Agentic relevance: Future capability gating.
- Problems / risks: Mock/manual billing states exist and must not be confused with permission approval.
- Recommended action: keep as-is.

### `apps/web/app/signals/page.tsx`
- Status: partial
- Area: jobs / agentic / frontend
- What it does: Presents opportunity signals.
- What depends on it: Navigation/experiments.
- What it depends on: Job data and frontend intelligence helpers.
- Agentic relevance: Potential read-only P0 Agentic surface.
- Problems / risks: Signal meaning and score provenance need clear labels.
- Recommended action: investigate and align with canonical scoring.

### `apps/web/app/archive/page.tsx`
- Status: partial
- Area: jobs / applications / frontend
- What it does: Presents archived/removed items.
- What depends on it: Navigation.
- What it depends on: Existing job/application APIs.
- Agentic relevance: Could support reversible action history.
- Problems / risks: Not an audit receipt view.
- Recommended action: keep separate from operational audit.

### `apps/web/components/ui/rico/ChatActionCard.tsx`
- Status: implemented
- Area: agentic / frontend
- What it does: Renders canonical action cards.
- What depends on it: `/command`.
- What it depends on: Mirrored `RicoChatAction` schema.
- Agentic relevance: Existing production action-card component.
- Problems / risks: PR #688 introduces separate contextual-action components/types.
- Recommended action: extend/reuse; do not create a second canonical card model.

### `apps/web/components/ui/rico/PermissionRequestCard.tsx`
- Status: implemented
- Area: permissions / agentic / frontend
- What it does: Renders server-issued permission details and approve/review/cancel actions.
- What depends on it: `/command`.
- What it depends on: Permission request schema and execute API.
- Agentic relevance: Real approval UI connected to backend consumption.
- Problems / risks: The live canonical card receives no permission expiry metadata and therefore cannot show the backend's actual deadline.
- Recommended action: extend only after the backend contract exposes `expires_at` or equivalent real expiry metadata.

### `apps/web/components/ui/rico/ProposedChangeCard.tsx`
- Status: implemented
- Area: agentic / profile / frontend
- What it does: Displays current versus proposed values with provenance.
- What depends on it: `/command`.
- What it depends on: Canonical proposed-change schema.
- Agentic relevance: Existing P1/P2 preview primitive.
- Problems / risks: Not every profile mutation path uses it.
- Recommended action: extend adoption.

### `apps/web/components/queue/ApplicationDraftCard.tsx`
- Status: partial
- Area: applications / CV / frontend
- What it does: Displays tailored CV/cover-letter drafts and queue controls.
- What depends on it: `/queue`.
- What it depends on: Queue API types.
- Agentic relevance: Existing tailored-application presentation.
- Problems / risks: Approval wording can imply external send; generated content trust is not surfaced.
- Recommended action: extend with truthful effect labels, provenance, and warnings.

### `apps/web/lib/api.ts`
- Status: implemented
- Area: frontend / infra / agentic
- What it does: Central frontend API client for auth, chat, jobs, applications, files, subscriptions, permissions, and queue.
- What depends on it: Most app routes/components.
- What it depends on: Backend endpoints and environment configuration.
- Agentic relevance: Existing client functions include permission execution and real queue access.
- Problems / risks: Large mock datasets for jobs/applications/queue remain behind `NEXT_PUBLIC_USE_MOCK`; production safety depends on flag discipline.
- Recommended action: keep; split by domain later without behavior change.

### `apps/web/lib/schemas/index.ts`
- Status: implemented
- Area: frontend / agentic
- What it does: Mirrors backend response/action/permission schemas with Zod.
- What depends on it: API parsing and Agentic UI rendering.
- What it depends on: Backend contract parity.
- Agentic relevance: Canonical frontend contract already exists.
- Problems / risks: PR #688's local `types.ts` bypasses it.
- Recommended action: extend and reuse for `/ask`.

### `apps/web/lib/api/orchestration.ts`
- Status: partial
- Area: agentic / frontend
- What it does: Adapts agent chat, jobs, applications, and profile into trajectory/signal views.
- What depends on it: Orchestration store.
- What it depends on: `/api/v1/agent/chat` and other live APIs.
- Agentic relevance: Older orchestration client.
- Problems / risks: Route redirects to `/command`; client depends on duplicate agent endpoint.
- Recommended action: investigate usage; consolidate later.

### `apps/web/lib/store/useOrchestrationStore.ts`
- Status: partial
- Area: agentic / frontend
- What it does: Stores trajectory, signals, and command history for orchestration UI.
- What depends on it: Any remaining orchestration components.
- What it depends on: Orchestration API adapter.
- Agentic relevance: Experimental client state.
- Problems / risks: Likely stranded after `/orchestrate` redirect.
- Recommended action: investigate; deprecate if unused.

### Remaining frontend files

| Files | Status | Area | Recommendation |
|---|---|---|---|
| `app/login`, `signup`, `forgot-password`, `reset-password`, `verify-email`, auth components/store | implemented | auth | Keep; all Agentic surfaces must preserve these guards. |
| `app/dashboard`, `components/Dashboard*`, profile readiness/completion components | implemented | frontend / profile | Keep; reuse live metrics and avoid duplicate Agentic dashboards. |
| `app/onboarding`, saved searches, admin leads | implemented | onboarding / jobs / admin | Keep; adjacent but not policy foundation. |
| Layout/navigation components | implemented | frontend | Keep; `/ask` should enter navigation only after product status is explicit. |
| Landing/about/contact/FAQ/legal/PWA files | implemented | marketing / infra | Ignore for Agentic implementation. |
| Shared/UI primitives and Rico visual primitives | implemented | frontend | Reuse; do not duplicate visual systems in `/ask`. |
| `lib/intelligence/*`, `lib/trajectoryHelpers.ts`, `lib/config/trajectory.ts`, `lib/memory/index.ts` | partial | agentic / frontend | Investigate current callers and evidence before treating as product intelligence. |

### 3.6 Workspace and product documentation

### `AI_WORKSPACE/CURRENT_STATE.md`
- Status: stale
- Area: docs / infra
- What it does: Records a previous production/main snapshot and active tasks.
- What depends on it: Agent handoffs.
- What it depends on: Manual updates.
- Agentic relevance: Useful historical context.
- Problems / risks: Main SHA and Agentic foundation state predate #672/#673/#676/#677/#700/#701.
- Recommended action: update in a separate docs PR after this inventory.

### `AI_WORKSPACE/START_HERE.md`
- Status: stale
- Area: docs
- What it does: Directs new sessions to current handoffs.
- What depends on it: Agent onboarding.
- What it depends on: Workspace state docs.
- Agentic relevance: Should eventually point to this inventory and current roadmap.
- Problems / risks: Latest handoff focus is behind current Agentic merges.
- Recommended action: update separately; PR #695 overlaps.

### `AI_WORKSPACE/TASKS.md`
- Status: stale
- Area: docs
- What it does: Large historical task ledger.
- What depends on it: Planning sessions.
- What it depends on: Manual maintenance.
- Agentic relevance: Contains useful older requirements.
- Problems / risks: Many active/completed labels are no longer reliable.
- Recommended action: consolidate later; do not use as live truth without verification.

### `AI_WORKSPACE/ARCHITECTURE.md`
- Status: partial
- Area: docs / infra
- What it does: Summarizes current architecture and legacy bridge.
- What depends on it: Engineering orientation.
- What it depends on: Manual updates.
- Agentic relevance: Correctly identifies the repo adapter/legacy pipeline bridge.
- Problems / risks: Simplifies the three parallel agent stacks and runtime DDL.
- Recommended action: extend after architecture consolidation.

### `AI_WORKSPACE/HANDOFFS/2026-06-20-agentic-ui-implementation-brief.md`
- Status: partial
- Area: docs / agentic
- What it does: Defines implementation expectations for Agentic UI.
- What depends on it: Recent Career OS work.
- What it depends on: #683-era state.
- Agentic relevance: Useful guardrails.
- Problems / risks: Some planned work is now merged.
- Recommended action: retain as historical handoff; reference this inventory for current state.

### `AI_WORKSPACE/HANDOFFS/2026-06-20-rico-career-os-roadmap.md`
- Status: partial
- Area: docs / agentic
- What it does: Proposes staged Career OS delivery.
- What depends on it: Planning.
- What it depends on: Pre-#700/#701 assumptions.
- Agentic relevance: Useful product sequence.
- Problems / risks: Must be reconciled with actual duplicate stacks and existing queue/tailoring code.
- Recommended action: revise separately based on this audit.

### `docs/agentic-ux-contract.md`
- Status: partial
- Area: docs / agentic / permissions / audit
- What it does: Defines action cards, P0-P4 permission vision, approval UX, and audit model.
- What depends on it: Agentic PR planning.
- What it depends on: Product intent, not current code.
- Agentic relevance: Primary design contract.
- Problems / risks: Status says not implemented although parts are implemented. Its signed-token and 5-minute examples are design text, not confirmed live behavior.
- Recommended action: update implementation matrix separately.

### `docs/rico-agentic-vision-github-intelligence.md`
- Status: partial
- Area: docs / agentic
- What it does: External-repo intelligence, gap analysis, and proposed roadmap.
- What depends on it: Agentic planning.
- What it depends on: External research and a snapshot of Rico.
- Agentic relevance: Broad vision input.
- Problems / risks: Calls existing tailoring/queue/cover-letter capabilities absent and proposes new HMAC/audit systems that duplicate current foundations.
- Recommended action: treat as research, not implementation truth; reconcile with this inventory.

### `docs/architecture/agentic-ui-action-layer.md`
- Status: implemented
- Area: docs / agentic
- What it does: Documents the current action-layer architecture and safety rules.
- What depends on it: Action UI/runtime work.
- What it depends on: Existing action runtime and contracts.
- Agentic relevance: Closer to current code than the broad vision report.
- Problems / risks: Must be updated as policy/audit hardening lands.
- Recommended action: keep and extend.

### `docs/STATEFUL_AGENT_ARCHITECTURE.md`
- Status: partial
- Area: docs / agentic
- What it does: Describes the stateful coordinator architecture.
- What depends on it: Older coordinator work.
- What it depends on: Parallel stateful modules.
- Agentic relevance: Explains useful context/identity concepts.
- Problems / risks: Can be mistaken for the canonical production path.
- Recommended action: label implementation status and consolidation decision.

### `docs/FRONTEND_BACKEND_ENDPOINT_MAPPING.md`
- Status: implemented
- Area: docs / frontend / infra
- What it does: Maps frontend calls to backend endpoints.
- What depends on it: Integration/debug work.
- What it depends on: Current routes.
- Agentic relevance: Useful for `/ask` wiring and duplicate endpoint discovery.
- Problems / risks: Must be refreshed after endpoint consolidation.
- Recommended action: keep.

### `docs/product/application-tracking.md`
- Status: implemented
- Area: docs / applications
- What it does: Documents lifecycle behavior.
- What depends on it: Tracker implementation/tests.
- What it depends on: Applications and lifecycle routes.
- Agentic relevance: Existing queue/tracker contract.
- Problems / risks: Must reflect queue approval versus external submission.
- Recommended action: extend.

### `docs/product/chat-routing-contract.md`
- Status: implemented
- Area: docs / chat
- What it does: Defines deterministic chat routing expectations.
- What depends on it: Chat tests and implementation.
- What it depends on: Production Rico chat behavior.
- Agentic relevance: `/ask` backend must preserve routing truthfulness.
- Problems / risks: None specific.
- Recommended action: keep.

### Remaining docs

| Files | Status | Recommendation |
|---|---|---|
| `docs/product/rico_behavior_spec.md`, `rico-product-model.md`, `subscription-flow.md` | implemented/partial | Keep as product contracts; verify against code before implementation. |
| `docs/SECURITY.md`, `PRODUCTION_READINESS.md`, operations smoke/status docs | implemented/partial | Keep; production facts are time-sensitive. |
| `docs/DEEP_ARCHITECTURE_ANALYSIS.md`, `PRODUCTION_ROADMAP.md` | stale | Historical May-era architecture/planning; do not use as current truth. |
| `docs/proposals/*` | prototype | Proposal-only; no implementation assumption. |
| `docs/archive/*` | stale/archive | Ignore for new implementation except historical context. |
| Frontend audits/localization/integration docs | implemented/partial | Useful domain references, not Agentic foundations. |

### 3.7 Test inventory and current evidence

The most relevant tests are:

| File | What it proves | Status |
|---|---|---|
| `tests/test_pending_permissions_job_binding.py` | Permission is bound to the intended job. | implemented |
| `tests/test_permission_execute.py` | Fabricated, expired, reused, wrong-user, and wrong-action permission IDs are rejected; approved apply does not loop. | implemented |
| `tests/test_apply_approval_gate.py` | `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS` defaults to blocking unapproved application submission. | implemented |
| `tests/test_bulk_apply_safety.py` | Bulk/unsafe apply behavior remains restricted. | implemented |
| `tests/test_action_endpoint.py` | Authenticated universal action endpoint behavior, including rejection of a client-forged `_approved` sentinel. | implemented |
| `tests/test_agent_runtime.py` | Runtime validation, idempotency, tool dispatch, audit, and permission composition. | implemented |
| `tests/unit/test_write_audit_log.py` | Audit event writes, fallback behavior, connection handling, and #701 transaction commit. | implemented |
| `tests/test_agentic_ui_contracts.py` | Backend Agentic UI schema compatibility. | implemented |
| `tests/test_agentic_ui_composer.py` | Runtime artifact to canonical UI composition. | implemented |
| `tests/test_match_explanation.py` | Deterministic match explanation behavior. | implemented |
| `tests/unit/test_fit_score_badge.py` and `tests/test_score_normalization.py` | Frontend/backend score normalization expectations. | implemented |
| `tests/unit/test_resume_screener.py` | Unused deterministic resume screener behavior. | implemented, runtime unused |
| `tests/test_application_drafts_activation.py` | Queue intent, preparation, approve/reject/follow-up API behavior. | implemented |
| `tests/test_application_lifecycle.py`, `test_job_lifecycle.py`, `test_manual_application_tracking.py` | Application tracker/lifecycle behavior. | implemented |
| `tests/test_cv_generation_continuity.py` | Deterministic CV builder avoids placeholders/invented metrics. | implemented |
| `tests/test_cover_letter_writer.py` | Identity-bound cover letters avoid generic/hardcoded identity claims. | implemented |
| `tests/test_document_storage_quotas.py`, `test_cv_activation_resync.py`, `unit/test_document_resolver.py` | Multi-CV quotas, primary CV switching, and active CV resolution. | implemented |
| `tests/test_upload_document_intelligence.py`, `src/tests/test_document_classifier.py` | Pre-upload document classification. | implemented |
| `tests/test_jwt_user_isolation.py`, `test_user_isolation.py`, `test_chat_identity_contamination.py` | User identity/isolation boundaries. | implemented |
| `tests/unit/test_policy_gateway.py` | Domain/capability routing gateway, not an action authorization policy gate. | implemented |
| `tests/test_agent.py` | Older `/agent` orchestrator contracts. | implemented, duplicate-path evidence |

The rest of the 225-file suite covers auth, Arabic routing, job-source quality, profile persistence, billing, Telegram/JotForm, provider resilience, chat regression, follow-ups, and production hardening. These are important regression coverage but do not establish a unified Agentic policy/audit architecture.

Focused audit verification run:

```text
164 passed, 29 warnings in 83.09s
```

Command scope:

```text
tests/test_pending_permissions_job_binding.py
tests/test_permission_execute.py
tests/test_apply_approval_gate.py
tests/unit/test_write_audit_log.py
tests/test_match_explanation.py
tests/test_application_drafts_activation.py
tests/test_cv_generation_continuity.py
tests/unit/test_resume_screener.py
```

## 4. Agentic Foundation Map

### 4.1 Permission / Approval System

#### How permissions are issued

`src/services/permission_factory.py` creates a server-issued opaque permission ID when the runtime receives `approval_required` from the apply tool. It builds a `RicoPermissionRequest`, registers the ID in `pending_permissions`, and returns actions pointing to `/api/v1/rico/actions/execute`.

#### How they expire

`src/services/pending_permissions.py` stores a monotonic expiry timestamp using the internal `_TTL_SECONDS` setting and deletes expired records during validation. The canonical `RicoPermissionRequest` response does not include `expires_at` or `expires_in_seconds`, and the live `PermissionRequestCard` does not render a countdown.

#### How they are consumed

`POST /api/v1/rico/actions/execute` derives the user from JWT, validates permission ID + user + action + job key, consumes the record, then calls `agent_runtime.handle_action(..., pre_approved=True)`.

PR #705 also strips `_approved` from client-provided job payloads at `/api/v1/actions/run`. This closes the known path where a caller could otherwise forge the runtime's internal approval sentinel.

#### One-time use and rejection behavior

- Valid permission: deleted before execution, so it is one-time use.
- Wrong user: rejected and not consumed.
- Wrong action: rejected and not consumed.
- Wrong job: rejected and not consumed.
- Expired ID: rejected and removed.
- Fabricated/unknown ID: rejected.
- Denials: audited through `audit_repo.log_action`.

#### Expiry metadata versus prototype countdowns

There is no confirmed live five-minute approval countdown. PR #688 hardcodes a local 300-second timer inside its mock-only `ApprovalSheet`; that timer is not sourced from the backend and is not authoritative. The required correction is to expose the real permission expiry metadata from the backend to the canonical UI contract. Any countdown must be derived from that server value rather than a client constant.

#### Redis timing

Redis is not required immediately for one process. It becomes necessary when:

- More than one API worker/process can receive issue/consume requests.
- Permissions must survive process restart/deploy.
- Atomic cross-process one-time consumption is required.
- Revocation/observability needs exceed in-memory storage.

Until then, the lock-protected in-memory store is safer than introducing an unreviewed distributed token system.

#### HMAC token decision

An HMAC token is not currently required. The opaque server-issued ID is already a bearer capability backed by server-side state and exact binding checks. HMAC becomes useful if Rico intentionally moves to stateless signed approvals or cross-service validation. Adding HMAC now would duplicate the pending-permission store without solving its actual single-process limitation.

#### Parallel permission risk

`src/agent/workflow/coordinator.py` has a separate confirmation-token dictionary and a different permission enum. It lacks TTL, lock, job binding, and canonical audit behavior. That path should not be extended.

### 4.2 Audit System

#### What is logged

The current action audit captures:

- `action_id`
- action type
- user email
- job identifiers/title/company
- timestamp
- result status/message
- duration
- failure reason

Permission denials are now written as action audit records. Stateful context code can also write generic event types/data, and separate helpers log learning, profile hydration, and permission checks.

#### Where it is logged

Primary storage is PostgreSQL `action_audit_log`; there is an in-memory fallback used for resilience/idempotency behavior. PR #701 fixed the missing commit so DB inserts persist.

#### Append-only status

Application code inserts records and does not normally update them. The database does not enforce append-only behavior:

- No trigger rejects `UPDATE` or `DELETE`.
- Table privileges do not visibly remove update/delete.
- Any sufficiently privileged connection can mutate history.

Therefore it is append-only by convention, not by guarantee.

#### Operational memory sufficiency

The table is enough for action outcome history and idempotency. It is not enough for full operational memory because it does not consistently represent:

- action proposed/created
- policy evaluated
- approval requested/granted/denied/expired
- execution started/completed
- before/after values
- external systems touched
- reversibility/undo data
- correlation/trace/permission IDs

#### Extend existing table or add `agent_audit_events`

Extend `action_audit_log`. A second `agent_audit_events` table would split action history and force dual writes/migration. The safest later migration is additive:

1. Add nullable `event_type`, `correlation_id`, `permission_id`, `policy_decision`, `risk_class`, `metadata`, `before_state`, `after_state`, `external_systems`, and `reversible`.
2. Backfill existing rows as `action_completed` where appropriate.
3. Add indexes for correlation/user/event/time.
4. Add a trigger rejecting `UPDATE` and `DELETE`.
5. Change repository code to INSERT-only without runtime `ALTER TABLE`.
6. Migrate or retire the three runtime-created audit helper tables deliberately.

PR #685 is superseded/duplicate-risk and must not be merged. In particular, it must not add either parallel audit model as a second foundation alongside `action_audit_log`.

### 4.3 Policy Gate

No explicit canonical action policy gate exists today.

`src/rico/policy/` is a request-domain/capability gateway. It decides whether Rico supports a requested tool/domain; it does not authorize side effects.

Current blocking is implicit and distributed:

- JWT dependencies protect routes.
- Action schemas allowlist executable actions.
- `agent_runtime` checks idempotency and subscriptions.
- `apply_service` enforces `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS`.
- `RICO_ENABLE_AUTO_APPLY` defaults false.
- Pending permission validation binds approved execution.
- `rico_safety.py` blocks unsafe command categories.

`RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` is enforced. The default is approval required even when the environment variable is absent, and agent/automation paths do not pass approval unless a valid permission has been consumed.

P0/P1/P2/P3/P4 exist in docs only. The stateful workflow has a different enum (`SAFE`, `REQUIRES_CONFIRMATION`, `AUTO_ONLY`, `PROHIBITED`) and must not be treated as P0-P4 implementation.

A real policy gate needs:

- One action registry with side effect, risk, external systems, reversibility, entitlement, and approval metadata.
- One policy decision function called by every action execution path.
- A decision result: allow, deny, require approval, reason, policy version.
- Canonical pending-permission issuance/consumption.
- Audit events for every decision and approval transition.
- No LLM authority to bypass the decision.

It does not initially need a new HTTP token-issuance endpoint.

### 4.4 Match Explanation / Scoring

Current deterministic explanation:

- `src/rico_match_explainer.py`: V1 deterministic evidence from title, skills, location, and profile.
- `src/services/job_match_explanation.py`: V2 deterministic verdict/summary around an existing score.
- `src/rico_chat_api.py` invokes both in at least one match-formatting path.

Current score sources:

- `src/llm_scorer.py`: embedding/keyword and fast profile-fit ranking.
- `src/scoring.py`: legacy HSE scoring plus user-specific logic.
- `src/agent/intelligence/scorer.py`: predefined role-family fit.

What is not ATS scoring:

- The displayed job score is an internal relevance/profile-fit heuristic.
- The explainers do not simulate an ATS parser/ranker.
- A verdict derived from an existing score does not make the score ATS-valid.

FitScorer path:

- Evaluate `src/resume_screener.py` as the deterministic JD/CV gap core.
- Reuse normalized profile/job evidence from current ranking.
- Produce a versioned result separating `rico_fit_score`, `resume_jd_score`, and explanation.
- Keep deterministic evidence separate from optional LLM wording.

Do not create a new FitScorer before consolidating these four existing scoring/explanation implementations.

### 4.5 CV / Documents / Tailoring

What exists:

- PDF/DOCX/TXT CV parsing.
- Document classification before CV handling.
- Authenticated multi-document storage and quotas.
- Primary/active CV selection and profile resync.
- Canonical active-CV resolver with fallback.
- Deterministic chat CV builder that uses extracted facts and avoids placeholders.
- Identity-bound cover-letter generator.
- Queue-connected per-job AI tailoring.

What is parser/storage only:

- `cv_parser`, `files` router, `document_resolver`, and `user_documents` manage facts and sources; they do not safely tailor per job by themselves.

What is deterministic CV builder:

- The CV builder in `rico_chat_api.py` builds from stored profile/CV facts and is covered by no-placeholder/no-invented-metric tests.

What is missing for safe per-job tailoring:

- A canonical tailoring request model using active CV + exact job description.
- Fact provenance and an allowlist of claims.
- Structured proposed changes/diff.
- Deterministic post-generation verification.
- Explicit warnings when job or CV evidence is insufficient.
- Versioned artifact storage and user acceptance before use.

Zero-fabrication:

- Do not rely on prompts alone.
- No new employer, title, dates, metrics, certifications, skills, achievements, identity fields, or contact details may appear unless traceable to a source fact.
- `rico_apply_ai` fallback must not emit `[Your Name]` or unsupported confidence claims.
- Reuse `cover_letter_writer.py` and the deterministic CV builder rather than creating parallel generators.

### 4.6 Applications / Queue / Flow

Implemented:

- Real saved/opened/applied/interview/rejected/offer lifecycle tracking.
- Manual application recording.
- `/flow` application tracker.
- `/queue` backed by `application_drafts`.
- Draft prepare/list/approve/reject/follow-up endpoints.
- Follow-up timing and lifecycle context.

Partial:

- Queue preparation uses per-job tailoring, but trust validation is incomplete.
- Queue approval updates state and lifecycle; it does not send an external application.
- Application status exists in both recommendation/application records and user job context.
- UI/API wording does not always distinguish “approved draft,” “marked applied,” and “externally submitted.”

Fake/prototype:

- Frontend mock jobs/applications/queue exist only when `NEXT_PUBLIC_USE_MOCK=true`.
- Browser engines are disabled prototypes, not the queue's execution backend.

Future Tailored Application Queue:

- Extend `/queue`, `application_drafts`, and `/flow`.
- Add truthful draft states such as `draft`, `ready_for_review`, `approved_for_manual_use`, `submission_pending`, `submitted`, `failed`.
- Never infer external submission from an approval click.
- Add provenance, fit gaps, CV diff, cover-letter draft, permission state, and receipt.

### 4.7 `/ask` Agentic UX

PR #688 is open and not merged.

Files added:

- `apps/web/app/ask/page.tsx`
- Ten components plus `mockData.ts` and `types.ts` under `apps/web/components/agentic/`
- `docs/product/rico-agentic-conversational-ux.md`

Current behavior:

- Auth guard: yes, via `fetchMe`; unauthenticated users redirect to `/login?next=/ask`.
- Preview/Demo banner: yes, always visible in the latest PR head.
- Backend calls: no.
- Real jobs/actions: no.
- Approval: simulated in client state with a hardcoded 300-second countdown and timeout; it is not backend expiry.
- Backend files changed: no.

Before preview mode can be removed:

1. Rebase on current `main`.
2. Replace local answer/action types with canonical `RicoAgenticUi`/Zod contracts.
3. Call authenticated Rico chat/stream endpoints.
4. Render real server-provided actions, permissions, progress, and proposed changes.
5. Execute approvals through the existing permission endpoint.
6. Add real permission expiry metadata to the canonical backend/frontend contract and derive any countdown from it.
7. Add error, rate-limit, session expiry, empty-result, and no-fabrication behavior.
8. Add frontend tests and run `npm run build`.
9. Keep explicit Preview labeling until all cards are backed by live data.

## 5. Duplicate / Parallel System Risks

| Existing system | Proposed/new system | Risk of duplication | Recommended consolidation path |
|---|---|---|---|
| `pending_permissions.py` server-issued, stateful, one-time IDs | Superseded PR #685 HMAC approval tokens and token tables | Two approval authorities with different binding/revocation behavior | Keep pending permissions as canonical. Expose its real expiry metadata; add Redis only when required. Do not merge #685. |
| `action_audit_log` + `audit_repo.py` | Superseded PR #685 `agent_audit_events`, `agent_audit_log`, and new `audit_writer.py` | Split history, dual writes, incompatible schemas, migration ambiguity | Add one migration to extend and protect `action_audit_log`; do not merge #685. |
| `rico_match_explainer.py`, `job_match_explanation.py`, current rankers, unused `resume_screener.py` | New `FitScorer` from the intelligence report | Fifth scoring/explanation implementation with unclear score meaning | Build a versioned facade around existing ranking + resume screener + one explanation model. |
| `src/schemas/chat.py` + mirrored frontend Zod + Rico action components | PR #688 local `types.ts`, contextual actions, risk badges | Incompatible impact/risk values and duplicate rendering logic | Adapt `/ask` components to canonical schemas; extract shared visual pieces only. |
| `/command` + `/api/v1/rico/chat` | `/ask` prototype | Two conversational products with divergent truth, history, tools, and permissions | Keep `/command` as production backend/surface; make `/ask` a presentation mode over the same backend contracts. |
| `/flow` application tracker + `/queue` application drafts | Proposed Tailored Application Queue | New queue/table would duplicate existing drafts and lifecycle | Extend current queue and make it feed the existing tracker with explicit state transitions. |
| Deterministic CV builder + `cover_letter_writer.py` + `rico_apply_ai.py` | New CVTailor/CoverLetterWriter agents | Parallel generators with different truth guarantees | Use active CV resolver, deterministic builder, and safe writer as components; harden `rico_apply_ai` or replace its internals without a new product path. |
| `agent_runtime` | Older orchestrator and stateful workflow coordinator | Three execution, permission, audit, and intent stacks | Declare `agent_runtime` canonical; migrate callers and retire duplicate confirmation/action execution. |
| `src/agent/registry/tool_registry.py` | `src/rico_tool_registry.py` | Two capability catalogs with different consumers/metadata | Define shared capability metadata or an adapter; avoid a third Agentic registry. |
| Applications repository | `user_job_context` lifecycle | Two current-state representations | Assign one canonical application status and use job context for interaction/context fields or events. |
| Numbered migrations | Runtime DDL in `rico_db.py`, `audit_repo.py`, `learning_repo.py` | Production schema differs by code path/startup history | Move schema changes into migrations incrementally; stop runtime `ALTER/CREATE` after migration coverage exists. |

## 6. What is already done

| Area | Done | Evidence | File/PR | Notes |
|---|---|---|---|---|
| Auth | Yes | JWT/cookie auth, protected dependencies, isolation tests | `src/api/auth.py`, `src/api/deps.py` | Agentic routes already have a secure identity boundary when they use these dependencies. |
| User profile | Yes | Persistent profile/settings, inline update, hydration | `profile_repo.py`, Rico chat/profile APIs | Provenance remains distributed. |
| CV upload | Yes | Parse, preview, confirm, authenticated file upload | `cv_parser.py`, `rico_chat.py`, `files.py` | Multiple intake paths exist. |
| Multi-CV | Yes | Quotas, list, labels/types, primary CV switch | `files.py`, `document_resolver.py`, tests | Base table migration ownership needs cleanup. |
| Job search | Yes | JSearch/source pipeline, profile ranking, live job APIs/chat | `jsearch_client.py`, `rico_repo_adapter.py`, `jobs_service.py` | Legacy pipeline bridge remains. |
| Match explanation | Yes | Deterministic V1/V2 explanations | `rico_match_explainer.py`, `job_match_explanation.py` | Duplicate explanation paths; not ATS scoring. |
| Application tracker | Yes | `/flow`, lifecycle API/repository/status tests | `applications.py`, `applications_repo.py`, `/flow` | State ownership is split. |
| Permission approval | Yes | Server-issued bound expiring ID, one-time consume, execution endpoint, client-sentinel sanitization | #673, #700, #705; `pending_permissions.py` | Backend expiry exists but is not exposed to canonical UI clients. |
| Audit log | Yes, basic | Action outcome rows, denial logging, committed DB writes | `006_action_audit_log.sql`, `audit_repo.py`, #701 | Not DB-enforced append-only or full event sequence. |
| Agentic UI contract | Yes | Backend Pydantic, frontend Zod, cards, tests | #672, #673, #676 | Canonical contract should be reused by `/ask`. |
| `/ask` prototype | Yes, prototype | Auth guard, Preview banner, structured mock cards | PR #688 | No backend wiring; local countdown is not real permission expiry. |
| GitHub intelligence report | Yes, docs | Report exists on `main`; two overlapping open PRs | `docs/rico-agentic-vision-github-intelligence.md`, #698/#699 | Contains stale assumptions about current Rico. |
| Queue | Yes, partial product | Draft prepare/list/approve/reject/follow-up and UI | `apply_queue.py`, `/queue` | Approval is not external submission. |
| Billing/subscription | Yes | Plans, checkout/portal, webhook, entitlements | subscription router/repos/services | Keep separate from permission risk. |
| Arabic support | Yes | Arabic translations, intents, application/chat tests | `translations.ts`, intent classifier, tests | Coverage is substantial but not universal for generated documents. |
| UAE targeting | Yes | UAE identity, job sources/locations, Naukrigulf path | `rico_identity.py`, sources, docs | A core differentiator already present. |

## 7. What is partially done

| Area | Current state | Missing piece | Risk | Next action |
|---|---|---|---|---|
| Action policy | Distributed gates in runtime, safety, subscriptions, apply service, pending permissions | One canonical policy decision and action metadata registry | Different paths can authorize differently | Add policy metadata and one pre-execution decision in `agent_runtime`. |
| Operational audit | Action outcomes persist; helper event writes exist | Append-only DB enforcement, correlation, approval/policy/before-after events | Incomplete history and runtime schema drift | Extend `action_audit_log` with a migration. |
| Permission service | Strong single-process validation | Shared/durable atomic store and server expiry metadata | Restart/multi-worker loss | Keep now; move to Redis when topology requires it. |
| Scoring | Several ranking/scoring/explanation implementations | Versioned score taxonomy and runtime resume/JD gap score | Users may read a heuristic as ATS probability | Consolidate existing scorers. |
| CV tailoring | Queue-connected AI tailoring exists | Fact verifier, provenance, diff, safe fallback | Fabricated/placeholder content | Harden current path; reuse safe writer/builder. |
| Cover letters | Identity-safe generator and queue generator both exist | One canonical generator integrated with queue and job facts | Different truth guarantees | Route queue through `cover_letter_writer.py` plus verification. |
| Application queue | Real drafts and UI | Truthful state model and external execution separation | “Approve” can be interpreted as “sent” | Rename states/copy and add receipts. |
| Application state | Application repo and job context both track lifecycle | One owner and defined synchronization | Conflicting status | Document and consolidate incrementally. |
| Career memory | Learning signals, chat memory, job context, career memory | Unified read model and operational events | Fragmented context | Build read model after audit events. |
| Stateful agent | Identity/context/workflow coordinator exists | Integration decision with production chat/runtime | Fourth architecture may emerge | Extract reusable context ideas; retire duplicate execution. |
| `/ask` | Complete visual prototype | Live chat/action/permission/audit wiring | Mock product could be mistaken for real | Keep Preview until canonical backend integration. |
| Browser apply | Board-specific disabled modules exist | Production policy, sessions, preflight, receipts, maintenance strategy | External side effects and fragility | Defer to later P3 work. |
| Database migrations | Many numbered migrations | Coverage for runtime-created tables/columns | Environment-dependent schema | Move runtime DDL to migrations in small PRs. |

## 8. What is not started

“Not started” below means the production-grade Agentic capability is not implemented. Some rows have reusable partial components, which are called out explicitly.

| Feature | Why it matters | Prerequisites | Recommended PR |
|---|---|---|---|
| Real policy gate | Makes every side effect use the same allow/deny/approval rules | Canonical action metadata; audit event schema; existing pending permissions | `feat/agentic-policy-decision` |
| Operational memory events | Gives Rico trustworthy action/approval history and receipts | Audit schema hardening | `feat/agentic-operational-events` |
| ATS/FitScorer | Separates resume/JD compatibility from generic job relevance | Scoring taxonomy; activate/adapt `resume_screener.py`; provenance | `feat/fit-scorer-v1` |
| Production per-job CV tailoring | Creates a truthful tailored artifact and diff | Active CV resolver; FitScorer; fact verifier; artifact schema | `feat/per-job-cv-tailoring-v1` |
| Production queue-integrated cover letter generation | Produces job-specific, identity-safe drafts | Canonical safe writer; verified job/company facts; fact verifier | `feat/cover-letter-draft-v1` |
| Company research | Improves tailoring and interview context without inventing facts | Trusted source policy, citations, caching, prompt-injection controls | `feat/company-research-context-v1` |
| Outreach drafts | Creates recruiter/follow-up drafts without sending | Verified identity/job/contact facts; P1 draft contract | `feat/outreach-drafts-v1` |
| Browser-assisted apply | Supports external forms while preserving approval and receipts | Mature P3 policy, secure session handling, preflight, audit, failure recovery | `feat/browser-assisted-apply-pilot` only after earlier gates |
| Real `/ask` backend wiring | Delivers the new UX on actual Rico data | Canonical chat schemas, permission execution, shared components, error handling | `feat/ask-live-backend` |

Clarifications:

- ATS/FitScorer is not greenfield: `resume_screener.py` and existing rankers are inputs.
- Per-job tailoring is not greenfield: `rico_apply_ai.py` exists but is not safe enough for production claims.
- Cover-letter generation is not greenfield: `cover_letter_writer.py` exists; the missing work is canonical queue integration and verification.
- Browser automation code exists, but the production Agentic feature is not started.

## 9. Recommended PR Roadmap from current reality

### PR 1 — `feat/action-audit-schema-hardening`

Already completed by #700–#707:

- Permission IDs are job-bound and denial attempts are audited.
- `action_audit_log` inserts commit.
- Application-attempt/dedup writes commit and close connections.
- Identity merge closes its database connection on all paths.
- `/actions/run` strips forged `_approved`.
- The hardening batch has a live-verification record in `AI_WORKSPACE/DECISIONS.md`.

Goal: Address only what remains in the existing audit persistence layer: extend `action_audit_log`, move its schema changes out of request-time code and into a numbered migration, and add database-level append-only protection where safe. Do not introduce a new audit table, token system, or permission behavior change.

Changed files:

- New additive migration for `action_audit_log`
- `src/repositories/audit_repo.py`
- `tests/unit/test_write_audit_log.py`
- New focused migration/immutability test if required

Tests:

- Existing audit repository tests
- Insert/commit test
- Event-column write/read test
- Database trigger rejects update/delete
- No runtime `ALTER TABLE` in request path

Do-not-touch:

- Frontend
- `/ask`
- Pending permission token format
- `agent_approval_tokens` or any duplicate HMAC approval system
- A duplicate `audit_writer.py`
- A new parallel `policy_gate.py`
- `agent_audit_events`; reconsidering a separate event table is a later architecture decision only if a documented review proves `action_audit_log` cannot meet the requirements
- Apply engines
- Billing
- Chat routing
- Production DB execution

Dependency: none beyond current `main`.
Risk level: low-medium because it changes persistence schema, but scope is narrow and additive.

### PR 2 — `feat/permission-expiry-metadata`

Goal: Expose the actual backend permission deadline to canonical clients without changing the chosen internal duration in the same PR.

Changed files:

- `src/services/pending_permissions.py`
- `src/services/permission_factory.py`
- `src/schemas/chat.py`
- `apps/web/lib/schemas/index.ts`
- `apps/web/components/ui/rico/PermissionRequestCard.tsx`
- Focused backend/frontend tests

Tests:

- Issued permission response includes backend-derived expiry metadata.
- UI countdown/deadline is derived from server metadata, never a hardcoded 300 seconds.
- Expired permissions remain rejected and one-time consumption remains unchanged.
- Missing expiry metadata remains backward compatible during rollout.

Do-not-touch:

- Internal expiry duration
- HMAC/stateless tokens
- Redis
- `/ask` mock implementation
- Action policy semantics

Dependency: none.
Risk level: low.

### PR 3 — `feat/agentic-policy-decision`

Goal: Add one explicit policy decision object and action metadata used by `agent_runtime`.

Changed files:

- `src/schemas/actions.py`
- `src/agent/registry/tool_registry.py`
- New small policy module under `src/agent/` or `src/services/`
- `src/agent/runtime.py`
- Focused tests

Tests:

- Read-only allow
- Draft allow
- Internal write requires configured approval
- External apply requires valid consumed permission
- Bulk external deny
- Subscription denial remains separate and explicit
- Every decision produces an audit event

Do-not-touch:

- Intent classifier
- `/ask`
- HMAC/stateless tokens
- Browser automation
- Billing plan definitions

Dependency: PR 1.
Risk level: medium.

### PR 4 — `fix/application-draft-truthfulness`

Goal: Make queue states/copy truthful and remove any implication that draft approval equals external submission.

Changed files:

- `src/api/routers/apply_queue.py`
- Queue schemas/storage state mapping
- `apps/web/app/queue/page.tsx`
- `apps/web/components/queue/ApplicationDraftCard.tsx`
- Focused backend/frontend tests

Tests:

- Approve means approved draft/ready state only
- No applied/submitted status without a real external event
- Follow-up scheduling only after a confirmed application event

Do-not-touch:

- Browser apply
- New queue table
- `/flow` redesign
- Tailoring generation content

Dependency: none, but should follow policy/audit decisions for consistent receipts.
Risk level: medium because user-visible lifecycle semantics change.

### PR 5 — `feat/fit-scorer-v1`

Goal: Consolidate existing scoring into versioned Rico fit and resume/JD gap results.

Changed files:

- `src/resume_screener.py`
- One scoring facade/service
- `src/services/job_match_explanation.py`
- Jobs response schema/service
- Focused scoring tests

Tests:

- Deterministic same-input result
- Score component bounds
- Missing CV/JD behavior
- No “ATS probability” wording
- Explanation evidence matches score inputs

Do-not-touch:

- AI tailoring
- Application submission
- Existing ranking order until explicitly approved

Dependency: none technically; benefits from PR 1 for version/event metadata.
Risk level: medium.

### PR 6 — `feat/per-job-cv-tailoring-v1`

Goal: Produce a verified, reviewable CV diff for one job without invented facts.

Changed files:

- `src/rico_apply_ai.py` or a narrowly extracted tailoring service
- `src/services/document_resolver.py`
- Existing deterministic CV builder helpers
- Artifact schema/storage
- Focused zero-fabrication tests

Tests:

- Every generated claim maps to source fact
- No placeholders
- No new metrics/dates/employers/certifications
- Insufficient-data warnings
- Stable diff and provenance

Do-not-touch:

- Browser apply
- Auto-send
- Bulk processing
- New CV storage system

Dependency: FitScorer and policy/audit foundation.
Risk level: high due to generated career documents.

### PR 7 — `feat/cover-letter-draft-v1`

Goal: Integrate `cover_letter_writer.py` into the queue with job evidence and verification.

Changed files:

- `src/cover_letter_writer.py`
- Queue preparation service/router
- Draft artifact tests

Tests:

- Verified identity only
- No unsupported claims
- Job/company facts traceable
- Arabic/English behavior
- Draft-only status

Do-not-touch:

- Sending email
- External application submission
- New writer implementation

Dependency: PR 6 verifier/artifact model.
Risk level: medium-high.

### PR 8 — `feat/ask-live-backend`

Goal: Convert PR #688 from mock prototype into a live presentation layer over existing Rico contracts.

Changed files:

- PR #688 `/ask` page/components
- Shared canonical frontend schemas/components
- `apps/web/lib/api.ts` only as needed
- Frontend tests

Tests:

- Auth redirect
- Real chat response rendering
- Permission execution and backend-derived expiry metadata
- Empty/error/rate-limit states
- No mock data in production path
- `npm run build`

Do-not-touch:

- New backend chat endpoint
- New permission-token system
- Parallel action schema
- Browser apply

Dependency: PR 2 plus policy/audit foundation; should not lose Preview labeling until canonical live behavior is complete.
Risk level: medium.

### Later PRs

Company research, outreach drafts, operational memory read models, and browser-assisted apply must each remain separate PRs. Browser automation should be last because it combines external side effects, third-party UI fragility, user-session security, and high audit requirements.

## 10. Final Recommendation

### 1. What should we do next

Open `feat/action-audit-schema-hardening`. The permission guardrail work in #700/#705 is already complete; this PR must address only the remaining audit-schema gap: extend the existing `action_audit_log`, enforce append-only behavior in PostgreSQL, and remove request-time audit-table alteration.

### 2. What should we not do next

- Do not merge or revive PR #685 as a foundation; it is superseded/duplicate-risk.
- Do not add both `agent_audit_events` and `agent_audit_log`.
- Do not add a new HMAC approval token while the server-side pending permission ID is canonical.
- Do not wire `/ask` to a new backend endpoint or local action schema.
- Do not create a new queue, application tracker, FitScorer, CV builder, or cover-letter writer before consolidating existing code.
- Do not begin browser-assisted apply.

### 3. Existing files to extend

- `src/repositories/audit_repo.py`
- `migrations/006_action_audit_log.sql` through a new additive migration
- `src/services/pending_permissions.py`
- `src/services/permission_factory.py`
- `src/agent/runtime.py`
- `src/agent/registry/tool_registry.py`
- `src/schemas/actions.py`
- `src/schemas/chat.py`
- `src/services/agentic_ui_composer.py`
- `src/resume_screener.py`
- `src/services/job_match_explanation.py`
- `src/services/document_resolver.py`
- `src/cover_letter_writer.py`
- `src/rico_apply_ai.py`
- `src/api/routers/apply_queue.py`
- `apps/web/app/queue/page.tsx`
- Existing Rico frontend Agentic components and mirrored Zod schemas

### 4. New files that should not be created because they duplicate existing systems

- A second approval token service equivalent to `approval_token.py` unless stateless/cross-service tokens are explicitly chosen.
- A second audit table/writer alongside `action_audit_log`/`audit_repo.py`.
- A new generic `FitScorer` that ignores `resume_screener.py`, current rankers, and explainers.
- A second `ActionCard`/permission schema separate from `src/schemas/chat.py`.
- A new `/ask` backend orchestrator separate from Rico chat/runtime.
- A new application queue or application lifecycle repository.
- A new CV builder or cover-letter writer.
- A fourth agent runtime/coordinator.

### 5. First implementation PR

Branch: `feat/action-audit-schema-hardening`

Scope:

- One additive, numbered audit migration extending `action_audit_log`.
- Database-enforced insert-only history.
- Canonical event fields on `action_audit_log`.
- Repository writes without request-time DDL.
- Focused tests only.
- No changes to permission binding, permission consumption, expiry duration, or `_approved` handling already completed by #700/#705.

### 6. Exact acceptance criteria

The first implementation PR is acceptable only when:

1. It uses the existing `action_audit_log`; no parallel agent audit table is introduced.
2. Existing action audit rows remain readable and valid.
3. New event rows support at least `event_type`, `correlation_id`, `permission_id`, `policy_decision`, `risk_class`, and JSON metadata.
4. PostgreSQL rejects `UPDATE` and `DELETE` against the audit table through an explicit trigger or equivalent database control.
5. Repository code performs INSERT-only event writes.
6. `audit_repo.py` no longer executes `ALTER TABLE action_audit_log` during a request.
7. Existing action/idempotency behavior remains unchanged.
8. Permission issuance/validation format remains unchanged.
9. Focused audit tests pass without external AI, Stripe, Telegram, JotForm, Gmail, JSearch, or production database calls.
10. The PR contains no frontend, chat-routing, apply-engine, billing, or `/ask` changes.
11. The migration is additive and has a documented rollback that removes only newly added trigger/index/nullable columns if rollback is required.
12. No migration is run against production without separate explicit approval.
13. It does not duplicate or import the audit/token architecture from superseded PR #685.
14. It creates no `agent_approval_tokens`, duplicate HMAC approval service, duplicate `audit_writer.py`, parallel `policy_gate.py`, or `agent_audit_events`.
15. A separate `agent_audit_events` design may be reconsidered only in a later decision after reviewing and documenting why the extended `action_audit_log` cannot satisfy the operational-event requirements.

This sequence builds from Rico's actual code, removes the highest-risk ambiguity, and preserves current production behavior while creating a clean base for policy decisions, FitScorer, verified tailoring, and live `/ask`.
