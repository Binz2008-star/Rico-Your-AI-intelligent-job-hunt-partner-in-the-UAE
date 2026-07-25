# Architecture V2 — Full System Rebuild Blueprint

> **Status: PROPOSAL. Nothing here is approved, nothing here is implemented.**
> Owner decision required before any code moves (see §11).
> This document does **not** change production behavior, routes, or the design system.

- Date: 2026-07-25
- Author: Claude (session `claude/website-api-restructure-5gtkpg`)
- Trigger: owner request — rebuild the site structure, restructure the route/API layer,
  and make the AI actually intelligent ("عيد تصميم النظام كامل، عيد معماريته").
- Relates to: `DEC-20260707-001` (phased maturation roadmap), `DEC-20260723-001`
  (trust-first: no new features until execution reliability is fixed),
  `DEC-20260716-001` (Atelier V3 is the sole design system),
  `AGENTS.md` → Landing Page Production Freeze.

---

## 0. ملخص تنفيذي بالعربية

المشكلة ليست في التصميم ولا في عدد الصفحات. المشكلة معمارية، وقِسناها بالأرقام:

1. **"الذكاء الاصطناعي" في ريكو ليس ذكاءً اصطناعياً بالدرجة الأولى.** الطبقة
   المحادثية كلها موجودة في صنف واحد `RicoChatAPI` بطول ~21 ألف سطر، فيه
   **313 دالة، و1691 تفرّع شرطي (if/elif)، و259 نمط regex** — مقابل
   **موضعين اثنين فقط** يُستدعى فيهما النموذج اللغوي فعلياً. أي أن ريكو محرك
   قواعد يدوي يرتدي ثوب الذكاء الاصطناعي. كل سلوك جديد = فرع `if` جديد، وكل
   صيغة عربية غير متوقعة = فشل صامت. هذا هو السبب الجذري لأغلب أعطال المحادثة.
2. **مسارات الـ API غير مُهيكلة.** 123 مساراً موزّعة على 24 راوتر، وراوتر واحد
   (`rico_chat.py`) يحمل 25 مساراً لستة سياقات مختلفة: المحادثة + الملف الشخصي +
   البحوث المحفوظة + رفع السيرة + ثلاثة webhooks + الصحة + المقاييس. وهناك
   **أربع طرق مختلفة** للتقدّم على وظيفة واحدة.
3. **انعكاس في اتجاه الاعتماديات.** 12 ملفاً في `src/services/` يستوردون
   `rico_chat_api` — أي أن طبقة الخدمات تعتمد على المتحكّم، لا العكس. هذا
   بالضبط ما يجعل الملف العملاق غير قابل للتفكيك.
4. **مكدّسان متوازيان للوكيل.** المكدّس القديم (`rico_chat_api.py`) والمكدّس
   الحديث (`src/agent/*` مع `tool_registry` و`runtime`) لا يلتقيان أبداً.

**التوصية:** لا إعادة كتابة من الصفر (greenfield) — الخطر عالٍ جداً على منتج حيّ.
بل **إعادة بناء تدريجي بنمط Strangler**: نبني نواة جديدة (حلقة وكيل حقيقية
بالأدوات + عقد API v2) بجانب القديم، ونحوّل السلوك مساراً بعد مسار، مع بقاء
الإنتاج حياً في كل خطوة. التفاصيل في §10، والقرار المطلوب منك في §11.

---

## 1. What this document is

A complete target architecture for Rico plus a migration path to reach it:

- §3 measured audit of what exists today (numbers, not opinions)
- §4 the structural defects, stated as root causes
- §5 target architecture and the dependency rule
- §6 **AI layer redesign** — rule engine → tool-calling agent loop
- §7 **API v2 contract** — full resource-oriented route table with old→new mapping
- §8 frontend restructure
- §9 data layer posture
- §10 migration strategy (two options, one recommendation)
- §11 the decision required from the owner

It is deliberately **not** a code change. A rewrite of a live product with 1,386
merged PRs starts with an agreed target or it becomes a second parallel
implementation — which `CLAUDE.md` explicitly forbids.

---

## 2. Constraints that survive the rebuild

These are non-negotiable and every phase below must preserve them:

| Constraint | Source |
| --- | --- |
| JWT-in-httpOnly-cookie auth; identity never from request body | `CLAUDE.md` → Auth Rules |
| Email verification required before login; signup forces `role="user"` | `CLAUDE.md` → Auth Rules |
| `rico_safety.py` guardrails cannot be bypassed by any new route | `CLAUDE.md` → Safety Layer Rules |
| `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS=true` gate on every apply path | `CLAUDE.md` → Safety Layer Rules |
| Telegram user-channel vs admin-channel separation | `src/CLAUDE.md` |
| Atelier V3 is the only design system | `DEC-20260716-001` |
| Landing page component swap needs explicit owner approval | `AGENTS.md` |
| Global, user-agnostic fixes only — no special-casing one account | `CLAUDE.md` → Product Generalization Rule |
| Trust before features: no new capability while execution reliability is broken | `DEC-20260723-001` |

The rebuild is **in service of** `DEC-20260723-001`, not an exception to it: the
monolith is the reason trust defects keep recurring in the same file.

---

## 3. Measured audit (2026-07-25, `main` @ `e26548b`)

### 3.1 Backend mass

| Metric | Value |
| --- | --- |
| Python files under `src/` | 266 |
| Python lines under `src/` | 99,483 |
| `src/rico_chat_api.py` | **23,081 lines** |
| `class RicoChatAPI` | lines **2156 → 23060** (~21,000 lines, one class) |
| Methods on that class | **313** |
| `if` / `elif` branches in the file | **1,691** |
| `re.search` / `match` / `compile` / `fullmatch` calls | **259** |
| Sites that actually call the LLM | **2** (`rico_chat_api.py:4745`, `:8064`) |
| Modules importing `rico_chat_api` | **19** (of which **12 are in `src/services/`**) |

### 3.2 API surface

| Metric | Value |
| --- | --- |
| Routers registered in `src/api/app.py` | 24 |
| Route handlers | 123 |
| Largest router `routers/rico_chat.py` | 2,962 lines / 25 endpoints |
| Prefixes owned by two different files | `/api/v1/billing` (`paddle_billing.py` + `billing_whatsapp.py`) |
| Distinct ways to act on a single job | **4** (`/jobs/{id}/apply`, `/actions/run`, `/jobs/lifecycle`, `/apply/prepare`) |
| Distinct chat entry points | **4** (`/rico/chat`, `/rico/chat/public`, `/rico/chat/stream`, `/agent/chat`) |
| Distinct action dispatchers | **2** (`/actions/run`, `/rico/actions/execute`) |

### 3.3 Frontend mass

| Metric | Value |
| --- | --- |
| TS/TSX files under `apps/web` (excl. node_modules) | 362 |
| TSX lines | 50,770 |
| `app/command/page.tsx` | **2,972 lines** (single page component) |
| `lib/api.ts` | **2,565 lines** (single API client module) |
| Landing page components present | **4** (`LandingPage`, `LandingPageV2`, `LandingPageV3`, `LandingPageNocturne`); live one is `LandingPageV2` (`app/page.tsx:51`) |
| Non-product route dirs shipped in `app/` | `_atelier`, `design-gallery`, `design-preview`, `rico-preview`, `sandbox`, `vision`, `archive` |

### 3.4 Duplicated legacy modules

`src/dashboard.py` (998) + `dashboard_v2.py` (688) + `dashboard_refactored.py`
(674) + `dashboard_ai.py` (473) + `dashboard_decision.py` (548) = **3,381 lines**
of four-generations-deep duplication in one concern.

---

## 4. Root-cause defects

**D1 — The intelligence is a rule engine.**
1,691 branches and 259 regexes decide what Rico says; the model is consulted at 2
sites. Consequences, all observed in the PR history: unrecognized Arabic phrasing
falls through to a template; every new phrasing needs a code change and a deploy;
identical logic is re-implemented per intent; the "typed-YES confirmation loop"
class of bug recurred **four separate times** because there is no single place
where a pending confirmation is resolved.

**D2 — Dependency inversion around the god-module.**
`src/services/*` (12 files) import `rico_chat_api`. The controller is below the
service layer in the import graph. Nothing can be extracted without a cycle,
which is why the file only grows.

**D3 — Two agent stacks that never meet.**
`src/agent/` has the right shape already — `tool_registry.py` (declarative tools),
`runtime.py` (idempotent dispatch + audit), `orchestrator.py`, `intelligence/`
(intent classifier, scorer, role classifier), `responses/schema.py`. But it is
reached only via `/api/v1/actions/run` and `/api/v1/agent/chat`. The **primary**
user path (`/api/v1/rico/chat`) goes to the monolith and re-implements the same
concerns by hand.

**D4 — Routers are not bounded contexts.**
`rico_chat.py` owns chat, profile, saved searches, scheduled searches, CV upload,
three inbound webhooks, health, and metrics. Webhooks are an ingress boundary with
a different trust model than an authenticated chat call, and they share a file
with it.

**D5 — Four competing write paths per job action.**
`/jobs/{id}/apply`, `/actions/run`, `/jobs/lifecycle`, `/apply/prepare`. Each must
independently honor the approval gate and idempotency. That is a safety surface,
not just untidiness.

**D6 — God-files on the frontend too.**
A 2,972-line page component and a 2,565-line API client are single points of
merge conflict and the reason UI work is slow and risky.

**D7 — Dead and preview surfaces ship to production.**
Seven non-product route directories plus three unused landing components live in
the deployed app, contradicting the No Dead UI Rule (`DEC-20260628-001`).

---

## 5. Target architecture

### 5.1 The dependency rule

One rule fixes D2 permanently and everything below follows from it:

```text
transport  →  application  →  domain  →  infrastructure
(routers)     (use cases)     (rules)    (db, providers, llm, telegram)
```

Imports point **inward only**. A module in `domain/` may not import from
`application/` or `transport/`; a module in `application/` may not import a
router. `src/services/*` importing `rico_chat_api` becomes a lint-enforced error.

### 5.2 Backend module map

```text
src/
  transport/            # FastAPI only: routing, serialization, auth deps, rate limits
    http/v2/            # API v2 routers (§7)
    webhooks/           # telegram, jotform, github, paddle — separate trust boundary
    ops/                # /health, /version, /metrics — no feature router owns these
  application/          # use cases, one file per user-visible capability
    chat/               # the agent loop (§6)
    jobs/  applications/  profile/  cv/  billing/  notifications/
  domain/               # pure rules, zero I/O, fully unit-testable
    matching/  scoring/  eligibility/  safety/  approval/  identity/
  infrastructure/
    db/          # repositories (already exists as src/repositories — moves here)
    llm/         # provider routing: deepseek → hf → keyword fallback
    providers/   # jsearch, gmail, telegram, paddle, jotform
    queue/       # background work (Phase D of DEC-20260707-001)
  workers/       # scheduled + queued jobs, no HTTP
```

`src/agent/` is **not** deleted — it is promoted: `registry/`, `runtime.py`, and
`intelligence/` become the core of `application/chat/`.

### 5.3 What happens to `rico_chat_api.py`

It is decomposed, not rewritten in place. Its 313 methods sort into four buckets:

| Bucket | Destination | Rough share |
| --- | --- | --- |
| Real domain rules (city validation, eligibility, matching, CV-state) | `domain/` | ~20% |
| Orchestration of a capability (search, apply, track, profile update) | `application/` as tools (§6) | ~25% |
| Response text assembly | `application/chat/presenter.py` + response schema | ~15% |
| Regex intent-matching that the model should be doing | **deleted**, replaced by §6 | ~40% |

That last row is the point of the whole exercise: ~40% of the largest file in the
repository exists to do badly what a tool-calling model does well.

---

## 6. AI layer redesign — the core of the request

### 6.1 Today

```text
message → 1,691 hand-written branches → regex matches → canned template
                                     ↘ (2 sites) → LLM → text
```

### 6.2 Target — a real agent loop

```text
message
  → context assembly (profile, active CV, journey state, recent turns, entitlements)
  → LLM with TOOL DEFINITIONS (the model chooses; no regex intent tree)
  → tool call(s) → agent/runtime.py (idempotency + audit + approval gate)
  → tool results returned to the model
  → structured response object (not a string) → typed UI blocks
```

Concretely:

1. **Tools replace intents.** Every capability currently expressed as a branch
   becomes a declarative tool in `tool_registry` with a JSON schema:
   `search_jobs`, `explain_match`, `save_job`, `prepare_application`,
   `track_application`, `update_profile`, `read_cv`, `schedule_search`,
   `list_applications`, `set_preferences`. The registry already exists
   (`src/agent/registry/tool_registry.py`) and is already wired to `runtime.py`
   — the work is defining the tools and letting the model call them, not building
   new infrastructure.
2. **The safety gate stays server-side and below the model.** The model may
   *request* `prepare_application`; only `agent/runtime.py` decides whether
   `RICO_REQUIRE_APPROVAL_FOR_APPLICATIONS` permits it. A model that hallucinates
   an apply cannot cause one. This is strictly safer than today, where the
   approval check is duplicated across four write paths (D5).
3. **Language handling stops being a token bank.** Arabic/English intent
   detection moves from keyword lists to the model, killing the entire class of
   "unrecognized Arabic phrasing" defects. Deterministic *validation* (e.g. city
   rejection in `city_validation.py`) stays deterministic — validation is domain
   logic; comprehension is not.
4. **Grounding and anti-fabrication become structural.** Job facts may only enter
   a reply through a tool result carrying a provenance id. The presenter refuses
   to render a job card without one. "No invented jobs" moves from a prompt
   instruction to a type constraint — directly serving `DEC-20260723-001`.
5. **Responses are objects.** `agent/responses/schema.py` becomes the only chat
   output type: `{ blocks[], actions[], provenance[], confirmations[] }`. The
   frontend renders blocks instead of parsing prose.
6. **One confirmation resolver.** A single `pending_confirmation` state machine in
   `application/chat/` — the four-times-recurring typed-YES bug becomes
   structurally impossible rather than patched a fifth time.
7. **Fallback chain preserved.** `deepseek → huggingface → keyword` stays, but the
   keyword tier degrades to *"I could not understand, here is what I can do"* —
   an honest failure, never a confident wrong answer.

### 6.3 Cost note

A tool-calling loop uses more tokens per turn than a regex match. Mitigations to
size before Phase 3: cache the system/tool preamble, keep tool schemas terse,
cap loop iterations (2–3), and keep cheap deterministic short-circuits for
trivial turns (greetings, acknowledgements). This must be measured on real
transcripts before rollout — see the Phase 3 exit criteria in §10.

---

## 7. API v2 contract

Principles: resource-oriented, one owner per resource, verbs only where a real
command exists, webhooks and ops outside the product namespace, `/api/v1` kept
alive and unchanged until the frontend has fully moved.

### 7.1 Target route table

| Domain | v2 route | Replaces (v1) |
| --- | --- | --- |
| Identity | `POST /api/v2/auth/{register,login,logout,password/forgot,password/reset}` | `/api/v1/auth/*` |
| | `GET /api/v2/me` | `/api/v1/me` |
| Profile | `GET|PATCH /api/v2/profile` | `/api/v1/rico/profile` (GET+PATCH) |
| | `GET /api/v2/profile/completion` | derived inline today |
| CV / documents | `GET|POST|DELETE /api/v2/documents` | `/api/v1/user/files*`, `/api/v1/rico/upload-cv` |
| | `POST /api/v2/documents/{id}/activate` | `/api/v1/user/files/{id}/set-primary` |
| | `POST /api/v2/documents/{id}/confirm-profile` | `/api/v1/rico/confirm-cv-profile` |
| | `GET /api/v2/documents/quota` | `/api/v1/user/files/quota` |
| Chat | `POST /api/v2/chat` (auth) · `POST /api/v2/chat/public` | `/api/v1/rico/chat`, `/chat/public`, `/agent/chat` |
| | `POST /api/v2/chat/stream` (+`/public`) | `/api/v1/rico/chat/stream*` |
| | `GET /api/v2/chat/sessions` · `GET|DELETE /api/v2/chat/messages` | `/rico/chat/sessions`, `/rico/chat/history` |
| | `POST /api/v2/chat/feedback` | `/api/v1/rico/feedback` |
| Jobs | `GET /api/v2/jobs` · `GET /api/v2/jobs/{id}` | unchanged semantics |
| | `GET /api/v2/jobs/{id}/match` | `/api/v1/rico/...` (in-monolith "why") |
| Job actions | `POST /api/v2/jobs/{id}/actions` `{action, idempotency_key}` | **collapses all 4 paths (D5)**: `/jobs/{id}/{apply,skip,save,block}`, `/actions/run`, `/jobs/lifecycle`, `/rico/actions/execute` |
| Applications | `GET|POST /api/v2/applications` · `PATCH /api/v2/applications/{id}` | `/api/v1/applications*` |
| | `GET /api/v2/applications/stats` · `GET /api/v2/applications/follow-ups` | `/applications/stats`, `/apply/follow-ups`, `/jobs/lifecycle/follow-ups` |
| Apply queue | `GET /api/v2/applications/drafts` · `POST /api/v2/applications/drafts/{id}/{approve,reject}` | `/api/v1/apply/*` |
| Searches | `GET|POST|DELETE /api/v2/searches/saved` | `/rico/settings/saved-searches` |
| | `GET|PATCH /api/v2/searches/scheduled` | `/rico/scheduled-searches` |
| Settings | `GET|PUT /api/v2/settings` | `/api/v1/settings` |
| | `POST /api/v2/settings/channels/{telegram,email}/{opt-in,opt-out}` · `GET .../status` | `/settings/{telegram,email}/*` |
| Onboarding | `POST /api/v2/onboarding/submit` · `GET /api/v2/onboarding/status` | unchanged semantics |
| Journey | `GET /api/v2/journey/today` · `GET /api/v2/mission/current` | unchanged semantics |
| Stats | `GET /api/v2/stats` | `/api/v1/stats` |
| Billing | `GET /api/v2/billing/config` · `GET /api/v2/billing/status` · `POST /api/v2/billing/checkout` · `POST /api/v2/billing/portal` | `paddle_billing.py` |
| | `GET /api/v2/billing/whatsapp/config` · `POST /api/v2/billing/whatsapp/request` | `billing_whatsapp.py` — **same prefix, now one owner** |
| Subscription | `GET /api/v2/subscription/{plans,me}` · `POST /api/v2/subscription/intent` | unchanged semantics |
| Integrations | `/api/v2/integrations/gmail/*` | unchanged semantics |
| Admin | `/api/v2/admin/{ops,subscribers,subscriptions}/*` | unchanged semantics |
| **Webhooks** | `POST /webhooks/{telegram,jotform,github,paddle}` | **out of `/api/v1/rico/*` and `/api/v1/billing/*`** (D4) |
| **Ops** | `GET /health` · `GET /version` · `GET /ops/metrics` · `GET /ops/ai-provider` | `/rico/metrics`, `/rico/health/ai-provider`, `/rico/admin/health/ai-provider` |
| **Internal cron** | `POST /internal/pipeline/*` (guarded by `RICO_CRON_SECRET`) | `/api/v1/pipeline/*` |

Net effect: 123 endpoints across 24 routers → ~95 endpoints across ~14 bounded
routers, with the four job-write paths collapsed to one audited entry point.

### 7.2 Cross-cutting contract

- **Envelope:** every response `{ data, error, meta }`; every error
  `{ code, message, error_ref }` with `error_ref` already generated by
  `generate_error_ref()`.
- **Idempotency:** `Idempotency-Key` header on every mutating route, honored by
  `agent/runtime.py`'s existing scheme.
- **Pagination:** cursor-based on every list route.
- **Deprecation:** v1 responses gain `Deprecation` + `Sunset` headers when the v2
  twin ships; v1 is removed only after the frontend reports zero v1 calls.

---

## 8. Frontend restructure

### 8.1 Route map

Product routes stay exactly as they are — **no user-visible URL changes, no
landing-page swap** (freeze respected). What changes is what ships:

| Action | Routes |
| --- | --- |
| Keep | `/`, `/command`, `/login`, `/signup`, `/verify-email`, `/forgot-password`, `/reset-password`, `/onboarding`, `/dashboard`, `/jobs`, `/applications`, `/profile`, `/settings`, `/subscription`, `/queue`, `/saved-searches`, `/upload`, `/admin`, marketing + legal |
| Move behind a dev-only guard, or delete | `_atelier`, `design-gallery`, `design-preview`, `rico-preview`, `sandbox`, `vision`, `archive`, `signals`, `flow` — pending a per-route product decision (D7) |
| Delete after confirming unused | `LandingPage.tsx`, `LandingPageV3.tsx`, `LandingPageNocturne.tsx` (live component is `LandingPageV2`) |

### 8.2 Breaking the god-files

```text
apps/web/
  app/                      # routing + layout only, thin pages
  features/                 # NEW — one folder per capability
    chat/       components/ hooks/ state/ types.ts
    jobs/  applications/  profile/  documents/  settings/  billing/
  lib/api/                  # api.ts (2,565 lines) split per domain
    client.ts               # fetch wrapper, envelope handling, error refs
    chat.ts jobs.ts applications.ts profile.ts documents.ts settings.ts billing.ts
  components/ui/            # Atelier V3 primitives — unchanged system
```

`app/command/page.tsx` (2,972 lines) becomes a thin route that composes
`features/chat`. Chat rendering switches from parsing prose to rendering the
typed blocks from §6.5 — that is what makes the AI *feel* different to the user,
not new CSS.

---

## 9. Data layer

- Neon stays the single source of truth. No schema rewrite in this program.
- Migrations continue as numbered SQL files via the existing drift tooling
  (`scripts/check_migration_drift.py` / `apply_migration_drift.py`). **No direct
  mutation of live Neon, ever.**
- V2 routes read and write the *same* tables as v1 during migration. There is no
  dual-write, no shadow schema — that is what keeps rollback trivial.
- Repository layer (`src/repositories/`) moves under `infrastructure/db/`
  unchanged in behavior.

---

## 10. Migration strategy

### Option A — Greenfield rewrite (build V2 as a new app, cut over)

Honest assessment: **not recommended.** 99k backend lines + 51k frontend lines
encode years of production-hardened edge cases (fail-closed billing quotas,
per-user `auth_version` JWT invalidation, scanner-safe email verification, city
write-boundary rules). A rewrite re-learns those by re-suffering them in front of
live users, and it violates `CLAUDE.md`'s ban on parallel implementations for
however many months it runs.

### Option B — Strangler rebuild in place *(recommended)*

Same target architecture, reached without ever taking production down. Each phase
is independently shippable, independently revertible, and green on CI before the
next begins.

| Phase | Work | Exit criteria |
| --- | --- | --- |
| **0. Guardrails** | Import-direction lint rule (§5.1); characterization tests capturing today's chat behavior on real transcripts; baseline token/latency measurement | Lint fails on a bad import; a transcript suite exists that must stay green through every later phase |
| **1. Boundaries, no logic change** | Split `routers/rico_chat.py` by context; move webhooks to `transport/webhooks/`, ops to `transport/ops/`; merge the two `/billing` files | All 123 v1 routes byte-identical in behavior; test suite green |
| **2. Break the inversion (D2)** | Extract pure rules out of `RicoChatAPI` into `domain/`; flip the 12 `services/ → rico_chat_api` imports | Zero `src/services/*` imports of `rico_chat_api`; monolith shrinks measurably |
| **3. Agent loop (D1, D3)** | Define tools in `tool_registry`; build the loop in `application/chat/`; single confirmation resolver; typed responses. Ship behind `RICO_AGENT_LOOP_ENABLED`, default **off**, rolled out to a synthetic cohort first | Transcript suite green through the new loop; measured cost/latency within an agreed envelope; approval gate proven on every apply path |
| **4. Delete the regex tree** | Remove the ~40% of `rico_chat_api.py` the loop replaced; delete the duplicate `dashboard_*.py` generation | `rico_chat_api.py` under ~4k lines; one dashboard module |
| **5. API v2** | Ship `/api/v2` as a thin transport over the now-clean application layer; v1 delegates to the same use cases; deprecation headers | Both versions serve identical data; contract tests per route |
| **6. Frontend features split** | `features/` structure; `lib/api/` split; typed-block chat rendering; retire dead routes/components | `command/page.tsx` under ~300 lines; `npm run build` + `npm run test` green |
| **7. Cut v1** | Remove v1 once telemetry shows zero calls | v1 routers deleted |

Phases 1–2 are pure refactors and can start immediately under `DEC-20260723-001`
— they *are* reliability work. Phase 3 is the one that needs an explicit owner
go-ahead on cost (§6.3). Phases 5–6 are the user-visible payoff.

This program subsumes rather than replaces `DEC-20260707-001`: its Phase 3
("API/client consolidation") is §7 here, its Phase 7 ("UI redesign") is §8, and
its worker/queue split lands in `src/workers/` per §5.2. The AI-layer rewrite
(§6) is genuinely new — the existing roadmap never addressed it.

---

## 11. Decision required from the owner

1. **Approach:** Option B (strangler, recommended) or Option A (greenfield)?
2. **Start scope:** approve Phase 0–1 (guardrails + boundary split, zero behavior
   change, safe under the current trust-first freeze) as the first PR?
3. **Phase 3 cost envelope:** the agent loop increases per-turn token cost. What
   is the acceptable ceiling per chat turn before it ships?
4. **Dead surfaces:** delete the 7 preview/sandbox route dirs and the 3 unused
   landing components, or keep them behind a dev guard?

No implementation proceeds until 1 and 2 are answered.

---

## 12. Risks

| Risk | Mitigation |
| --- | --- |
| Refactor silently changes chat behavior | Phase 0 characterization tests on real transcripts gate every later phase |
| Agent loop costs more per turn | Flagged off by default; preamble caching; iteration cap; measured before rollout (§6.3) |
| Model requests an unapproved apply | Approval gate lives in `runtime.py`, below the model — strictly safer than today's 4 duplicated checks |
| Long-running program collides with other agents | One writer per branch (`AGENTS.md`); each phase is one PR; `PROJECT_STATUS.md` updated per phase |
| v2 diverges from v1 mid-migration | v1 and v2 share one application layer and one schema; no dual-write |
| Scope creep into a redesign | Design system frozen (Atelier V3); landing page frozen; no user-visible URL changes |
