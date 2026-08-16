/**
 * H-5 guest→account merge — SignupForm wiring.
 *
 * SignupForm must offer this browser's existing guest session for merge when
 * creating the account (register(email, password, public:<sid>, name)). With no
 * guest session it passes null. The backend is authoritative for the merge.
 */
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithProviders as render } from "./test-utils";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { registerCalls } = vi.hoisted(() => ({ registerCalls: [] as unknown[][] }));
const { registerMock } = vi.hoisted(() => ({
    registerMock: vi.fn((...args: unknown[]) => {
        registerCalls.push(args);
        return Promise.resolve({
            email: "u@example.com",
            role: "user",
            email_verification_required: true,
        });
    }),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("next/link", () => ({
    default: ({ children, href }: { children: ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}));
vi.mock("@/lib/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api")>();
    return { ...actual, register: registerMock, resendVerification: vi.fn() };
});

import { SignupForm } from "@/components/auth/SignupForm";

function submitSignup() {
    fireEvent.change(screen.getByPlaceholderText("Your name"), { target: { value: "Uma" } });
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "u@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("••••••••"), { target: { value: "password123" } });
    const form = document.querySelector("form") as HTMLFormElement;
    fireEvent.submit(form);
}

beforeEach(() => {
    registerCalls.length = 0;
    window.localStorage.clear();
});

describe("SignupForm guest merge", () => {
    it("offers an existing guest session for merge", async () => {
        window.localStorage.setItem("rico_sid", "web-signup0000000001");
        render(<SignupForm />);
        submitSignup();

        await waitFor(() => expect(registerCalls).toHaveLength(1));
        expect(registerCalls[0]).toEqual([
            "u@example.com",
            "password123",
            "public:web-signup0000000001",
            "Uma",
        ]);
    });

    it("passes null when there is no guest session", async () => {
        render(<SignupForm />);
        submitSignup();

        await waitFor(() => expect(registerCalls).toHaveLength(1));
        expect(registerCalls[0]).toEqual([
            "u@example.com",
            "password123",
            null,
            "Uma",
        ]);
    });
});
