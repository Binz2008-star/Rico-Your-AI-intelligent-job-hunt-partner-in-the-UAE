/**
 * Guest correlation id (#1070, locked design): one CSPRNG-only helper for
 * every surface, correlation-only semantics, and NO automatic rotation.
 *
 * The direct /upload path previously minted `rico_sid` with
 * Date.now()+Math.random(), permanently carrying a low-entropy id into
 * /command. Both paths now share lib/publicSession. Authorization lives in
 * the server's HttpOnly capability cookie; the localStorage value only labels
 * requests only; the server-authoritative sid is never disclosed to JS.
 * Cookie loss or capability errors must NOT silently rotate the id —
 * failures stay observable; the only mutation path is the first mint.
 */
import { beforeEach, describe, expect, it } from "vitest";
import { ensurePublicSessionId, getPublicUserId } from "@/lib/publicSession";
import { ensureSessionId } from "@/app/command/sessionId";

beforeEach(() => {
    window.localStorage.clear();
});

describe("publicSession correlation id", () => {
    it("mints a web- prefixed CSPRNG id within the server charset bounds", () => {
        const sid = ensurePublicSessionId();
        expect(sid).toMatch(/^web-[A-Za-z0-9-]+$/);
        expect(sid.length).toBeGreaterThanOrEqual(8);
        expect(sid.length).toBeLessThanOrEqual(64);
        // No Date.now()-style timestamp prefix (the old weak path embedded a
        // base36 timestamp as the first segment).
        expect(sid).not.toMatch(/^web-[a-z0-9]{8}-[a-z0-9]{7}$/);
    });

    it("is stable across calls and shared with the command-page wrapper", () => {
        const sid = ensurePublicSessionId();
        expect(ensurePublicSessionId()).toBe(sid);
        const ref = { current: null as string | null };
        expect(ensureSessionId(ref)).toBe(sid);
        expect(getPublicUserId()).toBe(`public:${sid}`);
    });

    it("never rotates or adopts a server identity — correlation only", () => {
        // The server-authoritative sid is NEVER disclosed to JavaScript, and
        // cookie loss / capability failures must not silently mint a fresh
        // correlation id. The ONLY mutation path is the first mint.
        const sid = ensurePublicSessionId();
        expect(ensurePublicSessionId()).toBe(sid);
        const ref = { current: null as string | null };
        expect(ensureSessionId(ref)).toBe(sid);
        // The module deliberately exposes no rotation/sync API.
        import("@/lib/publicSession").then((mod) => {
            expect("rotatePublicSessionId" in mod).toBe(false);
            expect("syncPublicSessionId" in mod).toBe(false);
        });
    });
});
