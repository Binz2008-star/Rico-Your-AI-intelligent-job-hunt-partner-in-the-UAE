/**
 * Official-site opening film — owner decision 2026-07-14.
 *
 * Contract:
 *   1. Guest, first open this session → hand off to /explainer (random film
 *      pick happens inside /explainer/index.html), session flag set, landing
 *      not shown (near-black cover instead).
 *   2. Guest, same-session return → landing renders, no film hand-off (no loop).
 *   3. Authenticated user → router.replace("/command") verbatim; no film.
 *   4. Auth not resolved yet → landing renders, nothing fires.
 *
 * claimOpeningFilm runs REAL against jsdom sessionStorage; only the
 * navigation side effect (goToOpeningFilm) is mocked.
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
import { OPENING_FILM_SESSION_FLAG } from "@/lib/openingFilm";

beforeEach(() => {
    window.sessionStorage.clear();
    authState.current = { user: null, ready: false };
});
afterEach(() => {
    vi.clearAllMocks();
});

describe("official-site opening film", () => {
    it("guest first open → film hand-off, flag set, landing hidden", async () => {
        authState.current = { user: null, ready: true };
        render(<HomePage />);

        await waitFor(() => expect(goToFilm).toHaveBeenCalledTimes(1));
        expect(window.sessionStorage.getItem(OPENING_FILM_SESSION_FLAG)).toBe("1");
        expect(screen.queryByTestId("landing-v2")).toBeNull();
        expect(routerReplace).not.toHaveBeenCalled();
    });

    it("guest same-session return → landing renders, no second hand-off (no loop)", async () => {
        window.sessionStorage.setItem(OPENING_FILM_SESSION_FLAG, "1");
        authState.current = { user: null, ready: true };
        render(<HomePage />);

        expect(await screen.findByTestId("landing-v2")).toBeInTheDocument();
        expect(goToFilm).not.toHaveBeenCalled();
        expect(routerReplace).not.toHaveBeenCalled();
    });

    it("authenticated user → /command verbatim, never the film", async () => {
        authState.current = { user: { email: "u@rico.ai" }, ready: true };
        render(<HomePage />);

        await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/command"));
        expect(goToFilm).not.toHaveBeenCalled();
        // The flag stays unclaimed — a same-session logout landing on "/" may
        // still get the opening film once.
        expect(window.sessionStorage.getItem(OPENING_FILM_SESSION_FLAG)).toBeNull();
    });

    it("auth unresolved → landing renders, nothing fires yet", () => {
        authState.current = { user: null, ready: false };
        render(<HomePage />);

        expect(screen.getByTestId("landing-v2")).toBeInTheDocument();
        expect(goToFilm).not.toHaveBeenCalled();
        expect(routerReplace).not.toHaveBeenCalled();
        expect(window.sessionStorage.getItem(OPENING_FILM_SESSION_FLAG)).toBeNull();
    });
});
