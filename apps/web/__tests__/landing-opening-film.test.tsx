/**
 * Official-site opening film — owner directive 2026-07-16.
 *
 * Contract:
 *   1. Guest visit → hand off to the film chooser (/explainer/index.html),
 *      landing not shown (near-black cover instead).
 *   2. EVERY guest visit hands off — repeated visits in the same browser
 *      session go back through the chooser (no once-per-session gate).
 *      The non-repeating film rotation itself lives in the chooser and is
 *      covered by explainer-film-rotation.test.ts.
 *   3. Authenticated user → router.replace("/command") verbatim; no film.
 *   4. Auth not resolved yet → landing renders, nothing fires.
 *
 * Only the navigation side effect (goToOpeningFilm) is mocked.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { routerReplace, goToFilm } = vi.hoisted(() => ({
    routerReplace: vi.fn(),
    goToFilm: vi.fn(),
}));
const authState = vi.hoisted(() => ({
    current: { user: null as unknown, ready: false },
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace: routerReplace, push: vi.fn(), prefetch: vi.fn() }),
    usePathname: () => "/",
}));
vi.mock("@/hooks/useAuth", () => ({
    useAuth: () => authState.current,
}));
vi.mock("@/components/LandingPageV2", () => ({
    default: () => <div data-testid="landing-v2" />,
}));
vi.mock("@/lib/openingFilm", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/openingFilm")>();
    return { ...actual, goToOpeningFilm: goToFilm };
});

import HomePage from "@/app/page";

beforeEach(() => {
    window.sessionStorage.clear();
    authState.current = { user: null, ready: false };
});
afterEach(() => {
    vi.clearAllMocks();
});

describe("official-site opening film", () => {
    it("guest visit → film hand-off, landing hidden", async () => {
        authState.current = { user: null, ready: true };
        render(<HomePage />);

        await waitFor(() => expect(goToFilm).toHaveBeenCalled());
        expect(screen.queryByTestId("landing-v2")).toBeNull();
        expect(routerReplace).not.toHaveBeenCalled();
    });

    it("repeated guest visits → chooser runs every time, not once per session", async () => {
        authState.current = { user: null, ready: true };

        const first = render(<HomePage />);
        await waitFor(() => expect(goToFilm).toHaveBeenCalled());
        const callsAfterFirstVisit = goToFilm.mock.calls.length;
        first.unmount();

        // Second visit in the same browser session (same storage state).
        render(<HomePage />);
        await waitFor(() =>
            expect(goToFilm.mock.calls.length).toBeGreaterThan(callsAfterFirstVisit),
        );
        expect(screen.queryByTestId("landing-v2")).toBeNull();
        expect(routerReplace).not.toHaveBeenCalled();
    });

    it("legacy once-per-session flag in storage no longer blocks the hand-off", async () => {
        // Visitors from before this fix still carry the old flag; it must be inert.
        window.sessionStorage.setItem("rico-opening-film-shown", "1");
        authState.current = { user: null, ready: true };
        render(<HomePage />);

        await waitFor(() => expect(goToFilm).toHaveBeenCalled());
        expect(screen.queryByTestId("landing-v2")).toBeNull();
    });

    it("authenticated user → /command verbatim, never the film", async () => {
        authState.current = { user: { email: "u@rico.ai" }, ready: true };
        render(<HomePage />);

        await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/command"));
        expect(goToFilm).not.toHaveBeenCalled();
    });

    it("auth unresolved → landing renders, nothing fires yet", () => {
        authState.current = { user: null, ready: false };
        render(<HomePage />);

        expect(screen.getByTestId("landing-v2")).toBeInTheDocument();
        expect(goToFilm).not.toHaveBeenCalled();
        expect(routerReplace).not.toHaveBeenCalled();
    });
});
