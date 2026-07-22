/**
 * Command Workspace — foundation tokens.
 *
 * Source of truth: the owner-supplied Command Workspace artifact
 * (Rico_Command_Workspace_v5.dc.html, applied 2026-07-21 on the owner's
 * direct instruction — it supersedes the earlier v5 rebuild palette
 * entirely). Values are the artifact's LIGHT/DARK palettes and MODE_THEME
 * accents; every *Text token is an AA-corrected variant of its artifact
 * accent (darkened until ≥4.5:1 on paper — same policy the accepted
 * evidence package used).
 *
 * Source-of-truth contract: the CSS custom properties live in
 * `./motion.css` (`.wsx5` scope) so plain CSS can consume them; this module
 * re-exports the SAME values for TS consumers. A unit test
 * (`__tests__/command-v5-foundation.test.tsx`) parses motion.css and fails
 * on any drift between the two — edit both together.
 */

export const V5 = {
    /* paper world (artifact LIGHT) */
    paper: "#F2ECE0",
    panel: "#F6F0E5" /* artifact paperCard */,
    panel2: "#EAE1CD" /* artifact paper2 */,
    inset: "#EAE1CD",
    raise: "#F6F0E5",

    /* ink scale (artifact ink / inkSoft / inkMute) */
    ink: "#14110D",
    ink85: "rgba(20,17,13,.85)",
    ink70: "#3A342C" /* inkSoft, 10.4:1 */,
    ink55: "#6B6355" /* inkMute, 5.04:1 */,
    ink40: "rgba(20,17,13,.38)" /* borders/decoration ONLY — never text */,
    ink25: "rgba(20,17,13,.24)",
    hair: "#D3C9B4" /* artifact rule */,
    hair2: "#E0D6BF" /* artifact rule-soft */,

    /* deep plane (artifact DARK) */
    deep: "#16130E",
    deepPanel: "#1A1710" /* dark paperCard */,
    deepPanel2: "#1E1A12" /* dark paper2 */,
    deepEdge: "#120F0A",
    lightInk: "#F2ECE0",
    lightInk70: "#D7CEBC" /* dark inkSoft */,
    lightInk58: "#9A907D" /* dark inkMute, 5.5:1 on deepPanel2 */,
    lightInk50: "rgba(242,236,224,.5)",
    lightInk30: "rgba(242,236,224,.3)" /* decoration ONLY — never text */,
    deepHair: "#35302A" /* dark rule */,

    /* energy palette (artifact sun + MODE_THEME accents; decorative) */
    terra: "#CF3D17" /* sun */,
    terraDeep: "#B23A1A" /* destructive */,
    coral: "#E07A3A" /* applications accent-2 */,
    amber: "#D99C4E" /* overview/documents accent-2 */,
    gold: "#B8791A" /* search accent */,
    goldSoft: "#E0A93F" /* search accent-2 */,
    moss: "#3C7A52" /* success / learning accent */,
    mossSoft: "#DCE8D8",
    purple: "#7FA9C7" /* interview accent-2 (info-soft) */,
    electric: "#3A5F7D" /* info / interview accent */,
    electricSoft: "rgba(58,95,125,.12)",

    /* AA text-safe accent inks — use these for any accent-colored TEXT or
       active icon on the paper plane (artifact accents darkened to ≥4.5) */
    terraText: "#C33916" /* 4.56:1 on paper */,
    coralText: "#B24827" /* 4.64:1 — applications accent text */,
    amberText: "#906025" /* 4.59:1 — documents/vault accent text */,
    goldText: "#936115" /* 4.51:1 — search accent text */,
    mossText: "#3A754F" /* 4.65:1 — learning accent text */,
    logText: "#8A5A2B" /* 4.99:1 — activity accent text */,
    electricText: "#3A5F7D" /* 5.73:1 */,
    goldTextL: "#B8791A" /* 3.08:1 — large text (≥24px / 18.66px bold) only */,
    coralTextL: "#C24E2A" /* 4.04:1 — large text only */,
    emberBtnEnd: "#B23A1A" /* white 5.98:1 at the button-gradient end */,
    onEmber: "#FFFFFF" /* label ink on sun/ember button fills (≥4.85:1) */,
} as const;

/* Gradients — *Text variants keep every stop AA for their text size. */
export const V5_GRADIENT = {
    /** decorative sun→amber sweep (bars, rails, glows — never behind body text) */
    ember: `linear-gradient(100deg, ${V5.terra} 0%, ${V5.coral} 55%, ${V5.amber} 100%)`,
    /** display-headline accent words (large-text AA ≥3.0 at every stop) */
    emberDisplayText: "linear-gradient(100deg,#C33916,#CF3D17 50%,#A8702B)",
    /** primary energetic button fill (white label ≥4.85:1 at every stop) */
    emberButton: `linear-gradient(98deg,${V5.terra},${V5.emberBtnEnd})`,
    /** decorative gold */
    gold: `linear-gradient(98deg,#936115 0%, ${V5.gold} 45%, ${V5.goldSoft} 100%)`,
    /** large gold numerals (≥3.0 at every stop) */
    goldNumeralText: "linear-gradient(98deg,#7D5312,#936115 60%,#B8791A)",
    /** AI-moment accent (decorative) */
    ai: `linear-gradient(98deg, ${V5.electric}, ${V5.purple} 60%, ${V5.coral})`,
} as const;

/* Per-mode accent triples (artifact MODE_THEME). modeA/modeB drive
   atmosphere, decoration and the animated display-word gradient;
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
    overview: { modeA: "#CF3D17", modeB: "#D99C4E", modeAText: V5.terraText },
    search: { modeA: "#B8791A", modeB: "#E0A93F", modeAText: V5.goldText },
    applications: { modeA: "#C24E2A", modeB: "#E07A3A", modeAText: V5.coralText },
    documents: { modeA: "#A8702B", modeB: "#D99C4E", modeAText: V5.amberText },
    interview: { modeA: "#3A5F7D", modeB: "#7FA9C7", modeAText: V5.electricText },
    learning: { modeA: "#3C7A52", modeB: "#6FBE8F", modeAText: V5.mossText },
    activity: { modeA: "#8A5A2B", modeB: "#CF3D17", modeAText: V5.logText },
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

/* Artifact radii: sections 16, rail rows 8, buttons 9. */
export const V5_RADIUS = { card: 16, hero: 16 } as const;

/* Typography roles (artifact FONT_EN/FONT_AR: Fraunces + Inter + IBM Plex
   Mono; Amiri + IBM Plex Sans Arabic. Families resolve via route-scoped
   next/font variables — see ./fonts.ts; Fraunces reuses the shared
   atelier-kit loader). */
export const V5_FONT = {
    display:
        "var(--font-fraunces-landing), var(--font-amiri-v5, 'Amiri'), Georgia, serif",
    sans: "var(--font-inter-v5), var(--font-plex-arabic-v5, 'IBM Plex Sans Arabic'), ui-sans-serif, system-ui, sans-serif",
    mono: "var(--font-plex-mono-v5), ui-monospace,'SF Mono','Cascadia Mono',Consolas,monospace",
} as const;
