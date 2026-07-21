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
    light: {
        dark: false,
        bg: "#F1EADD",
        panel: "#F7F1E6",
        rail: "#EDE5D6",
        inset: "#EAE1D0",
        ink: "#1F1B15",
        ink70: "rgba(31,27,21,0.70)",
        ink55: "rgba(31,27,21,0.52)",
        ink40: "rgba(31,27,21,0.38)",
        hair: "rgba(31,27,21,0.16)",
        activeBg: "rgba(31,27,21,0.06)",
        track: "rgba(31,27,21,0.10)",
        red: "#C6492E",
    },
    dark: {
        dark: true,
        bg: "#17140F",
        panel: "#211C15",
        rail: "#14110C",
        inset: "#2A241B",
        ink: "#EFE7D6",
        ink70: "rgba(239,231,214,0.72)",
        ink55: "rgba(239,231,214,0.54)",
        ink40: "rgba(239,231,214,0.40)",
        hair: "rgba(239,231,214,0.16)",
        activeBg: "rgba(239,231,214,0.08)",
        track: "rgba(239,231,214,0.12)",
        red: "#E0895A",
    },
};

export const WorkspaceThemeContext = createContext<WorkspacePalette>(WORKSPACE_THEME.light);

export function useWorkspaceTheme(): WorkspacePalette {
    return useContext(WorkspaceThemeContext);
}
