/**
 * /upload dual-mode shell composition (supersedes the BUG-9 sidebar-widgets
 * regression).
 *
 * /upload migrated to the Atelier shells: WorkspaceShell (Shell C) for an
 * authenticated user, and the public AtelierAuthShell for a guest. BUG-9 — the
 * old AppShell sidebar's logout/status widgets silently disappearing when
 * `onLogout` was undefined — is now structurally impossible: WorkspaceShell owns
 * one consistent chrome for every authenticated workspace route, with no
 * per-page `sidebarProps`.
 *
 * These tests pin the dual composition and the critical guest invariant:
 *  - authenticated → WorkspaceShell chrome (workspace nav) + the file manager
 *  - guest        → the public upload flow, and the authenticated workspace
 *                   navigation is NEVER exposed to an unauthenticated visitor.
 */
import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "@/contexts/LanguageContext";

const { fetchMeMock, listUserFilesMock, fetchProfileMock } = vi.hoisted(() => ({
    fetchMeMock: vi.fn(),
    listUserFilesMock: vi.fn().mockResolvedValue({ files: [] }),
    fetchProfileMock: vi.fn().mockResolvedValue(null),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/upload",
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>{children}</a>
    ),
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

// Clear call history between tests (the mocks are shared/hoisted); mockClear
// keeps the resolved-value implementations set below and per-test.
beforeEach(() => {
    vi.clearAllMocks();
    listUserFilesMock.mockResolvedValue({ files: [] });
    fetchProfileMock.mockResolvedValue(null);
});

function renderUpload() {
    return render(
        <LanguageProvider>
            <UploadPage />
        </LanguageProvider>,
    );
}

function hasLinkTo(href: string): boolean {
    return screen.queryAllByRole("link").some((a) => a.getAttribute("href") === href);
}

describe("/upload — authenticated user", () => {
    it("renders the WorkspaceShell workspace chrome and the My files manager", async () => {
        fetchMeMock.mockResolvedValue({ authenticated: true, guest: false, role: "user", email: "jane@example.com", name: "Jane Doe" });
        listUserFilesMock.mockResolvedValue({ files: [] });

        renderUpload();

        // WorkspaceShell renders a <main> landmark + the authenticated workspace nav.
        expect(await screen.findByRole("main")).toBeInTheDocument();
        expect(hasLinkTo("/profile")).toBe(true);
        expect(hasLinkTo("/settings")).toBe(true);
        // The file manager loaded (empty-state calls listUserFiles).
        await waitFor(() => expect(listUserFilesMock).toHaveBeenCalled());
    });
});

describe("/upload — guest (public upload flow preserved)", () => {
    it("renders the guest upload and never exposes the authenticated workspace nav", async () => {
        fetchMeMock.mockResolvedValue({ authenticated: false, guest: true, role: "guest", email: null });

        renderUpload();

        await waitFor(() => expect(screen.getByText(/upload your cv/i)).toBeInTheDocument());
        // No authenticated workspace navigation and no logout for a guest.
        expect(hasLinkTo("/profile")).toBe(false);
        expect(hasLinkTo("/settings")).toBe(false);
        expect(screen.queryByRole("button", { name: /log out/i })).not.toBeInTheDocument();
        // The guest never triggers the authenticated file-list request.
        expect(listUserFilesMock).not.toHaveBeenCalled();
    });
});
