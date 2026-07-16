import { afterEach, describe, expect, it, vi } from "vitest";

import { ensureSessionId } from "@/app/command/sessionId";

// A fresh, mutable session-id holder equivalent to a React ref.
function makeRef(): { current: string | null } {
    return { current: null };
}

describe("ensureSessionId — public session id (FIX 4: CSPRNG bearer token)", () => {
    afterEach(() => {
        localStorage.clear();
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it("produces a web- prefixed id long enough to resist guessing", () => {
        localStorage.clear();
        const sid = ensureSessionId(makeRef());
        expect(sid.startsWith("web-")).toBe(true);
        expect(sid.length).toBeGreaterThan(20);
        // Must stay within the server's ^[A-Za-z0-9_-]{8,64}$ session-id constraint.
        expect(sid.length).toBeLessThanOrEqual(64);
        expect(sid).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    });

    it("mints a distinct id for each fresh session", () => {
        localStorage.clear();
        const a = ensureSessionId(makeRef());
        localStorage.clear();
        const b = ensureSessionId(makeRef());
        expect(a).not.toEqual(b);
    });

    it("uses crypto.randomUUID when it is available", () => {
        localStorage.clear();
        const fakeUuid = "11111111-2222-3333-4444-555555555555" as ReturnType<
            typeof crypto.randomUUID
        >;
        // Ensure a randomUUID exists to spy on even if the jsdom crypto lacks it.
        if (typeof crypto === "undefined" || typeof crypto.randomUUID !== "function") {
            vi.stubGlobal("crypto", { randomUUID: () => fakeUuid });
        }
        const spy = vi
            .spyOn(crypto, "randomUUID")
            .mockReturnValue(fakeUuid);

        const sid = ensureSessionId(makeRef());

        expect(spy).toHaveBeenCalled();
        expect(sid).toBe("web-11111111-2222-3333-4444-555555555555");
        // Total length stays comfortably within 64 chars ("web-" + 36-char uuid = 40).
        expect(sid.length).toBe(40);
    });

    it("persists the id in localStorage and reuses it", () => {
        localStorage.clear();
        const first = ensureSessionId(makeRef());
        // A new ref must read the stored value rather than mint a new one.
        const second = ensureSessionId(makeRef());
        expect(second).toBe(first);
        expect(localStorage.getItem("rico_sid")).toBe(first);
    });
});
