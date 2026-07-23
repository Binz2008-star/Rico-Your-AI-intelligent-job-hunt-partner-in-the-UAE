/**
 * TASK-20260723-002 — Medium Workspace Layout.
 *
 * Covers the new pieces added to preserve /command's Career Workspace
 * identity at 768–1199px: the CommandWorkspaceDrawer primitive, the compact
 * (icon/initial) Sessions rail, CommandRail's "bare" embedding mode, and
 * CommandObsidianShell's new drawer triggers/wiring. The ≥1200px and <768px
 * tiers are covered by the existing, unmodified
 * command-obsidian-noregression.test.tsx / command-workspace-shell.test.tsx
 * suites (re-run and passing, not touched here).
 */

import { CommandConversationRail } from "@/components/command/CommandConversationRail";
import { CommandObsidianShell } from "@/components/command/CommandObsidianShell";
import { CommandRail } from "@/components/command/CommandRail";
import { CommandWorkspaceDrawer } from "@/components/command/CommandWorkspaceDrawer";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React, { useRef } from "react";
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

beforeEach(() => {
    mockLanguage = "en";
    setLanguage.mockReset();
});

/* ── CommandWorkspaceDrawer (the shared accessible primitive) ────────────── */

function DrawerHarness({ initialOpen = true }: { initialOpen?: boolean }) {
    const [open, setOpen] = React.useState(initialOpen);
    const triggerRef = useRef<HTMLButtonElement>(null);
    return (
        <div>
            <button ref={triggerRef} type="button" onClick={() => setOpen(true)}>
                open drawer
            </button>
            <CommandWorkspaceDrawer
                open={open}
                onClose={() => setOpen(false)}
                titleId="test-drawer-title"
                title="Test Drawer"
                side="start"
                triggerRef={triggerRef}
                testId="test-drawer"
            >
                <button type="button">inner action</button>
            </CommandWorkspaceDrawer>
        </div>
    );
}

describe("CommandWorkspaceDrawer", () => {
    it("renders nothing when closed", () => {
        render(<DrawerHarness initialOpen={false} />);
        expect(screen.queryByTestId("test-drawer")).not.toBeInTheDocument();
    });

    it("has correct dialog semantics and real content when open", () => {
        render(<DrawerHarness initialOpen />);
        const panel = screen.getByTestId("test-drawer");
        expect(panel).toHaveAttribute("role", "dialog");
        expect(panel).toHaveAttribute("aria-modal", "true");
        expect(panel).toHaveAttribute("aria-labelledby", "test-drawer-title");
        expect(panel).toHaveAttribute("id", "test-drawer");
        expect(screen.getByText("inner action")).toBeInTheDocument();
    });

    it("Escape closes the drawer", () => {
        render(<DrawerHarness initialOpen />);
        expect(screen.getByTestId("test-drawer")).toBeInTheDocument();
        fireEvent.keyDown(document, { key: "Escape" });
        expect(screen.queryByTestId("test-drawer")).not.toBeInTheDocument();
    });

    it("backdrop click closes the drawer", () => {
        render(<DrawerHarness initialOpen />);
        fireEvent.click(screen.getByTestId("test-drawer-backdrop"));
        expect(screen.queryByTestId("test-drawer")).not.toBeInTheDocument();
    });

    it("the explicit close button closes the drawer", () => {
        render(<DrawerHarness initialOpen />);
        fireEvent.click(screen.getByTestId("test-drawer-close"));
        expect(screen.queryByTestId("test-drawer")).not.toBeInTheDocument();
    });

    it("focus returns to the trigger element when the drawer closes", async () => {
        render(<DrawerHarness initialOpen />);
        fireEvent.keyDown(document, { key: "Escape" });
        await waitFor(() => expect(screen.getByRole("button", { name: "open drawer" })).toHaveFocus());
    });

    it("anchors to the logical start or end side", () => {
        const { rerender } = render(<DrawerHarness initialOpen />);
        expect(screen.getByTestId("test-drawer").className).toMatch(/\bstart-0\b/);

        function EndHarness() {
            const triggerRef = useRef<HTMLButtonElement>(null);
            return (
                <div>
                    <button ref={triggerRef} type="button">trigger</button>
                    <CommandWorkspaceDrawer
                        open
                        onClose={() => {}}
                        titleId="end-title"
                        title="End Drawer"
                        side="end"
                        triggerRef={triggerRef}
                        testId="end-drawer"
                    >
                        content
                    </CommandWorkspaceDrawer>
                </div>
            );
        }
        rerender(<EndHarness />);
        expect(screen.getByTestId("end-drawer").className).toMatch(/\bend-0\b/);
    });

    it("respects reduced motion via the shared entrance-animation utility", () => {
        render(<DrawerHarness initialOpen />);
        // Same already-shipped, already reduced-motion-safe utility used by
        // CommandObsidianShell's account menu — not a new animation system.
        expect(screen.getByTestId("test-drawer").className).toMatch(/animate-fade-in-scale/);
        expect(screen.getByTestId("test-drawer").className).toMatch(/motion-reduce:animate-none/);
    });
});

/* ── CommandConversationRail — compact (900–1199px) variant ─────────────── */

const railBaseProps = {
    audience: "authenticated" as const,
    messages: [{ role: "user" as const, text: "Find me jobs" }],
    historyState: "has_history" as const,
    historyLoadError: false,
    busy: false,
    confirmClear: false,
    clearingHistory: false,
    onNewChat: vi.fn(),
    onClearHistory: vi.fn(),
    onCancelClear: vi.fn(),
};

describe("CommandConversationRail — compact variant", () => {
    it("renders a distinguishable initial, active marker, tooltip, and accessible name per session (never an anonymous dot)", () => {
        const onSelectSession = vi.fn();
        render(
            <CommandConversationRail
                {...railBaseProps}
                variant="compact"
                multiSession
                sessions={[
                    { id: "s1", title: "Find UAE jobs", userTurns: 2 },
                    { id: "s2", title: "Resume review", userTurns: 4 },
                ]}
                activeSessionId="s1"
                onSelectSession={onSelectSession}
            />,
        );
        const current = screen.getByTestId("command-rail-current-compact");
        expect(current).toHaveTextContent("F"); // derived initial, not a dot
        expect(current).toHaveAttribute("aria-current", "true");

        const other = screen.getByTestId("command-rail-session-compact");
        expect(other).toHaveTextContent("R");
        expect(other).toHaveAttribute("title", "Resume review"); // native tooltip
        expect(other).toHaveAttribute("aria-label", expect.stringContaining("Resume review")); // full real name, not icon-only

        fireEvent.click(other);
        expect(onSelectSession).toHaveBeenCalledWith("s2");
    });

    it("root is the compact ~64-80px column, not a shrunk copy of the full list", () => {
        render(<CommandConversationRail {...railBaseProps} variant="compact" />);
        const root = screen.getByTestId("command-conversation-rail-compact");
        expect(root.className).toMatch(/\bw-20\b/); // 80px — within the 64–80px target
        expect(screen.queryByTestId("command-conversation-rail")).not.toBeInTheDocument();
        expect(screen.queryByText("Sessions")).not.toBeInTheDocument(); // no text header at this width
    });

    it("the compact new-chat control is keyboard accessible and calls the real handler", () => {
        const onNewChat = vi.fn();
        render(<CommandConversationRail {...railBaseProps} variant="compact" onNewChat={onNewChat} />);
        const btn = screen.getByTestId("command-rail-new-chat-compact");
        expect(btn.tagName).toBe("BUTTON");
        fireEvent.click(btn);
        expect(onNewChat).toHaveBeenCalledTimes(1);
    });

    it("full variant is unchanged: still renders the text header and full session list", () => {
        render(<CommandConversationRail {...railBaseProps} variant="full" />);
        expect(screen.getByTestId("command-conversation-rail")).toBeInTheDocument();
        expect(screen.getByText("Sessions")).toBeInTheDocument();
    });
});

/* ── CommandRail — "bare" embedding mode for the Career-context drawer ───── */

describe("CommandRail — bare variant", () => {
    const picks = [{ title: "Senior Accountant", company: "Atelier Co", location: "Dubai", score: 0.92 }];
    const pipeline = [{ key: "p1", company: "Atelier Co", title: "Senior Accountant", statusLabel: "APPLIED" }];

    it("renders the same real Shortlist/Pipeline data without the outer aside chrome", () => {
        render(<CommandRail authenticated picks={picks} pipeline={pipeline} variant="bare" />);
        expect(screen.queryByTestId("command-rail")).not.toBeInTheDocument(); // no outer <aside> in bare mode
        expect(screen.getByTestId("command-rail-content")).toBeInTheDocument();
        expect(screen.getAllByText("Atelier Co").length).toBe(2); // once in Shortlist pick, once in Pipeline row
        expect(screen.getByTestId("command-rail-score")).toHaveTextContent("92%");
        expect(screen.getByText("APPLIED")).toBeInTheDocument();
        expect(screen.getByTestId("command-rail-applications-link")).toBeInTheDocument();
    });

    it("aside variant (default) is unchanged", () => {
        render(<CommandRail authenticated picks={picks} pipeline={pipeline} />);
        expect(screen.getByTestId("command-rail")).toBeInTheDocument();
        expect(screen.getByTestId("command-rail-content")).toBeInTheDocument();
    });
});

/* ── CommandObsidianShell — drawer triggers, wiring, RTL ─────────────────── */

describe("CommandObsidianShell — medium-workspace drawer wiring", () => {
    it("does not render drawer triggers when no toggle handler is passed (back-compat)", () => {
        render(<CommandObsidianShell>x</CommandObsidianShell>);
        expect(screen.queryByTestId("command-sessions-drawer-trigger")).not.toBeInTheDocument();
        expect(screen.queryByTestId("command-career-drawer-trigger")).not.toBeInTheDocument();
    });

    it("Sessions drawer trigger exposes aria-expanded/aria-controls and opens real Sessions content", () => {
        const onToggleSessionsDrawer = vi.fn();
        const { rerender } = render(
            <CommandObsidianShell
                onToggleSessionsDrawer={onToggleSessionsDrawer}
                sessionsDrawerOpen={false}
                sessionsDrawerContent={<div>real sessions content</div>}
            >
                x
            </CommandObsidianShell>,
        );
        const trigger = screen.getByTestId("command-sessions-drawer-trigger");
        expect(trigger).toHaveAttribute("aria-expanded", "false");
        expect(trigger).toHaveAttribute("aria-controls", "command-sessions-drawer");
        expect(screen.queryByText("real sessions content")).not.toBeInTheDocument();

        fireEvent.click(trigger);
        expect(onToggleSessionsDrawer).toHaveBeenCalledTimes(1);

        rerender(
            <CommandObsidianShell
                onToggleSessionsDrawer={onToggleSessionsDrawer}
                sessionsDrawerOpen
                sessionsDrawerContent={<div>real sessions content</div>}
            >
                x
            </CommandObsidianShell>,
        );
        expect(screen.getByText("real sessions content")).toBeInTheDocument();
        expect(screen.getByTestId("command-sessions-drawer")).toHaveAttribute("id", "command-sessions-drawer");
    });

    it("Career-context drawer trigger exposes aria-expanded/aria-controls and opens real career-context content", () => {
        const onToggleCareerDrawer = vi.fn();
        const { rerender } = render(
            <CommandObsidianShell
                onToggleCareerDrawer={onToggleCareerDrawer}
                careerDrawerOpen={false}
                careerContextDrawerContent={<div>real shortlist content</div>}
            >
                x
            </CommandObsidianShell>,
        );
        const trigger = screen.getByTestId("command-career-drawer-trigger");
        expect(trigger).toHaveAttribute("aria-expanded", "false");
        expect(trigger).toHaveAttribute("aria-controls", "command-career-context-drawer");

        fireEvent.click(trigger);
        expect(onToggleCareerDrawer).toHaveBeenCalledTimes(1);

        rerender(
            <CommandObsidianShell
                onToggleCareerDrawer={onToggleCareerDrawer}
                careerDrawerOpen
                careerContextDrawerContent={<div>real shortlist content</div>}
            >
                x
            </CommandObsidianShell>,
        );
        expect(screen.getByText("real shortlist content")).toBeInTheDocument();
    });

    it("renders the compact-rail wrapper content when provided", () => {
        render(
            <CommandObsidianShell leftRailCompact={<div>compact rail content</div>}>
                x
            </CommandObsidianShell>,
        );
        expect(screen.getByText("compact rail content")).toBeInTheDocument();
        expect(screen.getByTestId("command-obsidian-leftrail-compact").className).toMatch(/\bw-20\b/);
    });

    it("the ≥1200px collapse toggles are scoped to min-[1200px], not always-flex", () => {
        render(<CommandObsidianShell onToggleLeft={() => {}} onToggleRight={() => {}}>x</CommandObsidianShell>);
        const leftToggle = screen.getByLabelText("Toggle sessions rail");
        const rightToggle = screen.getByLabelText("Toggle shortlist rail");
        expect(leftToggle.className).toMatch(/\bhidden\b/);
        expect(leftToggle.className).toMatch(/min-\[1200px\]:flex/);
        expect(rightToggle.className).toMatch(/\bhidden\b/);
        expect(rightToggle.className).toMatch(/min-\[1200px\]:flex/);
    });

    it("Sessions drawer anchors start, Career-context drawer anchors end, in both languages (logical properties, no hardcoded left/right)", () => {
        for (const lang of ["en", "ar"] as const) {
            mockLanguage = lang;
            const { unmount } = render(
                <CommandObsidianShell
                    onToggleSessionsDrawer={() => {}}
                    sessionsDrawerOpen
                    sessionsDrawerContent={<div>sessions</div>}
                    onToggleCareerDrawer={() => {}}
                    careerDrawerOpen
                    careerContextDrawerContent={<div>career</div>}
                >
                    x
                </CommandObsidianShell>,
            );
            expect(screen.getByTestId("command-sessions-drawer").className).toMatch(/\bstart-0\b/);
            expect(screen.getByTestId("command-career-context-drawer").className).toMatch(/\bend-0\b/);
            unmount();
        }
        mockLanguage = "en";
    });
});
