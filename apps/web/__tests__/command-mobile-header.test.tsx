/**
 * MobileCommandHeader — focused logout contract tests (hotfix).
 *
 * Verifies that the mobile drawer logout still works after the desktop
 * account/logout control was added to CommandObsidianShell. The mobile
 * surface is unchanged — this test guards against regressions.
 */

import { MobileCommandHeader } from "@/components/command/MobileCommandHeader";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
    usePathname: () => "/command",
}));
vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: any) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

vi.mock("@/lib/api", () => ({
    fetchMe: vi.fn().mockResolvedValue({ authenticated: true, email: "u@u.com" }),
}));

const setLanguage = vi.fn();
let mockLanguage = "en";
vi.mock("@/contexts/LanguageContext", () => ({
    useLanguage: () => ({ language: mockLanguage, setLanguage }),
}));
vi.mock("@/contexts/ThemeContext", () => ({
    useTheme: () => ({ resolvedTheme: "dark", setTheme: vi.fn() }),
}));

beforeEach(() => {
    mockLanguage = "en";
    setLanguage.mockReset();
});

describe("MobileCommandHeader — drawer logout (hotfix regression guard)", () => {
    it("authenticated drawer shows Log out and clicking it calls onLogout once", () => {
        const onLogout = vi.fn();
        render(
            <MobileCommandHeader
                chatAudience="authenticated"
                onLogout={onLogout}
                onNewChat={vi.fn()}
                onClearChat={vi.fn()}
                loginHref="/login"
                signupHref="/signup"
            />,
        );

        // Open the drawer
        fireEvent.click(screen.getByLabelText(/open menu/i));

        // Logout button is in the drawer's auth footer
        const logoutBtn = screen.getByText(/log out/i);
        expect(logoutBtn).toBeInTheDocument();
        fireEvent.click(logoutBtn);
        expect(onLogout).toHaveBeenCalledTimes(1);
    });

    it("public drawer does not show Log out", () => {
        const onLogout = vi.fn();
        render(
            <MobileCommandHeader
                chatAudience="public"
                onLogout={onLogout}
                onNewChat={vi.fn()}
                onClearChat={vi.fn()}
                loginHref="/login"
                signupHref="/signup"
            />,
        );

        // Open the drawer
        fireEvent.click(screen.getByLabelText(/open menu/i));

        // Public drawer shows sign-up/sign-in, not logout
        expect(screen.queryByText(/log out/i)).not.toBeInTheDocument();
    });
});
