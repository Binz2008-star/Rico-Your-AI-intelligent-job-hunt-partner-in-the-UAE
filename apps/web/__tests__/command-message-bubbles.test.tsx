/**
 * CommandMessages — slice 4b tests
 *
 * Rendering contracts for the Atelier message rows and empty state:
 *  1.  Authenticated user turn renders the Atelier paper surface (ink text,
 *      panel background, hairline border) — no gold pill.
 *  2.  Authenticated Rico turn flows with the serif "R" mark; the mark is
 *      hidden (grouping) when not first in group.
 *  3.  Structured (profile_preview) Rico turn gets the paper panel.
 *  4.  Public surface keeps the pre-4b classes (gold bubble, rico-orb).
 *  5.  Long words/URLs get break-words; user bubble caps width.
 *  6.  AtelierMarkdownScope overrides --rico-* vars only when authenticated.
 *  7.  Empty-state hero: mark + title + subtitle + chips; chips fire their
 *      existing callbacks and respect disabled.
 *  8.  Empty-state chips variant renders chips only.
 *  9.  Public empty state keeps the pre-4b classes.
 * 10.  Content direction stays dir="auto" (Arabic-safe), rows anchored ltr.
 */

import {
    AtelierMarkdownScope,
    CommandEmptyState,
    CommandMessageRow,
} from "@/components/command/CommandMessages";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/workspace/theme", () => ({
    useWorkspaceTheme: () => ({
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
    }),
}));

const ACTIONS = [
    { key: "a", label: "Find jobs", icon: <svg data-testid="icon-a" />, onClick: vi.fn() },
    { key: "b", label: "Upload CV", icon: <svg data-testid="icon-b" />, onClick: vi.fn() },
];

describe("CommandMessageRow — Atelier surface (authenticated)", () => {
    it("renders the user turn on a paper surface with ink text, no gold pill", () => {
        const { container } = render(
            <CommandMessageRow authenticated role="user" isFirstInGroup isStructured={false}>
                Find me QHSE roles
            </CommandMessageRow>,
        );
        const row = screen.getByTestId("atelier-user-row");
        expect(row.className).toContain("justify-end");
        const bubble = row.firstElementChild as HTMLElement;
        expect(bubble.getAttribute("dir")).toBe("auto");
        expect(bubble.style.color).toBeTruthy();
        expect(bubble.style.background).toBeTruthy();
        expect(bubble.style.border).toContain("1px solid");
        expect(bubble.className).toContain("break-words");
        expect(bubble.className).toContain("max-w-[84%]");
        expect(container.querySelector(".bg-gold")).toBeNull();
        expect(container.querySelector(".rico-orb")).toBeNull();
    });

    it("renders the Rico turn as flowing text with the serif mark", () => {
        const { container } = render(
            <CommandMessageRow authenticated role="rico" isFirstInGroup isStructured={false}>
                Here are three roles.
            </CommandMessageRow>,
        );
        const row = screen.getByTestId("atelier-rico-row");
        expect(row.className).toContain("justify-start");
        const mark = screen.getByTestId("atelier-rico-mark");
        expect(mark.className).not.toContain("invisible");
        expect(mark.textContent).toBe("R");
        const body = row.lastElementChild as HTMLElement;
        expect(body.getAttribute("dir")).toBe("auto");
        expect(body.className).toContain("break-words");
        expect(body.style.background).toBe("");
        expect(container.querySelector(".rico-orb")).toBeNull();
    });

    it("hides the mark on grouped (non-first) Rico turns", () => {
        render(
            <CommandMessageRow authenticated role="rico" isFirstInGroup={false} isStructured={false}>
                …and a fourth.
            </CommandMessageRow>,
        );
        expect(screen.getByTestId("atelier-rico-mark").className).toContain("invisible");
    });

    it("gives structured turns the paper panel", () => {
        render(
            <CommandMessageRow authenticated role="rico" isFirstInGroup isStructured>
                profile preview
            </CommandMessageRow>,
        );
        const body = screen.getByTestId("atelier-rico-row").lastElementChild as HTMLElement;
        expect(body.style.background).toBeTruthy();
        expect(body.style.border).toContain("1px solid");
    });
});

describe("CommandMessageRow — public surface unchanged", () => {
    it("keeps the gold user bubble", () => {
        const { container } = render(
            <CommandMessageRow authenticated={false} role="user" isFirstInGroup isStructured={false}>
                hello
            </CommandMessageRow>,
        );
        expect(container.querySelector(".bg-gold")).not.toBeNull();
        expect(screen.queryByTestId("atelier-user-row")).toBeNull();
    });

    it("keeps the rico-orb avatar", () => {
        const { container } = render(
            <CommandMessageRow authenticated={false} role="rico" isFirstInGroup isStructured={false}>
                hi
            </CommandMessageRow>,
        );
        expect(container.querySelector(".rico-orb")).not.toBeNull();
        expect(screen.queryByTestId("atelier-rico-mark")).toBeNull();
    });
});

describe("AtelierMarkdownScope", () => {
    it("overrides the --rico-* variables when authenticated", () => {
        render(
            <AtelierMarkdownScope authenticated>
                <p>md</p>
            </AtelierMarkdownScope>,
        );
        const scope = screen.getByTestId("atelier-markdown-scope");
        expect(scope.style.getPropertyValue("--rico-fg-1")).toBe("#EFE7D6");
        expect(scope.style.getPropertyValue("--rico-primary")).toBe("#E0895A");
    });

    it("is a pass-through for the public surface", () => {
        render(
            <AtelierMarkdownScope authenticated={false}>
                <p>md</p>
            </AtelierMarkdownScope>,
        );
        expect(screen.queryByTestId("atelier-markdown-scope")).toBeNull();
    });
});

describe("CommandEmptyState — Atelier surface", () => {
    it("hero renders mark, serif title, subtitle, and working chips", () => {
        render(
            <CommandEmptyState
                authenticated
                variant="hero"
                title="What can Rico do for you?"
                subtitle="Search, track, and prepare."
                actions={ACTIONS}
                disabled={false}
            />,
        );
        expect(screen.getByTestId("atelier-empty-hero")).toBeTruthy();
        expect(screen.getByTestId("atelier-rico-mark")).toBeTruthy();
        expect(screen.getByText("What can Rico do for you?")).toBeTruthy();
        expect(screen.getByText("Search, track, and prepare.")).toBeTruthy();
        const chips = screen.getAllByTestId("atelier-quick-chip");
        expect(chips).toHaveLength(2);
        chips[0].click();
        expect(ACTIONS[0].onClick).toHaveBeenCalledTimes(1);
    });

    it("chips variant renders chips only and respects disabled", () => {
        const onClick = vi.fn();
        render(
            <CommandEmptyState
                authenticated
                variant="chips"
                title="t"
                subtitle="s"
                actions={[{ key: "x", label: "Chip", icon: <svg />, onClick }]}
                disabled
            />,
        );
        expect(screen.getByTestId("atelier-empty-chips")).toBeTruthy();
        expect(screen.queryByTestId("atelier-empty-hero")).toBeNull();
        const chip = screen.getByTestId("atelier-quick-chip") as HTMLButtonElement;
        expect(chip.disabled).toBe(true);
        chip.click();
        expect(onClick).not.toHaveBeenCalled();
    });

    it("renders an optional category hint above the label, without changing the click contract", () => {
        const onClick = vi.fn();
        render(
            <CommandEmptyState
                authenticated
                variant="chips"
                title="t"
                subtitle="s"
                actions={[{ key: "x", label: "Find UAE jobs", hint: "Search", icon: <svg />, onClick }]}
                disabled={false}
            />,
        );
        expect(screen.getByText("Search")).toBeTruthy();
        expect(screen.getByText("Find UAE jobs")).toBeTruthy();
        screen.getByTestId("atelier-quick-chip").click();
        expect(onClick).toHaveBeenCalledTimes(1);
    });

    it("omits the hint row entirely when not provided (unchanged layout)", () => {
        render(
            <CommandEmptyState
                authenticated
                variant="chips"
                title="t"
                subtitle="s"
                actions={ACTIONS}
                disabled={false}
            />,
        );
        const chip = screen.getAllByTestId("atelier-quick-chip")[0];
        expect(chip.querySelector(".atl-chip-hint")).toBeNull();
    });

    it("public hero keeps the pre-4b classes", () => {
        const { container } = render(
            <CommandEmptyState
                authenticated={false}
                variant="hero"
                title="t"
                subtitle="s"
                actions={ACTIONS}
                disabled={false}
            />,
        );
        expect(container.querySelector(".rico-orb")).not.toBeNull();
        expect(container.querySelector(".bg-surface-glass")).not.toBeNull();
        expect(screen.queryByTestId("atelier-empty-hero")).toBeNull();
    });
});
