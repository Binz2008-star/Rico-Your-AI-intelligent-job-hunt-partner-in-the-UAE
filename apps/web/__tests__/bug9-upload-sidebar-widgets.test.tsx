/**
 * Regression test for BUG-9: the desktop sidebar's status widgets and
 * WhatsApp support link (gated on AppSidebar's `enabled = Boolean(onLogout)`)
 * silently disappeared on /upload because UploadPage never passed
 * `sidebarProps` to AppShell — so `onLogout` was always undefined, even for
 * an authenticated user.
 *
 * Fix: UploadPage now captures the authenticated user from fetchMe() and
 * passes `sidebarProps={{ user, onLogout }}` once authenticated, matching
 * every other AppShell page (queue, flow, profile, settings, subscription).
 */
import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "@/contexts/LanguageContext";

const { fetchMeMock, listUserFilesMock, fetchProfileMock, clearAuthMock } = vi.hoisted(() => ({
    fetchMeMock: vi.fn(),
    listUserFilesMock: vi.fn().mockResolvedValue([]),
    fetchProfileMock: vi.fn().mockResolvedValue(null),
    clearAuthMock: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/upload",
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

vi.mock("@/hooks/useSidebarStatus", () => ({
    useSidebarStatus: (enabled: boolean) => ({
        readiness: null,
        pipeline: null,
        plan: null,
        queueCount: 0,
        loading: enabled,
        error: false,
        refresh: vi.fn(),
    }),
}));

vi.mock("@/lib/auth", () => ({
    clearAuth: clearAuthMock,
}));

vi.mock("@/lib/api", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    return {
        ...actual,
        fetchMe: fetchMeMock,
        listUserFiles: listUserFilesMock,
        fetchProfile: fetchProfileMock,
    };
});

import UploadPage from "@/app/upload/page";

function renderUpload() {
    return render(
        <LanguageProvider>
            <UploadPage />
        </LanguageProvider>,
    );
}

describe("BUG-9: sidebar widgets must not disappear on /upload for an authenticated user", () => {
    it("shows the logout button and WhatsApp support link once an authenticated session resolves", async () => {
        fetchMeMock.mockResolvedValue({
            authenticated: true,
            guest: false,
            role: "user",
            email: "jane@example.com",
            name: "Jane Doe",
        });

        renderUpload();

        expect(await screen.findByRole("button", { name: /log out/i })).toBeInTheDocument();
        expect(screen.getByText("Support on WhatsApp")).toBeInTheDocument();
    });

    it("still hides logout/widgets for an unauthenticated guest (correct, unchanged behavior)", async () => {
        fetchMeMock.mockResolvedValue({
            authenticated: false,
            guest: true,
            role: "guest",
            email: null,
        });

        renderUpload();

        await waitFor(() => expect(screen.queryByText(/upload your cv/i)).toBeInTheDocument());
        expect(screen.queryByRole("button", { name: /log out/i })).not.toBeInTheDocument();
        expect(screen.queryByText("Support on WhatsApp")).not.toBeInTheDocument();
    });
});
