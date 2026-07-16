/**
 * COMMAND_ATELIER — route-scoped palette for `/command` only (Atelier re-skin;
 * owner decision 2026-07-16, DEC-20260716-001).
 *
 * Values come verbatim from the canonical Atelier token layer
 * (`apps/web/app/_atelier/atelier-tokens.css`): the light `.atelier` block is
 * "Atelier day" (warm paper) and the `.atelier[data-atl-theme="dark"]` block is
 * "Atelier at Night". This replaces the historical "Command Obsidian" acid-lime
 * palette, which is now reference-only per the decision record.
 *
 * It deliberately implements the existing `WorkspacePalette` interface so every
 * already-merged C1–C4 surface (CommandObsidianShell, transcript rows, composer,
 * MATCH job cards, MissionContextBar) repaints through the same
 * WorkspaceThemeContext with zero structural change. The `red` slot carries the
 * palette's single accent — here the Atelier **sun-red** (`--sun`), NOT the old
 * acid-lime — because that is the semantic accent channel all consumers read
 * (send button, strong scores, hovers, focus rings, selection).
 *
 * Route-scoped by construction: only `/command`'s chrome provides this palette.
 * No global `:root`/`body` styling, no change to WORKSPACE_THEME, the public/
 * guest Nocturne palette, or any other WorkspaceShell route.
 */

import type { WorkspacePalette } from "@/components/workspace/theme";

export const COMMAND_ATELIER: { light: WorkspacePalette; dark: WorkspacePalette } = {
    /* "Atelier day" — warm paper */
    light: {
        bg: "#f2ece0",
        panel: "#f8f3ea",
        rail: "#f2ece0",
        inset: "#e8dfcd",
        ink: "#14110d",
        ink70: "#3a342c",
        ink55: "#6b6355",
        ink40: "rgba(107,99,85,0.72)",
        hair: "#d3c9b4",
        activeBg: "rgba(20,17,13,0.05)",
        track: "rgba(20,17,13,0.10)",
        red: "#cf3d17",
    },
    /* "Atelier at Night" */
    dark: {
        bg: "#16130e",
        panel: "#1f1a12",
        rail: "#16130e",
        inset: "#1f1a12",
        ink: "#f2ece0",
        ink70: "#d7cebc",
        ink55: "#9a907d",
        ink40: "rgba(154,144,125,0.72)",
        hair: "#35302a",
        activeBg: "rgba(242,236,224,0.06)",
        track: "rgba(242,236,224,0.12)",
        red: "#ee6a3a",
    },
};
