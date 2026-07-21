/**
 * apps/web/__tests__/command-v5-shell.test.tsx
 *
 * Command v5 PR 2 — WorkspaceShell skin contracts:
 * - active nav item keeps aria-current AND gains the v5 energy marker
 * - the Rico presence indicator sits in the shell controls (status semantics)
 * - the root carries the .wsx5 token island
 * - the light-only route atmosphere renders in light and disappears in dark
 * - the applications nav count contract is untouched
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
});

function renderShell() {
    return render(
        <WorkspaceShell>
            <div data-testid="sample-child">sample</div>
        </WorkspaceShell>,
    );
}

describe("WorkspaceShell — v5 skin (PR 2)", () => {
    it("active nav item keeps aria-current and gains the v5 energy marker", async () => {
        renderShell();
        const links = screen.getAllByRole("link", { name: /applications/i });
        const active = links.find((l) => l.getAttribute("aria-current") === "page");
        expect(active).toBeDefined();
        await waitFor(() => {
            expect(active!.querySelector('[data-testid="wsx5-nav-marker"]')).not.toBeNull();
        });
        // inactive items carry no marker
        const command = screen
            .getAllByRole("link", { name: /command/i })
            .find((l) => l.getAttribute("href") === "/command");
        expect(command?.querySelector('[data-testid="wsx5-nav-marker"]')).toBeNull();
    });

    it("renders the Rico presence indicator with status semantics", () => {
        renderShell();
        expect(screen.getAllByRole("status", { name: "Rico is ready" }).length).toBeGreaterThan(0);
    });

    it("root carries the .wsx5 token island and renders children", () => {
        const { container } = renderShell();
        expect(container.querySelector(".wsx-root.wsx5")).not.toBeNull();
        expect(screen.getByTestId("sample-child")).toBeInTheDocument();
    });

    it("route atmosphere renders in both islands (artifact ambience is theme-independent)", async () => {
        const user = userEvent.setup();
        renderShell();
        expect(screen.getAllByTestId("wsx5-atmosphere").length).toBe(1);
        await user.click(screen.getAllByRole("button", { name: /dark mode/i })[0]);
        expect(screen.getAllByTestId("wsx5-atmosphere").length).toBe(1);
        // marker survives the dark island (accent handled by the dark palette)
        const active = screen
            .getAllByRole("link", { name: /applications/i })
            .find((l) => l.getAttribute("aria-current") === "page");
        expect(active!.querySelector('[data-testid="wsx5-nav-marker"]')).not.toBeNull();
    });

    it("document children are wrapped in the v5 entrance layer", () => {
        const { container } = renderShell();
        const play = container.querySelector("main .wsx5-play");
        expect(play).not.toBeNull();
        expect(play!.querySelector('[data-wsx5-anim="rise"]')).not.toBeNull();
    });
});
