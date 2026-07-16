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
 *   4. The chooser navigates to the real film URL tagged #rico-rotation;
 *      the film masks its address bar back to the chooser
 *      (history.replaceState), so a reload re-enters the rotation.
 *   5. After a film's single pass, the visitor lands on the landing page
 *      (`/?after-film=1`); Skip/Join keep targeting /signup.
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
    isValidDeck(parsed: unknown): boolean;
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

describe("rotation films — after the film comes the landing page", () => {
    // Owner directive 2026-07-16: a film's single pass must end by handing
    // the visitor to the landing (`/?after-film=1`), not by looping, while
    // Skip/Join keep targeting /signup.
    for (const film of REQUIRED_FILMS) {
        const name = film.replace("/explainer/", "");
        const html = readFileSync(resolve(EXPLAINER_DIR, name), "utf8");

        it(`${name} ends its pass at the landing, not a loop`, () => {
            expect(html).toMatch(/window\.location\.href\s*=\s*'\/\?after-film=1'/);
            // advance() must terminate into goLanding instead of wrapping to 0.
            expect(html).toMatch(/function advance\(\)\{[^}]*goLanding\(\); return;/);
            expect(html).not.toMatch(/function advance\(\)\{[^}]*if\(n>=scenes\.length\) n=0;/);
        });

        it(`${name} keeps its Skip/Join CTA on /signup`, () => {
            expect(html).toContain("var REGISTER_URL = 'https://ricohunt.com/signup'");
        });

        it(`${name} masks its URL back to the chooser when arriving from the rotation`, () => {
            expect(html).toContain("location.hash==='#rico-rotation'");
            expect(html).toMatch(
                /history\.replaceState\(null,'','\/explainer\/index\.html'\+location\.search\)/,
            );
        });
    }
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

    it("rebuilds a stale persisted deck containing retired films", () => {
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

    it("rebuilds a deck with duplicate valid entries — a duplicate must not cause an immediate repeat", () => {
        const chooser = loadChooser();
        const storage = memoryStorage();
        // A corrupt deck like [option-2, option-2] would replay option-2
        // back-to-back if accepted verbatim.
        storage.map.set(
            "rico-film-deck-v1",
            JSON.stringify([REQUIRED_FILMS[0], REQUIRED_FILMS[0]]),
        );
        storage.map.set("rico-film-last-v1", REQUIRED_FILMS[0]);

        const draws = Array.from({ length: 6 }, () =>
            chooser.nextFilm(storage, Math.random),
        );

        // The rebuilt rotation must not open with the film that just played…
        expect(draws[0]).not.toBe(REQUIRED_FILMS[0]);
        // …and must restore full non-repeating cycles with no adjacent repeats.
        expect(sorted(draws.slice(0, 3))).toEqual(sorted(REQUIRED_FILMS));
        expect(sorted(draws.slice(3, 6))).toEqual(sorted(REQUIRED_FILMS));
        for (let i = 1; i < draws.length; i++) {
            expect(draws[i]).not.toBe(draws[i - 1]);
        }
    });

    it("accepts only a unique subset of the approved films as a persisted deck", () => {
        const { isValidDeck } = loadChooser();

        expect(isValidDeck([])).toBe(true);
        expect(isValidDeck([REQUIRED_FILMS[1]])).toBe(true);
        expect(isValidDeck([...REQUIRED_FILMS])).toBe(true);

        expect(isValidDeck([REQUIRED_FILMS[0], REQUIRED_FILMS[0]])).toBe(false); // duplicate
        expect(isValidDeck(["/explainer/option-1.html"])).toBe(false); // retired film
        expect(isValidDeck([...REQUIRED_FILMS, REQUIRED_FILMS[0]])).toBe(false); // longer than one cycle
        expect(isValidDeck("not-an-array")).toBe(false);
        expect(isValidDeck(null)).toBe(false);
        expect(isValidDeck([42])).toBe(false);
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

describe("explainer film chooser — navigation carries the rotation tag", () => {
    it("replaces to the real film URL tagged #rico-rotation, preserving the query", () => {
        const chooser = loadChooser();
        const win = {
            document: {},
            location: { replace: vi.fn(), search: "?utm=x", hash: "#ignored" },
        };

        chooser.showFilm(win, "/explainer/option-3.html");

        expect(win.location.replace).toHaveBeenCalledWith(
            "/explainer/option-3.html?utm=x#rico-rotation",
        );
    });

    it("plain visit → film URL with just the rotation tag", () => {
        const chooser = loadChooser();
        const win = {
            document: {},
            location: { replace: vi.fn(), search: "", hash: "" },
        };

        chooser.showFilm(win, "/explainer/option-2.html");

        expect(win.location.replace).toHaveBeenCalledWith(
            "/explainer/option-2.html#rico-rotation",
        );
    });
});
