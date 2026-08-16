/**
 * H-5 guest→account merge wiring.
 *
 * The backend merge contract (lib/api login/register `public_user_id_to_merge`)
 * was already implemented and is server-authoritative (HttpOnly capability
 * cookie + durable claim). The missing piece was the FRONTEND exposing it: the
 * auth flows must offer this browser's existing guest session for merge, and
 * must NOT invent one (logging in must never mint a guest identity).
 */
import { beforeEach, describe, expect, it } from "vitest";
import { getExistingPublicUserId } from "@/lib/publicSession";

beforeEach(() => {
    window.localStorage.clear();
});

describe("getExistingPublicUserId", () => {
    it("returns null when no guest session exists (never mints)", () => {
        expect(window.localStorage.getItem("rico_sid")).toBeNull();
        expect(getExistingPublicUserId()).toBeNull();
        expect(window.localStorage.getItem("rico_sid")).toBeNull();
    });

    it("returns the public: label for an existing guest session", () => {
        window.localStorage.setItem("rico_sid", "web-1234567890abcdef");
        expect(getExistingPublicUserId()).toBe("public:web-1234567890abcdef");
    });

    it("is correlation-only and needs no server disclosure", () => {
        window.localStorage.setItem("rico_sid", "web-deadbeef00000000");
        expect(getExistingPublicUserId()).toMatch(/^public:web-[A-Za-z0-9-]+$/);
    });
});
