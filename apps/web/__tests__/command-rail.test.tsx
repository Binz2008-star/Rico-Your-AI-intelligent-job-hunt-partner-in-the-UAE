/**
 * CommandRail — slice 4e tests.
 *
 * Contracts:
 *  1. deriveSessionPicks: newest-first, deduped by title+company, capped,
 *     rico-turns-with-matches only (pure; no API involvement by construction).
 *  2. isStrongPick: real scores only; 0/null/undefined never read as strong;
 *     accepts both 0–1 and 0–100 scales.
 *  3. Rail renders shortlist items (company/title/location/score), the count,
 *     the empty state, and the pipeline section only when entries exist.
 *  4. Unauthenticated → renders nothing (public surface never mounts a rail).
 *  5. The only interactive element is the existing /applications route link.
 */

import {
    CommandRail,
    deriveSessionPicks,
    isStrongPick,
    type RailSourceMessage,
} from "@/components/command/CommandRail";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/workspace/theme", async () => {
    const actual = await vi.importActual<typeof import("@/components/workspace/theme")>(
        "@/components/workspace/theme",
    );
    return { ...actual, useWorkspaceTheme: () => actual.WORKSPACE_THEME.dark };
});
vi.mock("@/contexts/LanguageContext", () => ({
    useLanguage: () => ({ language: "en" }),
}));

const match = (title: string, company: string, extra: Record<string, unknown> = {}) =>
    ({ title, company, ...extra }) as never;

describe("deriveSessionPicks", () => {
    it("collects matches newest-first, deduped by title+company, capped", () => {
        const messages: RailSourceMessage[] = [
            { role: "rico", matches: [match("HSE Manager", "ADNOC"), match("ESG Lead", "Masdar")] },
            { role: "user" },
            { role: "rico", matches: [match("HSE Manager", "ADNOC"), match("QA Manager", "DP World")] },
        ];
        const picks = deriveSessionPicks(messages, 6);
        // Newest message first; ADNOC deduped (newest occurrence kept).
        expect(picks.map((p) => `${p.title}@${p.company}`)).toEqual([
            "HSE Manager@ADNOC",
            "QA Manager@DP World",
            "ESG Lead@Masdar",
        ]);
        expect(deriveSessionPicks(messages, 2)).toHaveLength(2);
    });

    it("ignores user turns and rico turns without matches", () => {
        expect(
            deriveSessionPicks([
                { role: "user", matches: [match("X", "Y")] },
                { role: "rico" },
                { role: "rico", matches: [] },
            ]),
        ).toEqual([]);
    });
});

describe("isStrongPick", () => {
    it("recognizes strong scores on both scales and rejects absent/zero", () => {
        expect(isStrongPick(0.92)).toBe(true);
        expect(isStrongPick(92)).toBe(true);
        expect(isStrongPick(0.5)).toBe(false);
        expect(isStrongPick(0)).toBe(false);
        expect(isStrongPick(null)).toBe(false);
        expect(isStrongPick(undefined)).toBe(false);
    });
});

describe("CommandRail", () => {
    it("renders nothing when unauthenticated", () => {
        render(<CommandRail authenticated={false} picks={[match("A", "B")]} pipeline={[]} />);
        expect(screen.queryByTestId("command-rail")).toBeNull();
    });

    it("renders shortlist items with company, title, location, count, and score accent", () => {
        render(
            <CommandRail
                authenticated
                picks={[
                    match("Senior HSE Manager", "ADNOC", { location: "Abu Dhabi", score: 0.92 }),
                    match("ESG Lead", "Masdar", { location: "Dubai", score: 0.5 }),
                ]}
                pipeline={[]}
            />,
        );
        expect(screen.getByTestId("command-rail")).toBeTruthy();
        expect(screen.getByTestId("command-rail-count").textContent).toBe("2");
        const items = screen.getAllByTestId("command-rail-pick");
        expect(items).toHaveLength(2);
        expect(items[0].textContent).toContain("ADNOC");
        expect(items[0].textContent).toContain("Senior HSE Manager");
        expect(items[0].textContent).toContain("Abu Dhabi");
        const scores = screen.getAllByTestId("command-rail-score");
        expect(scores[0].textContent).toBe("92%");
        expect(scores[1].textContent).toBe("50%");
        expect(screen.queryByTestId("command-rail-empty")).toBeNull();
    });

    it("shows the empty state when the session has no matches yet", () => {
        render(<CommandRail authenticated picks={[]} pipeline={[]} />);
        expect(screen.getByTestId("command-rail-empty")).toBeTruthy();
        expect(screen.getByTestId("command-rail-count").textContent).toBe("0");
    });

    it("renders the pipeline section only when entries exist", () => {
        const { rerender } = render(<CommandRail authenticated picks={[]} pipeline={[]} />);
        expect(screen.queryByTestId("command-rail-pipeline")).toBeNull();

        rerender(
            <CommandRail
                authenticated
                picks={[]}
                pipeline={[
                    { key: "1", company: "ADNOC", title: "HSE Manager", statusLabel: "Applied" },
                ]}
            />,
        );
        const row = screen.getByTestId("command-rail-pipeline");
        expect(row.textContent).toContain("ADNOC");
        expect(row.textContent).toContain("HSE Manager");
        expect(row.textContent).toContain("Applied");
    });

    it("links to the existing /applications route as its only interactive element", () => {
        render(<CommandRail authenticated picks={[]} pipeline={[]} />);
        const link = screen.getByTestId("command-rail-applications-link") as HTMLAnchorElement;
        expect(link.getAttribute("href")).toBe("/applications");
        expect(screen.getByTestId("command-rail").querySelectorAll("button")).toHaveLength(0);
    });
});
