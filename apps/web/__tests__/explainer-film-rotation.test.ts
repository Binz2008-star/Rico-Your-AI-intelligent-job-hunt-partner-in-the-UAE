/**
 * Explainer film rotation — owner directive 2026-07-16.
 *
 * Contract (public/explainer/index.html, the chooser):
 *   1. Rotates exactly option-2 / option-3 / option-3b.
 *   2. Randomized non-repeating cycle: all three films appear before any
 *      film repeats; a fresh cycle never opens with the film that closed
 *      the previous one (reload ≠ replay).
 *   3. The rotation persists in localStorage so it spans visits/reloads;
 *      corrupted or unavailable storage degrades to a valid random pick.
 *   4. The film renders in place (document.write) so the URL stays on the
 *      chooser; a hard redirect is only the fetch-failure fallback.
 *
 * These tests execute the REAL inline script shipped in index.html — the
 * script exports its internals on `window.__ricoFilmChooser` and skips its
 * boot when the window has no document (the harness case).
 */

import { existsSync, readFileSync } from "fs";
import { resolve } from "path";
import { describe, expect, it, vi } from "vitest";

const EXPLAINER_DIR = resolve(__dirname, "../public/explainer");
const CHOOSER_HTML = readFileSync(resolve(EXPLAINER_DIR, "index.html"), "utf8");

const REQUIRED_FILMS = [
    "/explainer/option-2.html",
    "/explainer/option-3.html",
    "/explainer/option-3b.html",
];

type StorageLike = { getItem(k: string): string | null; setItem(k: string, v: string): void };
type Chooser = {
    FILMS: string[];
    nextFilm(storage: StorageLike | null, random: () => number): string;
    showFilm(win: unknown, url: string): void;
};

function loadChooser(): Chooser {
    const match = /<script>([\s\S]*?)<\/script>/.exec(CHOOSER_HTML);
    if (!match) throw new Error("chooser inline script not found in index.html");
    // No `document` on the fake window → the script exports but does not boot.
    const fakeWin: Record<string, unknown> = {};
    new Function("window", match[1])(fakeWin);
    return fakeWin.__ricoFilmChooser as Chooser;
}

function memoryStorage(): StorageLike & { map: Map<string, string> } {
    const map = new Map<string, string>();
    return {
        map,
        getItem: (k) => (map.has(k) ? (map.get(k) as string) : null),
        setItem: (k, v) => void map.set(k, String(v)),
    };
}

const sorted = (a: string[]) => [...a].sort();

describe("explainer film chooser — rotation set", () => {
    it("rotates exactly option-2, option-3, option-3b", () => {
        const { FILMS } = loadChooser();
        expect(sorted(FILMS)).toEqual(sorted(REQUIRED_FILMS));
    });

    it("every rotation target exists as a real film file", () => {
        for (const film of REQUIRED_FILMS) {
            const file = resolve(EXPLAINER_DIR, film.replace("/explainer/", ""));
            expect(existsSync(file), `${film} missing on disk`).toBe(true);
        }
    });
});

describe("explainer film chooser — non-repeating cycle", () => {
    it("all three films appear before any repeats, across many visits", () => {
        const chooser = loadChooser();
        const storage = memoryStorage();
        const draws = Array.from({ length: 30 }, () =>
            chooser.nextFilm(storage, Math.random),
        );

        // Each block of 3 consecutive visits is a full permutation of the set.
        for (let i = 0; i < draws.length; i += 3) {
            expect(sorted(draws.slice(i, i + 3))).toEqual(sorted(REQUIRED_FILMS));
        }
    });

    it("never plays the same film twice in a row — including across cycle boundaries (reload ≠ replay)", () => {
        const chooser = loadChooser();
        const storage = memoryStorage();
        const draws = Array.from({ length: 60 }, () =>
            chooser.nextFilm(storage, Math.random),
        );

        for (let i = 1; i < draws.length; i++) {
            expect(draws[i], `visit ${i + 1} repeated visit ${i}`).not.toBe(draws[i - 1]);
        }
    });

    it("cycles are randomized, not a fixed order", () => {
        const chooser = loadChooser();
        const storage = memoryStorage();
        const cycles = new Set<string>();
        for (let i = 0; i < 60; i++) {
            const cycle = [
                chooser.nextFilm(storage, Math.random),
                chooser.nextFilm(storage, Math.random),
                chooser.nextFilm(storage, Math.random),
            ];
            cycles.add(cycle.join(">"));
        }
        // 60 shuffled cycles of 3 films collapsing to a single order would mean
        // the shuffle is broken (probability ≈ 0 for a working shuffle).
        expect(cycles.size).toBeGreaterThan(1);
    });
});

describe("explainer film chooser — storage resilience", () => {
    it("recovers from a corrupted deck and keeps the cycle guarantee", () => {
        const chooser = loadChooser();
        const storage = memoryStorage();
        storage.map.set("rico-film-deck-v1", "{not json![");

        const cycle = [
            chooser.nextFilm(storage, Math.random),
            chooser.nextFilm(storage, Math.random),
            chooser.nextFilm(storage, Math.random),
        ];
        expect(sorted(cycle)).toEqual(sorted(REQUIRED_FILMS));
    });

    it("drops retired films found in a stale persisted deck", () => {
        const chooser = loadChooser();
        const storage = memoryStorage();
        storage.map.set(
            "rico-film-deck-v1",
            JSON.stringify(["/explainer/option-1.html", "/explainer/option-4.html"]),
        );

        for (let i = 0; i < 6; i++) {
            expect(REQUIRED_FILMS).toContain(chooser.nextFilm(storage, Math.random));
        }
    });

    it("still returns a valid film when storage throws (privacy mode)", () => {
        const chooser = loadChooser();
        const broken: StorageLike = {
            getItem() { throw new Error("denied"); },
            setItem() { throw new Error("denied"); },
        };
        expect(REQUIRED_FILMS).toContain(chooser.nextFilm(broken, Math.random));
    });

    it("still returns a valid film when storage is unavailable entirely", () => {
        const chooser = loadChooser();
        expect(REQUIRED_FILMS).toContain(chooser.nextFilm(null, Math.random));
    });
});

describe("explainer film chooser — in-place render keeps the chooser URL", () => {
    it("writes the fetched film into the current document (no redirect)", async () => {
        const chooser = loadChooser();
        const doc = { open: vi.fn(), write: vi.fn(), close: vi.fn() };
        const win = {
            document: doc,
            location: { replace: vi.fn(), search: "", hash: "" },
            fetch: vi.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve("<!DOCTYPE html><html>film</html>"),
            }),
        };

        chooser.showFilm(win, "/explainer/option-3.html");
        await new Promise((r) => setTimeout(r, 0));

        expect(win.fetch).toHaveBeenCalledWith("/explainer/option-3.html", {
            credentials: "same-origin",
        });
        expect(doc.open).toHaveBeenCalled();
        expect(doc.write).toHaveBeenCalledWith("<!DOCTYPE html><html>film</html>");
        expect(doc.close).toHaveBeenCalled();
        expect(win.location.replace).not.toHaveBeenCalled();
    });

    it("falls back to a hard redirect when the film fails to load", async () => {
        const chooser = loadChooser();
        const doc = { open: vi.fn(), write: vi.fn(), close: vi.fn() };
        const win = {
            document: doc,
            location: { replace: vi.fn(), search: "?utm=x", hash: "#top" },
            fetch: vi.fn().mockResolvedValue({ ok: false, status: 404 }),
        };

        chooser.showFilm(win, "/explainer/option-2.html");
        await new Promise((r) => setTimeout(r, 0));

        expect(win.location.replace).toHaveBeenCalledWith(
            "/explainer/option-2.html?utm=x#top",
        );
        expect(doc.write).not.toHaveBeenCalled();
    });

    it("falls back to a hard redirect when fetch is unavailable", () => {
        const chooser = loadChooser();
        const win = {
            document: { open: vi.fn(), write: vi.fn(), close: vi.fn() },
            location: { replace: vi.fn(), search: "", hash: "" },
        };

        chooser.showFilm(win, "/explainer/option-3b.html");

        expect(win.location.replace).toHaveBeenCalledWith("/explainer/option-3b.html");
    });
});
