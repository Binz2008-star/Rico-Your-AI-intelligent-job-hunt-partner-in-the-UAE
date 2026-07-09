# C2 Implementation Brief — `/privacy` + `/refund-policy`

**For:** whoever owns the production Rico repo.
**Not for:** the Lovable prototype (`lovable/design-preview-handoff` branch is out of scope for this work).

## 1. Scope

Two static routes, styled and structured to match the existing `/terms` route. No backend, no forms, no auth, no billing, no model/prompt work, no Command page changes, no landing animation, no design-system refactor.

- `GET /privacy` → 200
- `GET /refund-policy` → 200
- Footer/legal nav links updated if `/terms` is linked there today
- Build + typecheck pass
- No unrelated files changed

## 2. Pre-work (read-only inspection in the production repo)

1. Create branch from `main`: `feat/c2-privacy-refund`
2. Open the existing `/terms` route and note:
   - File location + routing convention (e.g. `app/terms/page.tsx`, `src/routes/terms.tsx`, `pages/terms.tsx`)
   - Head/meta pattern (title, description, og:*)
   - Layout wrapper (nav + footer components)
   - Typography classes / section structure / "last updated" placement
   - Any shared `<LegalPage>` or `<Prose>` component
3. Open the footer/nav component and note how `/terms` is linked, so `/privacy` and `/refund-policy` slot into the same list with the same styling.
4. Do **not** copy from the Lovable prototype. Mirror only the production `/terms` pattern.

## 3. Files to add / change

Exact paths depend on the production repo's convention — match `/terms`:

- **New:** privacy route file (mirror `/terms` file)
- **New:** refund-policy route file (mirror `/terms` file)
- **Edit (only if `/terms` is already linked there):** footer / legal nav component — add two links next to Terms
- **Optional:** if the repo has a shared legal-page layout component, reuse it; don't duplicate markup

No new dependencies. No new design tokens. No new shared components unless `/terms` already uses one.

## 4. Head / meta per page

Mirror the `/terms` head() shape exactly. Suggested strings:

**/privacy**
- title: `Privacy — Rico`
- description: `How Rico handles your data: what we collect, why, retention, and your rights.`
- og:title / twitter:title: same as title
- og:description / twitter:description: same as description
- No og:image unless `/terms` sets one

**/refund-policy**
- title: `Refund Policy — Rico`
- description: `When Rico issues refunds, eligibility, and how to request one.`
- og:* mirrors `/terms`

## 5. Content — draft with `TODO: legal review` markers

Every legal/business fact stays as a marker. Nothing invented.

Add a visible banner at the top of both pages:

> **Draft — pending legal review.** This page is a placeholder and is not a binding notice.

### 5.1 `/privacy` sections

1. **Who we are**
   Rico is operated by `TODO: legal review — legal entity name, jurisdiction, registered address`.
2. **What we collect**
   - Account data: name, email, authentication identifiers.
   - Profile content you provide: CV, preferences, notes.
   - Usage data needed to operate the product: pages loaded, features used, error diagnostics.
3. **What we do not collect**
   - We do not buy personal data from third parties.
   - We do not track you across unrelated sites.
   - We do not sell your personal data.
4. **Why we process it (purposes & legal bases)**
   - Provide and secure the service.
   - Match you with relevant opportunities.
   - Improve Rico using aggregated, non-identifying analytics.
   - Legal basis: `TODO: legal review — contract / legitimate interest / consent per jurisdiction`.
5. **Who sees it**
   - You and Rico's operating team.
   - Employers only when you send an application yourself.
   - Processors / subprocessors: `TODO: legal review — list of subprocessors (hosting, email, analytics, payments, AI providers)`.
6. **International transfers**
   `TODO: legal review — data residency + transfer mechanism (SCCs, adequacy, etc.)`.
7. **Retention**
   Personal data is kept while your account is active and deleted within `TODO: legal review — retention window` after account closure, except where law requires longer retention.
8. **Your rights**
   Access, correction, deletion, portability, objection, withdrawal of consent. Contact `TODO: legal review — privacy contact email`. We respond within `TODO: legal review — response SLA`.
9. **Security**
   Encryption in transit, access controls, least-privilege operations. No system is perfectly secure; report concerns to `TODO: legal review — security contact`.
10. **Cookies / local storage**
    We use strictly necessary storage to keep you signed in and remember preferences. Analytics/marketing cookies: `TODO: legal review — list or "none"`.
11. **Children**
    Not intended for users under 18.
12. **Changes**
    We will post updates here and update the "Last updated" date. Material changes will be notified `TODO: legal review — notification method`.
13. **Contact**
    `TODO: legal review — privacy contact email + postal address`.

Footer: `Last updated: TODO: legal review — date`.

### 5.2 `/refund-policy` sections

1. **Scope**
   Applies to paid Rico subscriptions purchased directly from Rico. Purchases via third-party stores follow that store's refund rules.
2. **Refund window**
   Refunds may be requested within `TODO: legal review — refund window (e.g. 14 days)` of the initial charge.
3. **Eligibility**
   - `TODO: legal review — eligibility rules (first-time purchase only? unused? consumed credits?)`
   - `TODO: legal review — statutory rights notice per jurisdiction (e.g. UAE consumer protection, EU right of withdrawal)`.
4. **Non-refundable items**
   `TODO: legal review — e.g. consumed AI credits, add-ons, custom services`.
5. **How to request a refund**
   Email `TODO: legal review — billing contact email` from the account's registered address with the order reference. We reply within `TODO: legal review — response SLA`.
6. **How refunds are issued**
   To the original payment method via `TODO: legal review — payment processor(s)`. Processing time depends on the processor and your bank.
7. **Cancellations**
   You can cancel anytime from account settings. Cancellation stops future renewals; it does not automatically trigger a refund for the current period unless the eligibility rules above apply.
8. **Chargebacks**
   Please contact us before initiating a chargeback so we can resolve the issue directly.
9. **Changes**
   We may update this policy; the version in force at time of purchase applies to that purchase.
10. **Contact**
    `TODO: legal review — billing contact email`.

Footer: `Last updated: TODO: legal review — date`.

## 6. Footer / nav wiring

Only touch the footer/nav if `/terms` is currently linked there. Add:

- `Privacy` → `/privacy`
- `Refund Policy` → `/refund-policy`

Match the existing link component, ordering convention, and i18n mechanism used for `Terms`. Do not restructure the footer.

## 7. Acceptance checklist

- [ ] Branch `feat/c2-privacy-refund` off `main`
- [ ] `/privacy` renders, returns 200, matches `/terms` visual pattern
- [ ] `/refund-policy` renders, returns 200, matches `/terms` visual pattern
- [ ] Draft banner visible on both pages
- [ ] All legal/business facts are `TODO: legal review` markers — nothing invented
- [ ] Footer/nav links added only if `/terms` is linked there today
- [ ] `pnpm build` (or repo equivalent) passes
- [ ] Typecheck passes
- [ ] No files changed outside: 2 new route files (+ optional footer/nav + optional shared layout reuse)
- [ ] No changes to: Command page, landing animations, AI gateway, auth, billing, model/prompt config, design tokens

## 8. Explicitly out of scope

- C3 landing hero animation
- C4 Command UI polish
- C8 streaming / Rico agent / persistence
- Any Lovable prototype code (do not import, copy, or reference)
- Backend, API routes, auth, billing, model, prompt, or context-window changes
- Design-system refactor, new tokens, new fonts
- SEO sitemap/robots changes beyond what `/terms` already does

## 9. PR description template

```
C2 — Add /privacy and /refund-policy (draft, pending legal review)

- New static routes mirroring /terms structure and styling
- All legal/business facts marked `TODO: legal review` — no invented content
- Visible draft banner on both pages
- Footer links added alongside Terms (if applicable)

Out of scope: C3, C4, C8, backend, auth, billing, model/prompt changes.
No Lovable prototype code used.

Follow-up required before publishing:
- Legal review pass to replace all TODO markers and remove draft banner
- Confirm subprocessor list with engineering
- Set "Last updated" date
```

## 10. Follow-up tickets to file (not part of this PR)

- **Legal-copy PR:** replaces every `TODO: legal review` marker with reviewed copy, removes the draft banner, sets the last-updated date. Owned by whoever runs legal review.
- **Analytics/subprocessor audit:** feeds the Cookies and Subprocessors sections. Coordinate with engineering before the legal-copy PR merges.
