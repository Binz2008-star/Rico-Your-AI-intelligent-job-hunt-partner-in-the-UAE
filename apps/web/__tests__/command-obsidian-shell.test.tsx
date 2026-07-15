/**
 * CommandObsidianShell — slice C1 unit contracts.
 *
 *  1. Dark "Obsidian night" default: shell reports dark mode and provides the
 *     COMMAND_OBSIDIAN.dark palette through WorkspaceThemeContext (accent slot
 *     carries the acid-lime sun `#c8ff3f`), so 4a–4e children repaint with no
 *     component changes.
 *  2. Top bar: brand, workspace eyebrow, live status (READY idle / WORKING
 *     while busy), panel toggles wired to the callbacks.
 *  3. Compact top-bar nav: shared WORKSPACE_NAV links render as icon links
 *     (general navigation does NOT occupy the Sessions rail position — owner
 *     correction 2026-07-16); /command is current page. The start rail renders
 *     the injected `leftRail` content; leftOpen=false collapses its width.
 *  4. Theme toggle flips to the light "Obsidian at dawn" palette.
 *  5. Arabic: dir=rtl + lang=ar on the root.
 *  6. Route-scoping: no global body/root mutation — canvas layers live inside
 *     the shell subtree.
 */

import { CommandObsidianShell } from "@/components/command/CommandObsidianShell";
import { COMMAND_OBSIDIAN } from "@/components/command/obsidianTheme";
import { useWorkspaceTheme } from "@/components/workspace/theme";
import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
    usePathname: () => "/command",
}));
vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: any) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

const setLanguage = vi.fn();
let mockLanguage = "en";
vi.mock("@/contexts/LanguageContext", () => ({
    useLanguage: () => ({ language: mockLanguage, setLanguage }),
}));

function PaletteProbe() {
    const c = useWorkspaceTheme();
    return <span data-testid="palette-probe" data-accent={c.red} data-bg={c.bg} />;
}

beforeEach(() => {
    mockLanguage = "en";
    setLanguage.mockReset();
});

describe("CommandObsidianShell (slice C1)", () => {
    it("defaults to Obsidian night and provides the obsidian palette to children", () => {
        render(
            <CommandObsidianShell>
                <PaletteProbe />
            </CommandObsidianShell>,
        );
        expect(screen.getByTestId("command-obsidian-shell")).toHaveAttribute("data-obsidian-mode", "dark");
        const probe = screen.getByTestId("palette-probe");
        expect(probe).toHaveAttribute("data-accent", COMMAND_OBSIDIAN.dark.red); // #c8ff3f
        expect(probe).toHaveAttribute("data-bg", COMMAND_OBSIDIAN.dark.bg); // #0a0b0d
    });

    it("shows the idle status when not busy and the working status while busy", () => {
        const { rerender } = render(<CommandObsidianShell busy={false}>x</CommandObsidianShell>);
        expect(screen.getByTestId("command-obsidian-status")).toHaveTextContent(/ready/i);
        rerender(<CommandObsidianShell busy>x</CommandObsidianShell>);
        expect(screen.getByTestId("command-obsidian-status")).toHaveTextContent(/rico is working/i);
    });

    it("wires the panel toggles and collapses the nav rail when leftOpen=false", () => {
        const onToggleLeft = vi.fn();
        const onToggleRight = vi.fn();
        const { rerender } = render(
            <CommandObsidianShell leftOpen rightOpen onToggleLeft={onToggleLeft} onToggleRight={onToggleRight}>
                x
            </CommandObsidianShell>,
        );
        fireEvent.click(screen.getByLabelText("Toggle sessions rail"));
        fireEvent.click(screen.getByLabelText("Toggle shortlist rail"));
        expect(onToggleLeft).toHaveBeenCalledTimes(1);
        expect(onToggleRight).toHaveBeenCalledTimes(1);

        expect(screen.getByTestId("command-obsidian-leftrail").className).toContain("lg:w-[260px]");
        rerender(
            <CommandObsidianShell leftOpen={false} rightOpen onToggleLeft={onToggleLeft} onToggleRight={onToggleRight}>
                x
            </CommandObsidianShell>,
        );
        expect(screen.getByTestId("command-obsidian-leftrail").className).toContain("lg:w-0");
    });

    it("renders the shared workspace nav as compact top-bar icons, /command current", () => {
        render(<CommandObsidianShell>x</CommandObsidianShell>);
        const topnav = screen.getByTestId("command-obsidian-topnav");
        expect(topnav).toBeInTheDocument();
        const command = screen.getByRole("link", { name: /command/i });
        expect(command).toHaveAttribute("aria-current", "page");
        expect(topnav).toContainElement(command);
        expect(screen.getByRole("link", { name: /profile/i })).toHaveAttribute("href", "/profile");
        expect(screen.getByRole("link", { name: /applications/i })).toHaveAttribute("href", "/applications");
        expect(screen.getByRole("link", { name: /settings/i })).toHaveAttribute("href", "/settings");
    });

    it("renders the injected leftRail content in the Sessions rail position", () => {
        render(
            <CommandObsidianShell leftRail={<div data-testid="sessions-probe">sessions</div>}>
                x
            </CommandObsidianShell>,
        );
        expect(screen.getByTestId("command-obsidian-leftrail")).toContainElement(
            screen.getByTestId("sessions-probe"),
        );
    });

    it("theme toggle flips to the light 'Obsidian at dawn' palette", () => {
        render(
            <CommandObsidianShell>
                <PaletteProbe />
            </CommandObsidianShell>,
        );
        fireEvent.click(screen.getByLabelText("Light mode"));
        expect(screen.getByTestId("command-obsidian-shell")).toHaveAttribute("data-obsidian-mode", "light");
        expect(screen.getByTestId("palette-probe")).toHaveAttribute("data-accent", COMMAND_OBSIDIAN.light.red);
    });

    it("mirrors Arabic onto the root (dir=rtl, lang=ar)", () => {
        mockLanguage = "ar";
        render(<CommandObsidianShell>x</CommandObsidianShell>);
        const root = screen.getByTestId("command-obsidian-shell");
        expect(root).toHaveAttribute("dir", "rtl");
        expect(root).toHaveAttribute("lang", "ar");
    });

    it("does not mutate global body/root styling (route-scoped canvas only)", () => {
        render(<CommandObsidianShell>x</CommandObsidianShell>);
        expect(document.body.getAttribute("style")).toBeNull();
        expect(document.documentElement.getAttribute("style")).toBeNull();
    });
});
