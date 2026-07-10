# 2026-07-10 — `/design-preview` is the approved production target: repo-evidence inventory

**Purpose.** The owner clarified that the approved production direction is to reproduce the
full Rico `/design-preview` package — **shape + content + flows**, not "visual polish" and not
"landing below-the-fold only." This handoff records the **authoritative reference inventory
built from actual repo evidence** so future migration PRs copy the real package, not a
re-interpretation.

**On the uploaded PDF.** The owner referenced an uploaded design-preview PDF. **That PDF is
NOT present in this execution environment** (the only PDF on disk is an unrelated skills
sample, `/mnt/skills/examples/theme-factory/theme-showcase.pdf`). Per owner instruction, this
inventory is built from the in-repo `/design-preview` source, which **is** available and
authoritative. If the PDF contains screens beyond the 53 catalogued below, this inventory must
be extended before relying on it as complete.

## Authoritative sources (all in-repo / live)

1. Live approved reference: `https://ricohunt.com/design-preview`
2. Hub route + tile inventory: `apps/web/app/design-preview/_client.tsx` (435 lines), `page.tsx`
3. Reference image set: `apps/web/public/design-preview/*.png` — **53 PNGs** (catalogued below)
4. Live interactive previews already in the repo:
   - `/design-preview` — the hub (noindex, reference-only)
   - `/design-gallery` — `apps/web/app/design-gallery/{page,_client}.tsx` (+ `atelier/`)
   - `/rico-preview` — `apps/web/app/rico-preview/{page,_client}.tsx`

Do not rely on memory or assumptions about the upstream (Lovable) origin. The repo files above
are the source of truth.

## Reference PNG inventory (53 files, `apps/web/public/design-preview/`)

Naming: `{lang}-{screen}-{device}` or `{device}-{screen}-{lang}-light`. EN = English, AR = العربية.

- **Landing (5):** `desktop-home-en-light`, `desktop-home-ar-light`, `mobile-home-ar-light`
  (hub tile also references EN; `desktop-home-en-light` is the primary), plus the two AR/mobile.
- **Auth — sign in (4):** `en-auth-signin-desktop`, `en-auth-signin-mobile`,
  `ar-auth-signin-desktop`, `ar-auth-signin-mobile`
- **Auth — signup (2):** `en-auth-signup-desktop`, `en-auth-signup-mobile`
- **Auth — forgot (2):** `en-auth-forgot-desktop`, `en-auth-forgot-mobile`
- **Auth — verify + reset (4):** `en-auth-verify-desktop`, `en-auth-verify-mobile`,
  `en-auth-reset-desktop`, `en-auth-reset-mobile`
- **Onboarding (4):** `en-onboarding-desktop`, `en-onboarding-mobile`,
  `ar-onboarding-desktop`, `ar-onboarding-mobile`
- **Command / chat (4):** `en-command-desktop`, `en-command-mobile`,
  `ar-command-desktop`, `ar-command-mobile`
- **Dashboard / home (5):** `desktop-dashboard-en-light`, `desktop-dashboard-ar-light`,
  `mobile-dashboard-ar-light`, `en-app-index-desktop`, `en-app-index-mobile`
- **Profile (4):** `en-profile-desktop`, `en-profile-mobile`, `ar-profile-desktop`,
  `ar-profile-mobile`
- **Settings (4):** `en-settings-desktop`, `en-settings-mobile`, `ar-settings-desktop`,
  `ar-settings-mobile`
- **Applications / pipeline (4):** `en-applications-desktop`, `en-applications-mobile`,
  `ar-applications-desktop`, `ar-applications-mobile`
- **Upload CV (4):** `en-upload-desktop`, `en-upload-mobile`, `ar-upload-desktop`,
  `ar-upload-mobile`
- **Subscription / pricing (3):** `desktop-pricing-en-light`, `desktop-pricing-ar-light`,
  `mobile-pricing-ar-light`
- **Support / contact (2):** `desktop-support-en-light`, `desktop-support-ar-light`
- **States (4):** `en-states-rico-desktop`, `en-states-rico-mobile`,
  `en-states-app-desktop`, `en-states-app-mobile`

(Privacy / refund / terms have **no** reference PNGs — they are already live Atelier pages and
are represented in the hub as live links, not screenshots.)

## Hub tile inventory — 6 groups (from `_client.tsx`)

1. **Public landing** — Landing (EN/AR desktop, AR mobile).
2. **Auth** — Login (EN/AR desktop+mobile), Signup (EN desktop+mobile), Forgot password
   (EN desktop+mobile), Check email / verify + reset (EN desktop+mobile each).
3. **Onboarding** — one flow covering CV upload, profile confirmation, target-role/preferences
   (EN/AR desktop+mobile).
4. **Authenticated workspace** — Command/chat (**live → `/rico-preview`**, EN/AR desktop, EN
   mobile), Dashboard/home (+ app index), Profile, Settings, Applications/pipeline, Upload CV,
   Subscription/pricing.
5. **Support / legal** — Support/contact (EN/AR desktop, reference only), Privacy
   (**live → `/privacy`**), Refund policy (**live → `/refund-policy`**), Terms
   (**live → `/terms`**).
6. **States & design systems** — Rico states (**live → `/rico-preview`**), App states,
   Design gallery (**live → `/design-gallery`**), demonstrating empty/loading/error/mobile/
   RTL/light-dark.

## Design system (confirmed from the reference support-page colophon)

- **Type:** Fraunces (serif display) · Inter (body) · IBM Plex Mono (mono labels).
- **Palette:** "paper, ink, and one hot signal" — warm cream canvas, near-black ink, a single
  sun-red accent.
- **Languages:** English · العربية (RTL variants shipped for most screens).
- **Devices:** desktop + mobile for every screen group.
- **Three shells:** (A) marketing/support masthead (`Rico Hunt — VOLUME I · ISSUE 03`, ruled
  mono nav, dark COLOPHON footer); (B) minimal auth/onboarding header (serif `Rico` wordmark +
  lang/theme toggle); (C) workspace left sidebar (`Rico WORKSPACE` + Command/Profile/
  Applications/Upload CV/Settings). Production currently ships none of these three shells.

## Production vs target — classification (route by route)

| Route | Production today | Classification vs `/design-preview` |
|---|---|---|
| `/` | LandingPageV2 dark hero (below-fold cream only on unmerged #933 draft) | **Partially matches** — below-fold direction only; masthead/hero/hero-content missing |
| `/login` | Dark, working JWT auth | **Exists, wrong design** (+ ref shows "Continue with Google"; production has no OAuth) |
| `/signup` | Dark, working | **Exists, wrong design** |
| `/forgot-password` | Dark, working | **Exists, wrong design** |
| `/reset-password` | Dark, working | **Exists, wrong design** |
| `/verify-email` | Dark, working | **Exists, wrong design** |
| `/onboarding` | Redirect → `/command` + real 466-line page (hybrid dead-UI) | **Exists, wrong content/flow + blocked by hybrid state** (ref = 3-step intent flow; prod = CV-first) |
| `/command` | Dark chat, working | **Exists, wrong design — EXCLUDED, requires own DEC** |
| `/dashboard` | Nocturne dark + prod shell | **Exists, wrong design + shell change (Shell C) + sample-data** |
| `/profile` | Nocturne dark | **Exists, wrong design** |
| `/settings` | Nocturne dark | **Exists, wrong design** |
| `/flow` (`/applications` → redirect) | Nocturne dark `/flow` | **Exists, wrong design** + action/data risk |
| `/upload` | Nocturne dark | **Exists, wrong design** (CV-safety #916) |
| `/subscription` | Dark, manual/WhatsApp billing | **Exists, wrong design + billing gate** |
| `/support` / `/contact` | `/contact` + `/faq` exist (dark) | **Exists, wrong design + content/flow** (combined support page missing; contact form needs endpoint) |
| `/privacy` | Already cream Atelier | **Already matches** — preserve legal copy |
| `/refund-policy` | Already cream Atelier | **Already matches** — preserve copy |
| `/terms` | Cream (C1 pilot #879) | **Already matches / near** — preserve copy |
| States (empty/loading/error/mobile/RTL) | Scattered per-page | **Partially matches / missing** dedicated coverage |

## Content the package has that production lacks / differs

- Landing: masthead, hero "A career, in conversation." + red underline, interview-transcript
  block, sample-match plate (PLATE 01 / score ring / WHY THIS FITS / WORTH KNOWING),
  "Bilingual by design —" band, "Three quiet convictions" section.
- Auth: "Continue with Google" (no production OAuth); preview-only labels.
- Onboarding: reference intent-flow vs production CV-first — **different flows** (owner to pick canonical).
- Dashboard: profile-completeness meter, stat tiles, quick actions, recent activity, saved-roles
  with status pills — all **sample data**.
- Support: combined FAQ + contact form + dark colophon (production splits `/contact` + `/faq`;
  contact form has no backend endpoint).

## Recorded status

- `/design-preview` is the **approved production target for shape + content + flows** — see
  `DEC-20260710-002`.
- `DEC-20260710-001` (visual-only, per-phase) is **expanded** by `DEC-20260710-002`: the target
  is the full package, still delivered as small per-route PRs with owner visual approval gates,
  still excluding `/command` (own DEC), billing, and backend/auth/schema changes unless approved.
- PR #933 (landing below-the-fold cream) is **paused** and does not merge unless it becomes full
  public-landing parity; see the `DEC-20260710-002` follow-ups.
- Migration sequencing, risks, and the #933 decision live in the plan captured with this task
  (`TASK-20260710-003`, revised scope).

## Provenance

Built read-only from repo evidence by Claude, 2026-07-10: `ls apps/web/public/design-preview/`
(53 PNGs), `apps/web/app/design-preview/_client.tsx` (6-group tile inventory), and direct view
of the landing, auth-signin, onboarding, dashboard, and support reference PNGs. No `apps/web`
files changed; no #933 code touched. Docs-only.
