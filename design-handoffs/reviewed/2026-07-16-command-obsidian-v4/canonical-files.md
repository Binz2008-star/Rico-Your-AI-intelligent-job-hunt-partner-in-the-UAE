# Canonical file inventory — Remix of Career Compass AI.zip

Reviewed 2026-07-16 against the recording. The ZIP was extracted to a local
scratch directory for inspection only; the raw archive stays uncommitted in
`design-handoffs/incoming/`.

## Canonical (the four files that define the target)

### 1. `src/routes/rico.tsx` (2,795 lines) — the console composition

Everything visible in the recording is implemented here. Key structures:

- **Root**: `h-dvh` flex column, `dir`/`lang` driven by a local i18n context,
  `bg-[var(--paper)] text-[var(--ink)]`, overflow hidden.
- **TopBar** (h-12, sticky, `bg-paper/85 backdrop-blur`, bottom hairline):
  PanelLeft toggle · brand "Rico" (display font, links home) · mono-eyebrow
  workspace tag `JOB HUNT · UAE` · `ms-auto` status (1.5px dot, lime pulse
  while busy; mono caps label READY / RICO IS WORKING / LIVE) · EN/ع toggle ·
  theme toggle · PanelRight toggle.
- **SessionsRail** (left, 260 px; `md:relative`, `<md` fixed overlay under the
  top bar with a backdrop button): mono-eyebrow `SESSIONS` + `+ new`; session
  rows (13px title + mono caps relative time; active row = card bg + 1px lime
  dot); footer rule `6 THREADS · JOB HUNT`.
- **Transcript** (center, `max-w-[720px]` centered, vertical `gap-6`):
  - opening slug row: mono caps `SESSION · date · time` + bordered lime
    `SAMPLE DATA · DEMO` chip + right-aligned `JOB HUNT · UAE` + `Skip ›`.
  - **Gutter** labels (mono 10px caps, `min-w-[64px]`): YOU (ink) · THINK ·
    PLAN · RUN/DONE · CHOOSE · WRITE (lime) · ✓ check · FAIL (lime) · ASK
    (lime) · MATCH · RICO (lime).
  - user turns: display font 22–26px, tight leading.
  - think: italic 15px muted.
  - plan: `n / total` mono header over rule; rows = lime-filled ✓ box +
    `01`-style mono index + strikethrough on completion.
  - tool rows: mono `name (arg)` + animated 3-dot ellipsis while running →
    `✓ note` in lime when done; arrow-prefixed detail lines behind a start
    hairline (`border-s`), LTR-forced.
  - error/FAIL: warning triangle + mono name(arg); lime `✗ message` behind a
    2px lime start border; italic retry note.
  - ask: question + pill options (picked = lime border/tint + `→`; rejected =
    strikethrough muted) + mono caps echo `YOU · <choice>`.
  - say/RICO: 16px ink text; final "done" rows get a top rule, a lime Sparkle
    ✦ prefix, and suggestion pill buttons (`→ label`, mono 11px).
  - streaming cursor: 7px × 1.05em ink block, pulse; standalone `…` gutter
    cursor row while busy.
- **JobMatchLine** (MATCH card): card bg + hairline (lime border + ring/glow
  when recommended); header = display 18px role + `RICO PICKS` lime pill +
  `SAMPLE DATA` chip + ScorePip (92% style, tiered strong/solid/stretch);
  mono meta row (Building2 company · MapPin city · Wallet salary · posted);
  `WHY IT FITS YOU` block behind 2px lime start border with lime `→` bullets;
  `HONEST GAPS` italic `·` bullets; footer actions `TAILOR CV & APPLY`
  (ink-filled button, lime hover) · `SAVE` · `SKIP` + `FIT · 92%`.
- **ShortlistRail** (right, 300 px, `lg:relative`, `<lg` fixed end-overlay):
  `SHORTLIST` + count; empty state italic "Empty for now — Rico fills this as
  he scores matches."; job mini-cards (display company + small ScorePip +
  mono role + mono caps city + lime `✦ RICO PICKS`); `PIPELINE` + count
  (company + lime stage caps + segmented stage bar: done 60% ink / current
  lime / rest rule + mono `NEXT · …`); `SIGNAL` + count (icon + mono LTR path
  + caps op tag GREP/READ/WRITE, write ops in lime).
- **Composer** (sticky bottom, gradient fade from paper): rounded-2xl card
  row = lime `/` glyph · paperclip · autosizing textarea (Enter submits) ·
  ink square send/stop button (lime hover); hints row = `⌘K COMMANDS` +
  `/FIND /TAILOR /TRACK` mono caps + `↻ reset` end-aligned.
- Additional step renderers seen in the recording: FormLine (profile
  confirm-changes card with field rows, `✓ COMMITTED`, `SAVED`/EDIT footer),
  TrackerLine, ReminderLine, AnalyticsLine (funnel bars + benchmark deltas +
  `WHAT THIS MEANS` ✓/! insights + `DO THIS NEXT` numbered actions).

**Do NOT port from this file:** TanStack `createFileRoute`/server fns,
`localStorage` live-history persistence (`rico.live.v1`), the scripted
walkthrough runner, `ricoChat` AI-gateway calls, mock sessions/job data,
`PrototypeNoticeToast`.

### 2. `src/styles.css` (371 lines) — the Obsidian token system

- Fonts: Space Grotesk (display) · Inter (body) · JetBrains Mono (meta) ·
  Fraunces italic accents; Arabic: IBM Plex Sans Arabic + Amiri display.
- **Light "Obsidian at dawn"**: paper `#f4f5f0` · paper-2 `#e8ebe0` · ink
  `#0f1210` · ink-soft `#2f342e` · ink-mute `#626a5e` · rule `#d2d6c8` · card
  `#fbfcf6` · sun `#3e6b0f` · sun-soft `#6ea41f` · destructive `#b23a1a`.
- **Dark "Obsidian night"** (the recording's mode, default for `/command`):
  paper `#0a0b0d` · paper-2 `#12141a` · ink `#f2f4f0` · ink-soft `#c7ccc0` ·
  ink-mute `#7a8078` · rule `#1f2229` · card `#10131a` · **sun `#c8ff3f`** ·
  sun-soft `#9de81a` · destructive `#ff5a4a`; primary/accent/ring = sun;
  selection = sun on near-black.
- Radius base 0.375rem. Plate shadow with faint lime top edge in dark.
- **Grid grain**: fixed 64px × 64px 1px grid of `ink-mute` at 5% opacity,
  radially masked toward the top-center. **Lime aura**: fixed radial lime
  ellipse above the viewport, blur 60px, 8% light / 20% dark.
  (Prototype applies these via global `body::before/::after` — Rico must
  re-implement them as route-scoped elements inside the `/command` chrome.)
- Utilities to mirror in spirit: `mono-eyebrow` (mono 11px, 0.18em caps,
  ink-mute), `serif`→display, `serif-italic`→Fraunces, rules, `ink-underline`
  (lime underline), caret/fade-up/drift keyframes.
- Arabic: `:lang(ar)` swaps stacks, zeroes letter-spacing; `mono-eyebrow`
  under RTL drops uppercase tracking for 12px Arabic sans.

### 3. `src/lib/rico-content.ts` (1,719 lines) — bilingual console strings

`RicoUI` dictionaries (EN + AR) for: top-bar status labels + workspace tag,
sessions rail strings, gutter labels, slug/sample chips, composer
placeholders/hints/reset, jobMatch labels (WHY IT FITS YOU / HONEST GAPS /
TAILOR CV & APPLY / SAVE / SKIP / FIT / RICO PICKS / SAMPLE DATA), ScorePip
tiers, shortlist-rail labels (SHORTLIST / PIPELINE / SIGNAL / empty copy /
NEXT), tracker stage names, ask/form labels, live-mode status strings — plus
the scripted demo content (demo script itself is NOT ported).

### 4. `src/lib/i18n.tsx` (245 lines) — EN/AR + theme toggles

`LangProvider` (localStorage-backed en/ar, sets `dir`/`lang`), `LangToggle`
(EN | ع segmented control), `ThemeToggle` (`.dark` class toggle, dark
default). Rico already has its own language context and local theme islands —
port the **visual pattern** (segmented mono toggle, sun/moon button), not the
provider implementation.

## Reviewed and rejected (present in ZIP, NOT targets)

- `src/routes/app.command.tsx` and every other `src/routes/app.*` — older
  cream/paper direction, explicitly excluded by the owner.
- `design-reference/command-concept/*`, `design-handoff/`, `DESIGN-HANDOFF.md`,
  `HANDOFF_TO_CLAUDE.md`, `AGENTS.md`, `.lovable/`, `mem/` — historical or
  agent-instruction material; conflicting directions.
- `src/lib/ai-gateway.server.ts`, `src/lib/rico.functions.ts`, `src/routes/api/*`
  — prototype backend; prohibited.
- `src/lib/rico-jobs.ts`, `rico-schemas.ts`, `rico-storage.test.ts` — mock
  data/localStorage state; prohibited.
