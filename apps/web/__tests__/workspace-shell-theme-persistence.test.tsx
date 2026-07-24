/**
 * WorkspaceShell dark/light persistence.
 *
 * Reported bug: choosing dark, then navigating between routes/tabs (any
 * remount of WorkspaceShell), silently reverted to light. Root cause: the
 * toggle was plain `useState(defaultDark)` with no persistence at all, so a
 * fresh mount always fell back to whatever the current route hardcodes as
 * its default — discarding the user's own explicit choice.
 *
 * Fix: the choice is now persisted to localStorage (one shared key, mirroring
 * LanguageContext's pattern) and re-applied on mount, overriding the route's
 * default once the user has ever toggled it.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders as render } from "./test-utils";

vi.mock("next/navigation", () => ({
    usePathname: () => "/applications",
}));
vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: any) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";

const fetchMock = vi.fn(async () => ({ ok: false, status: 401, json: async () => ({}) }));

beforeEach(() => {
    fetchMock.mockClear();
    vi.stubGlobal("fetch", fetchMock);
    localStorage.clear();
});

function renderShell() {
    return render(
        <WorkspaceShell>
            <div data-testid="sample-child">sample</div>
        </WorkspaceShell>,
    );
}

describe("WorkspaceShell — dark/light theme persistence", () => {
    it("choosing dark, then remounting (simulating a route/tab switch), stays dark", async () => {
        const user = userEvent.setup();
        const first = renderShell();

        const toggle = screen.getAllByRole("button", { name: /dark mode/i })[0];
        await user.click(toggle);
        // Button label flips once the island is dark.
        await waitFor(() => {
            expect(screen.getAllByRole("button", { name: /light mode/i }).length).toBeGreaterThan(0);
        });

        // Simulate navigating away and back — a real remount, not just a re-render.
        first.unmount();
        renderShell();

        await waitFor(() => {
            expect(screen.getAllByRole("button", { name: /light mode/i }).length).toBeGreaterThan(0);
        });
    });

    it("persists across three consecutive remounts (repeated tab switching)", async () => {
        const user = userEvent.setup();
        const r1 = renderShell();
        await user.click(screen.getAllByRole("button", { name: /dark mode/i })[0]);
        await waitFor(() => {
            expect(screen.getAllByRole("button", { name: /light mode/i }).length).toBeGreaterThan(0);
        });
        r1.unmount();

        const r2 = renderShell();
        await waitFor(() => {
            expect(screen.getAllByRole("button", { name: /light mode/i }).length).toBeGreaterThan(0);
        });
        r2.unmount();

        renderShell();
        await waitFor(() => {
            expect(screen.getAllByRole("button", { name: /light mode/i }).length).toBeGreaterThan(0);
        });
    });

    it("with no stored preference, a fresh mount still uses the route's own default (light)", () => {
        renderShell();
        expect(screen.getAllByRole("button", { name: /dark mode/i }).length).toBeGreaterThan(0);
    });

    it("choosing light again persists too — round-trip, not a one-way ratchet", async () => {
        const user = userEvent.setup();
        const r1 = renderShell();
        await user.click(screen.getAllByRole("button", { name: /dark mode/i })[0]);
        await waitFor(() => {
            expect(screen.getAllByRole("button", { name: /light mode/i }).length).toBeGreaterThan(0);
        });
        await user.click(screen.getAllByRole("button", { name: /light mode/i })[0]);
        await waitFor(() => {
            expect(screen.getAllByRole("button", { name: /dark mode/i }).length).toBeGreaterThan(0);
        });
        r1.unmount();

        renderShell();
        await waitFor(() => {
            expect(screen.getAllByRole("button", { name: /dark mode/i }).length).toBeGreaterThan(0);
        });
    });
});
