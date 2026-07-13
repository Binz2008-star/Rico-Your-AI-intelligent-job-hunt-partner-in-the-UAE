# Rico Launch Execution Plan

## Owner outcome

Ship the approved new interface across the real product, offer one paid plan at AED 79/month, invite users by email, and open Rico to users only after the launch-critical product path is verified end to end.

## Non-negotiable sequence

```text
Control-plane reconciliation
  -> open-PR cleanup and ownership map
  -> route/design parity inventory
  -> launch-critical UI completion
  -> AED 79 billing implementation
  -> invitation workflow
  -> launch smoke and rollback readiness
  -> owner approval to open access
```

Do not combine these stages in one PR. Billing, auth, email, database, and design changes require separate reviewable increments.

## Phase 0 — Control plane and PR reconciliation

### Objective

Make repository coordination reflect live GitHub state before additional implementation begins.

### Deliverables

- Current `main` SHA fetched and reported at every session start.
- Every relevant open PR classified as `ACTIVE`, `REVIEW`, `HOLD`, `STALE/CLOSE`, or `REFERENCE`.
- One active runtime objective recorded after the control-plane PR is merged.
- Each active branch has one owner and one authority role.
- Stale branches are explicitly prohibited from resumption.
- Daily Autopilot is mandatory after the canonical `OPERATING_RULES.md` boot sequence.
- Every active PR has a current TASKS Continuity Block and dated handoff when incomplete.

### Exit gate

No unknown writer, no competing branch, no missing Continuity Block, and no stale control document claiming an obsolete execution lock.

## Phase 1 — Route and design parity inventory

### Objective

Determine the real state of every user-facing route against the approved Lovable/Atelier reference and the current production behavior.

### Required route matrix

| Surface | Route examples | Required classification |
| --- | --- | --- |
| Public launch | `/`, `/explainer`, `/pricing` | complete / partial / legacy / gated |
| Authentication | `/signup`, `/login`, `/verify-email`, password reset | complete / partial / legacy |
| Onboarding | `/onboarding` | visual parity + real persistence |
| Workspace | `/dashboard`, `/command`, `/profile`, `/settings` | complete / partial / legacy |
| Career workflow | `/applications`, `/upload`/My Files, `/flow`, `/queue` | complete / partial / legacy |
| Legal/support | `/privacy`, `/terms`, `/refund-policy` | production-ready / legal-review blocker |

For each route record:

- current component and shell;
- EN/AR and RTL status;
- mobile status;
- auth guard status;
- real data/actions bound;
- loading, empty, error, and forbidden states;
- reference screenshot/component note;
- launch blocker status;
- owning PR or new proposed PR.

### Exit gate

The owner can see exactly what is already complete, what remains, and which small PR closes each gap.

## Phase 2 — Launch-critical interface completion

Use small route-group PRs. Recommended sequence:

1. Auth and account entry surfaces.
2. Onboarding parity and first-run continuity.
3. Workspace remaining read/action routes.
4. Command/chat design and truthful action affordances.
5. Public launch, pricing, navigation, footer, and legal presentation.
6. Cross-route visual QA, RTL, mobile, accessibility, and regression pass.

### Global acceptance criteria

- Approved design composition is reproduced, not merely recolored.
- Existing production behavior and API contracts are preserved unless a separate backend PR explicitly changes them.
- No prototype claims a save, apply, payment, setting mutation, or upload succeeded unless the backend confirms it.
- Guest/private route boundaries are correct.
- EN and AR are first-class.
- Mobile widths have no horizontal overflow.
- Focus, keyboard, contrast, loading, empty, and error states are usable.
- `npm run build` and focused route tests pass.

## Phase 3 — One paid plan: AED 79/month

### Product contract

```text
Plan name: Rico Monthly
Price: AED 79 per month
Paid plans exposed to users: one
Billing authority: verified provider webhook, never frontend success state
```

### Entry gate

Before billing implementation resumes:

- deep-review PR #1008 together with subscription-gating follow-up #989;
- identify every changed file, migration/config dependency, and external contract;
- confirm whether #1008 is salvageable or must be superseded by smaller PRs;
- record a dedicated billing task and Continuity Block;
- keep production provider mutation forbidden without explicit owner approval.

### Required implementation

- Provider product/price IDs configured through environment, never committed as secrets.
- Checkout initiated for the authenticated account.
- Signed webhook verification.
- Provider customer and subscription IDs mapped to Rico's canonical user/account identity.
- Idempotent activation and renewal handling.
- Cancellation and end-of-period behavior.
- Failed-payment and grace-state behavior.
- Customer portal or subscription-management path.
- Server-side plan gating.
- Synthetic tests for cross-user isolation, replayed webhooks, duplicate events, cancellation, and failure.
- Pricing UI bound to the real checkout path.

### Forbidden shortcuts

- No activation from query parameters or checkout return URL alone.
- No hard-coded paid entitlement.
- No owner-account special case.
- No live provider mutation or production purchase without explicit owner approval.

### Exit gate

A synthetic account can complete the full lifecycle in the provider's test environment, and Rico's entitlement state follows verified webhook events correctly.

## Phase 4 — User invitation email workflow

### Objective

Allow the owner/system to invite users through branded, secure, trackable email invitations.

### Required behavior

- Create a single-use, expiring invitation token.
- Bind invitation to intended email and lifecycle state.
- Send branded EN/AR mail through the canonical mailer.
- Invitation link reaches account claim/signup without losing the token.
- Consumed, expired, revoked, and resent states are handled safely.
- Repeated delivery is idempotent.
- Delivery failures are visible to the owner/admin workflow.
- No secrets or raw tokens are logged.

### Exit gate

A synthetic invited user receives the email, claims the invitation, verifies the account, completes onboarding, and reaches the correct workspace state.

## Phase 5 — Launch gate

The site must remain gated until all launch blockers pass.

### Required smoke path

1. Public entry loads on desktop and mobile.
2. Signup and email verification succeed.
3. Login, logout, password reset, and validated return path succeed.
4. Onboarding and CV upload/confirmation persist correctly.
5. My Files and profile survive logout/login.
6. Rico reads only real user state and does not invent documents or actions.
7. Job discovery, save, application tracking, and follow-up surfaces work.
8. Pricing opens the real AED 79 checkout.
9. Verified billing event activates the correct account only.
10. Invitation flow succeeds.
11. Arabic/RTL critical path succeeds.
12. No cross-user data leakage.
13. Render `/health` and `/version`, Vercel/proxy health, CI, and migrations are verified.
14. Rollback switches and previous known-good deployment are documented.

### Launch decision

Only the owner authorizes removal of the teaser/waitlist/access gate and production billing activation.

## Agent allocation model

| Agent/session | Primary authority role | Allowed work |
| --- | --- | --- |
| UI account/session | WRITER | one route-group UI PR at a time |
| Backend/billing account/session | WRITER | billing or invitations, never overlapping UI files without agreement |
| Independent account/session | REVIEWER / RELEASE | diff review, CI, deployment and smoke evidence |
| Local Windsurf/OneSurf | verifier activity | focused local build/tests/screenshots; no foreign-branch edits |
| Codex | reviewer activity | correctness/regression signal only |
| Lovable | design reference | prototypes and handoff evidence; no backend/billing/auth mutation |

Every session must also state its activity pass from `OPERATING_RULES.md`.

## Definition of done

Rico is launch-ready only when:

- the control plane is current;
- the approved interface covers the complete launch-critical journey;
- the single AED 79 plan works through verified billing events;
- invitations work end to end;
- all launch smoke checks pass;
- known non-blocking issues are explicitly deferred with owners;
- rollback is ready;
- the owner approves opening access.
