/**
 * BUG-18 — ?q=/?prompt= deep-link params must be one-shot.
 *
 * Verifies stripDeepLinkParams captures the prompt and returns a cleaned search
 * string with the prompt/q params removed (so the /command effect can strip them
 * from the URL via replaceState). If they survived a refresh, the same prompt
 * would re-fire and mutate an already-active chat thread.
 */
import { describe, expect, it } from "vitest";
import { stripDeepLinkParams } from "@/lib/deepLinkPrompt";

describe("stripDeepLinkParams (BUG-18)", () => {
    it("captures ?q= and strips it from the search", () => {
        const r = stripDeepLinkParams("?q=Show my applications");
        expect(r.prompt).toBe("Show my applications");
        expect(r.changed).toBe(true);
        expect(r.cleanSearch).toBe("");
    });

    it("captures legacy ?prompt= and strips it", () => {
        const r = stripDeepLinkParams("?prompt=Find UAE jobs");
        expect(r.prompt).toBe("Find UAE jobs");
        expect(r.changed).toBe(true);
        expect(r.cleanSearch).toBe("");
    });

    it("prefers ?prompt= over ?q= when both are present, and strips both", () => {
        const r = stripDeepLinkParams("?prompt=legacy&q=newer");
        expect(r.prompt).toBe("legacy");
        expect(r.changed).toBe(true);
        expect(r.cleanSearch).toBe("");
    });

    it("preserves other params (e.g. cv=ready) while stripping q", () => {
        const r = stripDeepLinkParams("?q=Find+jobs&cv=ready");
        expect(r.prompt).toBe("Find jobs");
        expect(r.changed).toBe(true);
        expect(r.cleanSearch).toBe("?cv=ready");
    });

    it("is a no-op when neither prompt nor q is present", () => {
        const r = stripDeepLinkParams("?cv=ready");
        expect(r.prompt).toBeNull();
        expect(r.changed).toBe(false);
        expect(r.cleanSearch).toBe("?cv=ready");
    });

    it("handles an empty search string", () => {
        const r = stripDeepLinkParams("");
        expect(r.prompt).toBeNull();
        expect(r.changed).toBe(false);
        expect(r.cleanSearch).toBe("");
    });

    it("treats an empty ?q= as present (changed) but an empty-string prompt", () => {
        const r = stripDeepLinkParams("?q=");
        // present-but-empty: strip it so a refresh can't re-read it; prompt is "" (falsy),
        // so the /command init effect will not fire a send.
        expect(r.prompt).toBe("");
        expect(r.changed).toBe(true);
        expect(r.cleanSearch).toBe("");
    });
});
