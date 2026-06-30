/**
 * Regression test for BUG-7: session hydration — a logged-in user briefly
 * saw the sidebar render with the generic guest "User" label (and no
 * widgets/logout) while /command was still verifying the session
 * (chatAudience === "checking"), making the page look logged-out until the
 * /me check resolved.
 *
 * Fix: AppSidebar now accepts a `loading` prop. When true, the footer
 * renders a skeleton placeholder instead of falling back to the generic
 * "User" label, so a verifying session is never visually indistinguishable
 * from a logged-out one.
 */
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "@/contexts/LanguageContext";
import { AppSidebar } from "@/components/layout/AppSidebar";

vi.mock("next/navigation", () => ({
    usePathname: () => "/command",
}));

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

vi.mock("@/hooks/useSidebarStatus", () => ({
    useSidebarStatus: () => ({
        readiness: null,
        pipeline: null,
        plan: null,
        queueCount: 0,
        loading: false,
        error: false,
        refresh: vi.fn(),
    }),
}));

function renderSidebar(props: Partial<React.ComponentProps<typeof AppSidebar>> = {}) {
    return render(
        <LanguageProvider>
            <AppSidebar {...props} />
        </LanguageProvider>,
    );
}

describe("BUG-7: AppSidebar does not look logged-out while the session is still verifying", () => {
    it("renders a loading skeleton, not the generic guest avatar/footer, when loading=true", () => {
        renderSidebar({ loading: true });

        // The footer avatar (initials "R", same fallback as a resolved guest) must
        // NOT render during "checking" — only the brand-header "R" should be
        // present — otherwise a verifying session looks identical to a guest.
        expect(screen.getAllByText("R")).toHaveLength(1);
        expect(screen.queryByRole("button", { name: /log out/i })).not.toBeInTheDocument();
        expect(screen.getByRole("status")).toBeInTheDocument();
    });

    it("renders the real logout button + user name once loading=false and a user is known", () => {
        renderSidebar({ loading: false, user: { name: "Jane Doe", email: "jane@example.com" }, onLogout: vi.fn() });

        expect(screen.getByText("Jane Doe")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
        expect(screen.queryByRole("status")).not.toBeInTheDocument();
    });

    it("still falls back to the real (non-skeleton) guest footer when explicitly resolved as public", () => {
        // Unauthenticated/public is a real, resolved state — distinct from "checking"
        // — so the original (non-skeleton) guest footer is the correct behavior here:
        // the footer avatar renders its own "R" fallback alongside the brand header's.
        renderSidebar({ loading: false });

        expect(screen.getAllByText("R")).toHaveLength(2);
        expect(screen.queryByRole("status")).not.toBeInTheDocument();
    });
});
