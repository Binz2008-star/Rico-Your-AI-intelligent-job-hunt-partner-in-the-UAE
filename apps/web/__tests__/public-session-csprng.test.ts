/**
 * Guest session minting (#1070): one CSPRNG-only helper for every surface.
 *
 * The direct /upload path previously minted `rico_sid` with
 * Date.now()+Math.random(), permanently carrying a low-entropy id into
 * /command. Both paths now share lib/publicSession, and rotation (after a 403
 * guest_session_unverified) propagates through the command page's ref wrapper.
 */
import { beforeEach, describe, expect, it } from "vitest";
import {
    ensurePublicSessionId,
    getPublicUserId,
    isGuestSessionUnverified,
    rotatePublicSessionId,
} from "@/lib/publicSession";
import { ensureSessionId } from "@/app/command/sessionId";

beforeEach(() => {
    window.localStorage.clear();
});

describe("publicSession CSPRNG minting", () => {
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

    it("rotation mints a fresh id and the command ref picks it up", () => {
        const ref = { current: null as string | null };
        const before = ensureSessionId(ref);
        const rotated = rotatePublicSessionId();
        expect(rotated).not.toBe(before);
        // The ref wrapper re-reads storage, so the retired id is never reused.
        expect(ensureSessionId(ref)).toBe(rotated);
    });

    it("detects the server's guest_session_unverified error body", () => {
        expect(
            isGuestSessionUnverified({ detail: { code: "guest_session_unverified" } }),
        ).toBe(true);
        expect(isGuestSessionUnverified({ detail: "nope" })).toBe(false);
        expect(isGuestSessionUnverified(undefined)).toBe(false);
    });
});
