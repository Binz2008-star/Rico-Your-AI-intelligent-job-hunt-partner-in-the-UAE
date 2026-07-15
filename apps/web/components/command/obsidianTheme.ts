/**
 * COMMAND_OBSIDIAN — route-scoped palette for `/command` only (slice C1 of the
 * Command Obsidian program; owner directive 2026-07-16).
 *
 * Values come verbatim from the canonical handoff
 * (`design-handoffs/reviewed/2026-07-16-command-obsidian-v4/canonical-files.md`,
 * ZIP `src/styles.css`): dark "Obsidian night" is the recording's mode and the
 * `/command` default; light is "Obsidian at dawn".
 *
 * It deliberately implements the existing `WorkspacePalette` interface so every
 * already-merged 4a–4e surface (composer, message rows, state cards, right
 * rail, MissionContextBar) repaints through the same context with zero
 * component changes. The `red` slot carries the palette's single accent — here
 * the acid-lime "sun" — because that is the semantic accent channel all
 * consumers read (send button, strong scores, hovers, focus rings).
 *
 * Route-scoped by construction: only `/command`'s chrome provides this palette.
 * No global `:root`/`body` styling, no change to WORKSPACE_THEME or any other
 * WorkspaceShell route.
 */

import type { WorkspacePalette } from "@/components/workspace/theme";

export const COMMAND_OBSIDIAN: { light: WorkspacePalette; dark: WorkspacePalette } = {
    /* "Obsidian at dawn" */
    light: {
        bg: "#f4f5f0",
        panel: "#fbfcf6",
        rail: "#f4f5f0",
        inset: "#e8ebe0",
        ink: "#0f1210",
        ink70: "#2f342e",
        ink55: "#626a5e",
        ink40: "rgba(98,106,94,0.72)",
        hair: "#d2d6c8",
        activeBg: "rgba(15,18,16,0.05)",
        track: "rgba(15,18,16,0.10)",
        red: "#3e6b0f",
    },
    /* "Obsidian night" — the recording's mode; /command default */
    dark: {
        bg: "#0a0b0d",
        panel: "#10131a",
        rail: "#0a0b0d",
        inset: "#12141a",
        ink: "#f2f4f0",
        ink70: "#c7ccc0",
        ink55: "#7a8078",
        ink40: "rgba(122,128,120,0.72)",
        hair: "#1f2229",
        activeBg: "rgba(242,244,240,0.06)",
        track: "rgba(242,244,240,0.12)",
        red: "#c8ff3f",
    },
};
