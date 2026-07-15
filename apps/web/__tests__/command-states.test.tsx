/**
 * CommandStates — slice 4c tests
 *
 * Rendering contracts for the Atelier transient/interactive surfaces
 * (tool execution, permission, attachment/CV, loading/thinking/streaming,
 * error/retry):
 *
 *  1.  AtelierCardScope remaps the design-system channel variables
 *      (surface/overlay/gold/text) to the active Atelier palette — but only
 *      when authenticated. It is layout-transparent (display:contents) so it
 *      cannot shift the cards it wraps.
 *  2.  Public/guest surface renders children verbatim — no scope wrapper, no
 *      variable overrides (pre-4c behaviour preserved).
 *  3.  The remapped `--gold` channel equals the Atelier sun-red, so the
 *      cards' gold CTAs/borders repaint to the accent.
 *  4.  Job/application cards are NOT this component's concern — the scope
 *      passes any child through untouched (structure preserved).
 *  5.  AtelierWorkingIndicator keeps the WorkingIndicator a11y contract
 *      (role="status", polite live region, sr-only label) and renders the
 *      serif "R" mark + sun-red typing dots via the scoped --gold.
 */

import {
    AtelierCardScope,
    AtelierWorkingIndicator,
    atelierCardVars,
} from "@/components/command/CommandStates";
import { WORKSPACE_THEME } from "@/components/workspace/theme";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

// Match how 4a/4b unit-test the Atelier surface: pin the dark Atelier palette
// (the /command default via WorkspaceShell defaultDark).
const DARK = WORKSPACE_THEME.dark;
vi.mock("@/components/workspace/theme", async () => {
    const actual = await vi.importActual<typeof import("@/components/workspace/theme")>(
        "@/components/workspace/theme",
    );
    return { ...actual, useWorkspaceTheme: () => actual.WORKSPACE_THEME.dark };
});

function hexChannels(hex: string): string {
    const h = hex.replace("#", "");
    return `${parseInt(h.slice(0, 2), 16)} ${parseInt(h.slice(2, 4), 16)} ${parseInt(h.slice(4, 6), 16)}`;
}

describe("atelierCardVars", () => {
    it("maps the accent (--gold) to the palette sun-red channel", () => {
        const vars = atelierCardVars(DARK) as Record<string, string>;
        expect(vars["--gold"]).toBe(hexChannels(DARK.red));
        expect(vars["--gold-hover"]).toBe(hexChannels(DARK.red));
    });

    it("maps surface/bg to paper-panel channels and ink to text-primary", () => {
        const vars = atelierCardVars(DARK) as Record<string, string>;
        expect(vars["--surface"]).toBe(hexChannels(DARK.panel));
        expect(vars["--surface-elevated"]).toBe(hexChannels(DARK.panel));
        expect(vars["--bg"]).toBe(hexChannels(DARK.bg));
        expect(vars["--text-primary"]).toBe(hexChannels(DARK.ink));
        // Ink-tinted hairline/glass channel.
        expect(vars["--overlay"]).toBe(hexChannels(DARK.ink));
    });

    it("derives solid, alpha-modifiable channels for secondary/muted text", () => {
        const vars = atelierCardVars(DARK) as Record<string, string>;
        // Composited, not raw ink — three integer channels.
        expect(vars["--text-secondary"]).toMatch(/^\d+ \d+ \d+$/);
        expect(vars["--text-muted"]).toMatch(/^\d+ \d+ \d+$/);
        expect(vars["--text-secondary"]).not.toBe(vars["--text-primary"]);
        expect(vars["--text-muted"]).not.toBe(vars["--text-secondary"]);
    });
});

describe("AtelierCardScope", () => {
    it("wraps children in a layout-transparent scope that overrides the channels when authenticated", () => {
        render(
            <AtelierCardScope authenticated>
                <div data-testid="child" className="bg-surface text-gold" />
            </AtelierCardScope>,
        );
        const scope = screen.getByTestId("atelier-card-scope");
        // display:contents → no box, cannot shift layout.
        expect(scope.style.display).toBe("contents");
        expect(scope.style.getPropertyValue("--gold")).toBe(hexChannels(DARK.red));
        expect(scope.style.getPropertyValue("--surface")).toBe(hexChannels(DARK.panel));
        // Child is passed through untouched.
        expect(screen.getByTestId("child")).toBeTruthy();
        expect(scope.contains(screen.getByTestId("child"))).toBe(true);
    });

    it("renders children verbatim on the public surface — no scope wrapper, no overrides", () => {
        render(
            <AtelierCardScope authenticated={false}>
                <div data-testid="child" />
            </AtelierCardScope>,
        );
        expect(screen.queryByTestId("atelier-card-scope")).toBeNull();
        expect(screen.getByTestId("child")).toBeTruthy();
    });

    it("preserves arbitrary (e.g. job-card) children without altering their structure", () => {
        render(
            <AtelierCardScope authenticated>
                <article data-testid="job-card">
                    <button data-testid="job-action">Apply</button>
                </article>
            </AtelierCardScope>,
        );
        const card = screen.getByTestId("job-card");
        expect(card.tagName).toBe("ARTICLE");
        expect(screen.getByTestId("job-action").textContent).toBe("Apply");
    });
});

describe("AtelierWorkingIndicator", () => {
    it("keeps the WorkingIndicator accessibility contract", () => {
        render(<AtelierWorkingIndicator message="Rico is working" />);
        const row = screen.getByTestId("atelier-working-indicator");
        expect(row.getAttribute("role")).toBe("status");
        expect(row.getAttribute("aria-live")).toBe("polite");
        expect(row.getAttribute("aria-label")).toBe("Rico is working");
        // Visible + sr-only label present.
        expect(screen.getAllByText("Rico is working").length).toBeGreaterThanOrEqual(1);
    });

    it("renders the serif R mark and scopes --gold so the typing dots read sun-red", () => {
        render(<AtelierWorkingIndicator message="Searching" />);
        const row = screen.getByTestId("atelier-working-indicator");
        expect(screen.getByTestId("atelier-rico-mark")).toBeTruthy();
        expect(row.style.getPropertyValue("--gold")).toBe(hexChannels(DARK.red));
        expect(row.querySelector(".rico-dots")).toBeTruthy();
    });
});
