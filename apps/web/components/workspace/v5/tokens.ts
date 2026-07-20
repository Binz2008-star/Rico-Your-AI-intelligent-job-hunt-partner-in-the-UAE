/**
 * Command Workspace v5 — foundation tokens (PR 1 of the approved v5
 * implementation program; owner adoption decision 2026-07-20, evidence
 * package: design-handoffs/incoming/2026-07-20-command-workspace-v5-cinematic
 * at commit 69074a8 = the visual acceptance reference).
 *
 * Values are the artifact's audited palette: every *Text token already
 * carries the WCAG AA fix from EVIDENCE.md §6 (19 failing pairs corrected).
 * `check:contrast:v5` gates these pairs in CI the same way
 * `check:contrast` gates globals.css.
 *
 * Source-of-truth contract: the CSS custom properties live in
 * `./motion.css` (`.wsx5` scope) so plain CSS can consume them; this module
 * re-exports the SAME values for TS consumers. A unit test
 * (`__tests__/command-v5-foundation.test.tsx`) parses motion.css and fails
 * on any drift between the two — edit both together.
 *
 * This module intentionally does NOT touch WORKSPACE_THEME or ATELIER:
 * existing routes keep rendering byte-identically until their own v5 PRs.
 */

export const V5 = {
    /* paper world (light plane) */
    paper: "#F1EADD",
    panel: "#F7F1E6",
    panel2: "#EDE5D6",
    inset: "#EAE1D0",
    raise: "#FBF7EE",

    /* ink scale — ink55 is the AA-corrected secondary text (was .52) */
    ink: "#1F1B15",
    ink85: "rgba(31,27,21,.85)",
    ink70: "rgba(31,27,21,.70)",
    ink55: "rgba(31,27,21,.62)",
    ink40: "rgba(31,27,21,.38)" /* borders/decoration ONLY — never text */,
    ink25: "rgba(31,27,21,.24)",
    hair: "rgba(31,27,21,.14)",
    hair2: "rgba(31,27,21,.08)",

    /* deep cinematic plane */
    deep: "#191D2E",
    deepPanel: "#171B2B",
    deepPanel2: "#1F2439",
    deepEdge: "#131627",
    lightInk: "#F2ECDD",
    lightInk70: "rgba(242,236,221,.72)",
    lightInk58: "rgba(242,236,221,.58)" /* smallest AA text on deep */,
    lightInk50: "rgba(242,236,221,.5)",
    lightInk30: "rgba(242,236,221,.30)" /* decoration ONLY — never text */,
    deepHair: "rgba(242,236,221,.14)",

    /* energy palette (decorative / large surfaces) */
    terra: "#C6492E",
    terraDeep: "#9E3520",
    coral: "#E0895A",
    amber: "#E8A33D",
    gold: "#CA8A04",
    goldSoft: "#E7C46B",
    moss: "#3E7C4F",
    mossSoft: "#DCE8D8",
    purple: "#7A5CF0",
    electric: "#3D5BF5",
    electricSoft: "rgba(61,91,245,.14)",

    /* AA text-safe accent inks (EVIDENCE.md §6) — use these for any
       accent-colored TEXT or active icon on the paper plane */
    terraText: "#A83A22" /* 5.33:1 on paper */,
    amberText: "#8A5E0E" /* 4.76:1 */,
    goldText: "#77560A" /* 5.63:1 */,
    goldTextL: "#9C6705" /* 4.03:1 — large text (≥24px / 18.66px bold) only */,
    coralTextL: "#C05A28" /* 3.71:1 — large text only */,
    electricText: "#2F48D1" /* 5.91:1 */,
    purpleText: "#5B3ED6" /* 5.65:1 */,
    emberBtnEnd: "#BE452B" /* white ≥4.85:1 across the ember button */,
    onEmber: "#FFF7EC" /* label ink on ember-button fills */,
} as const;

/* Gradients — *Text variants keep every stop AA for their text size. */
export const V5_GRADIENT = {
    /** decorative ember (bars, rails, glows — never behind body text) */
    ember: `linear-gradient(98deg, ${V5.terra} 0%, ${V5.coral} 52%, ${V5.amber} 100%)`,
    /** display-headline accent words (large-text AA ≥3.0 at every stop) */
    emberDisplayText: "linear-gradient(98deg,#A83A22,#C6492E 50%,#B25419)",
    /** primary energetic button fill (white label ≥4.85:1 at every stop) */
    emberButton: `linear-gradient(98deg,#A83A22,${V5.emberBtnEnd})`,
    /** decorative gold */
    gold: `linear-gradient(98deg,#B07507 0%, ${V5.gold} 45%, ${V5.goldSoft} 100%)`,
    /** large gold numerals (≥3.0 at every stop) */
    goldNumeralText: "linear-gradient(98deg,#8F6203,#9C6705 60%,#B07507)",
    /** AI-moment accent (decorative) */
    ai: `linear-gradient(98deg, ${V5.electric}, ${V5.purple} 60%, ${V5.coral})`,
} as const;

/* Per-mode accent triples. modeA/modeB drive atmosphere and decoration;
   modeAText is the ONLY member allowed to color text/icons on paper. */
export type V5ModeKey =
    | "overview"
    | "search"
    | "applications"
    | "documents"
    | "interview"
    | "learning"
    | "activity";

export const V5_MODE_ACCENTS: Record<
    V5ModeKey,
    { modeA: string; modeB: string; modeAText: string }
> = {
    overview: { modeA: V5.terra, modeB: V5.amber, modeAText: V5.terraText },
    search: { modeA: V5.electric, modeB: V5.coral, modeAText: V5.electricText },
    applications: { modeA: V5.coral, modeB: V5.amber, modeAText: V5.terraText },
    documents: { modeA: V5.gold, modeB: V5.goldSoft, modeAText: V5.goldText },
    interview: { modeA: V5.terra, modeB: V5.electric, modeAText: V5.terraText },
    learning: { modeA: V5.purple, modeB: V5.goldSoft, modeAText: V5.purpleText },
    activity: { modeA: V5.terra, modeB: V5.electric, modeAText: V5.terraText },
};

/* Motion language (matches .wsx5 CSS vars in motion.css). */
export const V5_MOTION = {
    outExpo: "cubic-bezier(.16,1,.3,1)",
    spring: "cubic-bezier(.34,1.56,.64,1)",
    swift: "cubic-bezier(.4,0,.2,1)",
    fastMs: 180,
    medMs: 420,
    slowMs: 760,
} as const;

export const V5_RADIUS = { card: 18, hero: 26 } as const;

/* Typography roles (families resolve via route-scoped next/font variables —
   see ./fonts.ts; Fraunces reuses the shared atelier-kit loader). */
export const V5_FONT = {
    display:
        "var(--font-fraunces-landing), var(--font-naskh-arabic, 'Noto Naskh Arabic'), Georgia, serif",
    sans: "var(--font-space-grotesk), var(--font-sans-arabic, 'Noto Sans Arabic'), ui-sans-serif, system-ui, sans-serif",
    mono: "ui-monospace,'SF Mono','Cascadia Mono',Consolas,monospace",
} as const;
