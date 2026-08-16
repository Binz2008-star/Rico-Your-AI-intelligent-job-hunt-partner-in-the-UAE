/**
 * H-5 guest→account merge — store wiring.
 *
 * useAuthStore.login(email, password) must internally attach this browser's
 * existing guest session (public:<sid>) as the merge offer. The sid comes from
 * localStorage only when it already exists; no guest identity is ever minted by
 * logging in. The backend remains authoritative for the actual merge.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const { loginCalls } = vi.hoisted(() => ({ loginCalls: [] as unknown[][] }));
const { loginMock } = vi.hoisted(() => ({
    loginMock: vi.fn((...args: unknown[]) => {
        loginCalls.push(args);
        return Promise.resolve({ message: "ok", email: "u@example.com" });
    }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api")>();
    return { ...actual, login: loginMock };
});

import { useAuthStore } from "@/lib/store/useAuthStore";

beforeEach(() => {
    loginCalls.length = 0;
    window.localStorage.clear();
});

describe("useAuthStore.login guest merge", () => {
    it("passes the existing guest session as the merge offer", async () => {
        window.localStorage.setItem("rico_sid", "web-merge0000000001");

        await useAuthStore.getState().login("u@example.com", "pw");

        expect(loginCalls).toHaveLength(1);
        expect(loginCalls[0]).toEqual([
            "u@example.com",
            "pw",
            "public:web-merge0000000001",
        ]);
    });

    it("passes null (no merge offer) when there is no guest session", async () => {
        await useAuthStore.getState().login("u@example.com", "pw");

        expect(loginCalls).toHaveLength(1);
        expect(loginCalls[0]).toEqual(["u@example.com", "pw", null]);
    });

    it("does not mint a guest session while logging in", async () => {
        await useAuthStore.getState().login("u@example.com", "pw");

        expect(window.localStorage.getItem("rico_sid")).toBeNull();
    });
});
