/**
 * Slice 4d — job-match / application / profile-gap cards under AtelierCardScope.
 *
 * 4d wraps the render sites of the three remaining /command card families in
 * AtelierCardScope (authenticated surface only). The card components are NOT
 * edited — this suite pins the contracts that make that safe:
 *
 *  1. AtelierCardScope remains layout-transparent (display:contents) and
 *     remaps the channel variables these cards consume (surface/overlay/
 *     gold/text) to the active Atelier palette.
 *  2. Card-shaped children (article/list/link markup like JobMatchCard,
 *     ApplicationStatusCard, ProfileGapCard emit) pass through structurally
 *     unchanged — same tags, same test ids, same interactive elements.
 *  3. Public/guest (authenticated=false) renders children verbatim with no
 *     scope wrapper — the public surface stays pre-4d byte-identical.
 *  4. Semantic status hues (emerald success, amber warning) are NOT part of
 *     the remap — the scope only overrides the design-system channels.
 */

import { atelierCardVars, AtelierCardScope } from "@/components/command/CommandStates";
import { WORKSPACE_THEME } from "@/components/workspace/theme";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

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

/** Minimal stand-in with the same structural surface as JobMatchCard output. */
function FakeJobCard() {
    return (
        <article data-testid="opportunity-card" aria-label="Job match: HSE Manager at ADNOC">
            <div data-testid="opportunity-card-title" className="text-rico-text">HSE Manager</div>
            <span data-testid="job-score" className="text-gold">92%</span>
            <a data-testid="job-link-apply" href="https://example.com/apply" className="bg-gold/10 text-gold">
                Apply
            </a>
            <button type="button" data-testid="mark-applied" className="text-emerald-200 bg-emerald-500/10">
                Mark as applied
            </button>
        </article>
    );
}

describe("4d — job/application/profile-gap cards under AtelierCardScope", () => {
    it("passes card markup through structurally unchanged when authenticated", () => {
        render(
            <AtelierCardScope authenticated>
                <FakeJobCard />
            </AtelierCardScope>,
        );
        const scope = screen.getByTestId("atelier-card-scope");
        expect(scope.style.display).toBe("contents");

        const card = screen.getByTestId("opportunity-card");
        expect(card.tagName).toBe("ARTICLE");
        expect(card.getAttribute("aria-label")).toBe("Job match: HSE Manager at ADNOC");
        expect(screen.getByTestId("opportunity-card-title").textContent).toBe("HSE Manager");
        expect(screen.getByTestId("job-score").textContent).toBe("92%");
        const apply = screen.getByTestId("job-link-apply") as HTMLAnchorElement;
        expect(apply.href).toBe("https://example.com/apply");
        expect(screen.getByTestId("mark-applied")).toBeTruthy();
        expect(scope.contains(card)).toBe(true);
    });

    it("remaps the channel variables the cards consume to the Atelier palette", () => {
        render(
            <AtelierCardScope authenticated>
                <FakeJobCard />
            </AtelierCardScope>,
        );
        const scope = screen.getByTestId("atelier-card-scope");
        // gold accents (score pill, apply button) → sun-red channel
        expect(scope.style.getPropertyValue("--gold")).toBe(hexChannels(DARK.red));
        // card surfaces → paper panel channel
        expect(scope.style.getPropertyValue("--surface-elevated")).toBe(hexChannels(DARK.panel));
        // hairline borders (overlay channel) → ink tint
        expect(scope.style.getPropertyValue("--overlay")).toBe(hexChannels(DARK.ink));
        // primary/secondary/muted text → ink tiers
        expect(scope.style.getPropertyValue("--text-primary")).toBe(hexChannels(DARK.ink));
        expect(scope.style.getPropertyValue("--text-secondary")).toMatch(/^\d+ \d+ \d+$/);
        expect(scope.style.getPropertyValue("--text-muted")).toMatch(/^\d+ \d+ \d+$/);
    });

    it("does not touch semantic status hues (emerald/amber stay literal)", () => {
        const vars = atelierCardVars(DARK) as Record<string, string>;
        // The remap must never define semantic-status channels — Tailwind
        // emerald/amber/rose literals in the cards resolve outside the scope.
        expect(Object.keys(vars).some((k) => /emerald|amber|rose|success/.test(k))).toBe(false);
    });

    it("renders children verbatim on the public surface — no wrapper, no overrides", () => {
        render(
            <AtelierCardScope authenticated={false}>
                <FakeJobCard />
            </AtelierCardScope>,
        );
        expect(screen.queryByTestId("atelier-card-scope")).toBeNull();
        expect(screen.getByTestId("opportunity-card")).toBeTruthy();
    });

    it("keeps interactive children clickable through the scope", () => {
        const onClick = vi.fn();
        render(
            <AtelierCardScope authenticated>
                <button type="button" data-testid="card-action" onClick={onClick}>
                    Save job
                </button>
            </AtelierCardScope>,
        );
        screen.getByTestId("card-action").click();
        expect(onClick).toHaveBeenCalledTimes(1);
    });
});
