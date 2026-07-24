"use client";

/**
 * Shared workspace-island theme (Shell C). WorkspaceShell owns a LOCAL
 * light/dark toggle and provides the active palette through this context so
 * the shell chrome and the page content (DashboardAtelier, and future
 * workspace pages) always render with one consistent set of colors — light
 * or dark. This is deliberately NOT the global ThemeContext: the dark
 * Nocturne app default is never touched.
 */

import { createContext, useContext } from "react";

export interface WorkspacePalette {
    /** True on the dark island. v5 paper-plane treatments (Command v5 PR 3)
     *  apply only when false — the dark island keeps its own language. */
    dark: boolean;
    bg: string;
    panel: string;
    rail: string;
    inset: string;
    ink: string;
    ink70: string;
    ink55: string;
    ink40: string;
    hair: string;
    activeBg: string;
    track: string;
    red: string;
}

export const WORKSPACE_THEME: { light: WorkspacePalette; dark: WorkspacePalette } = {
    /* Values are the owner-supplied Command Workspace artifact palettes
       (LIGHT/DARK), applied 2026-07-21 — they supersede the earlier v5
       rebuild palette entirely. */
    light: {
        dark: false,
        bg: "#F2ECE0" /* paper */,
        panel: "#F6F0E5" /* paperCard */,
        rail: "#EAE1CD" /* paper2 */,
        inset: "#EAE1CD",
        ink: "#14110D",
        ink70: "#3A342C" /* inkSoft */,
        ink55: "#6B6355" /* inkMute */,
        ink40: "rgba(20,17,13,0.40)",
        hair: "#D3C9B4" /* rule */,
        activeBg: "rgba(20,17,13,0.05)",
        track: "#E0D6BF" /* ruleSoft */,
        red: "#CF3D17" /* sun */,
    },
    dark: {
        dark: true,
        bg: "#16130E" /* paper */,
        panel: "#1A1710" /* paperCard */,
        rail: "#1E1A12" /* paper2 */,
        inset: "#1E1A12",
        ink: "#F2ECE0",
        ink70: "#D7CEBC" /* inkSoft */,
        ink55: "#9A907D" /* inkMute */,
        ink40: "rgba(242,236,224,0.40)",
        hair: "#35302A" /* rule */,
        activeBg: "rgba(242,236,224,0.07)",
        track: "#2A2620" /* ruleSoft */,
        red: "#EE6A3A" /* sun */,
    },
};

export const WorkspaceThemeContext = createContext<WorkspacePalette>(WORKSPACE_THEME.light);

export function useWorkspaceTheme(): WorkspacePalette {
    return useContext(WorkspaceThemeContext);
}

// The dark/light toggle previously lived in plain useState(defaultDark) with
// no persistence at all, so it reset to each route's hardcoded default on
// every remount (switching tabs/pages, a full reload) even right after the
// user explicitly chose the other theme — a real reported bug. Persisted here
// as one shared, explicit user preference (mirrors LanguageContext's
// single-key pattern) so an explicit choice sticks across the whole app.
// `defaultDark` (per-route) still governs the FIRST-EVER visit, before the
// user has ever toggled anything.
const WORKSPACE_DARK_STORAGE_KEY = "rico-workspace-dark";

export function readStoredWorkspaceDark(): boolean | null {
    try {
        const stored = localStorage.getItem(WORKSPACE_DARK_STORAGE_KEY);
        if (stored === "1") return true;
        if (stored === "0") return false;
    } catch {
        // Ignore localStorage errors (private browsing, disabled storage, SSR).
    }
    return null;
}

export function writeStoredWorkspaceDark(dark: boolean): void {
    try {
        localStorage.setItem(WORKSPACE_DARK_STORAGE_KEY, dark ? "1" : "0");
    } catch {
        // Ignore localStorage errors.
    }
}
